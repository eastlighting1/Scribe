from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest import CaptureFixture

from scribe import Scribe
from scribe.config import ScribeConfig
from scribe.replay.cli import main
from scribe.results import PayloadFamily
from scribe.sinks import Sink


class AlwaysFailSink(Sink):
    name = "always-fail"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        raise RuntimeError("still failing")


def test_replay_cli_replays_local_jsonl_target(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    outbox_root = tmp_path / "outbox"
    storage_root = tmp_path / "store"
    scribe = Scribe(
        project_name="demo-project",
        sinks=[AlwaysFailSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        run.event("run.note", message="queued for cli replay")

    exit_code = main(
        [
            "--outbox-root",
            str(outbox_root),
            "--sink-kind",
            "local-jsonl",
            "--sink-name",
            "always-fail",
            "--target-sink-name",
            "always-fail",
            "--storage-root",
            str(storage_root),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "replayed=" in captured.out
    assert "omitted=0" in captured.out
    assert (storage_root / "records.jsonl").exists()
