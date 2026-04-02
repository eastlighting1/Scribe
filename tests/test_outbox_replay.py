from __future__ import annotations

from typing import Any

from scribe import DeliveryStatus, Scribe, replay_outbox
from scribe.adapters.local.outbox import LocalOutbox
from scribe.config import ScribeConfig
from scribe.results import PayloadFamily
from scribe.sinks import Sink
from scribe.spine_bridge import StructuredEventRecord


class AlwaysFailSink(Sink):
    name = "always-fail"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        raise RuntimeError("still failing")


class RecordingSink(Sink):
    name = "always-fail"
    supported_families = frozenset(PayloadFamily)

    def __init__(self) -> None:
        self.actions: list[tuple[PayloadFamily, Any]] = []

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        self.actions.append((family, payload))


def test_replay_outbox_replays_pending_entries_and_acknowledges_success(tmp_path) -> None:
    outbox_root = tmp_path / "outbox"
    scribe = Scribe(
        project_name="demo-project",
        sinks=[AlwaysFailSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        result = run.event("run.note", message="queued for replay")

    assert result.recovered_to_outbox is True
    outbox = LocalOutbox(outbox_root)
    assert len(outbox.read_pending_entries()) >= 1

    replay_sink = RecordingSink()
    replay_result = replay_outbox(outbox_root=str(outbox_root), sinks=[replay_sink])

    assert replay_result.total_count >= 1
    assert replay_result.success_count >= 1
    assert replay_sink.actions
    assert any(isinstance(payload, StructuredEventRecord) for _, payload in replay_sink.actions)
    assert outbox.read_pending_entries() == []


def test_replay_outbox_leaves_failed_entries_pending(tmp_path) -> None:
    outbox_root = tmp_path / "outbox"
    scribe = Scribe(
        project_name="demo-project",
        sinks=[AlwaysFailSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        run.event("run.note", message="still pending")

    replay_result = replay_outbox(outbox_root=str(outbox_root), sinks=[AlwaysFailSink()])

    assert replay_result.failure_count >= 1
    assert replay_result.skipped_count == 0
    assert any(result.status == DeliveryStatus.FAILURE for result in replay_result.results)
    outbox = LocalOutbox(outbox_root)
    assert len(outbox.read_pending_entries()) >= 1


def test_replay_outbox_dead_letters_entries_after_threshold(tmp_path) -> None:
    outbox_root = tmp_path / "outbox"
    scribe = Scribe(
        project_name="demo-project",
        sinks=[AlwaysFailSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        run.event("run.note", message="dead-letter me")

    replay_result = replay_outbox(
        outbox_root=str(outbox_root),
        sinks=[AlwaysFailSink()],
        dead_letter_after_failures=1,
    )

    assert replay_result.failure_count >= 1
    outbox = LocalOutbox(outbox_root)
    assert outbox.read_pending_entries() == []
    dead_letters = outbox.read_dead_letters()
    assert dead_letters
    assert any(
        entry["entry"]["family"] == PayloadFamily.RECORD.value
        for entry in dead_letters
    )
