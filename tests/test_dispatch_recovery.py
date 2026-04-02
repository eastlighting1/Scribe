from __future__ import annotations

from pathlib import Path
from typing import Any

from scribe import DeliveryStatus, EventEmission, InMemorySink, PayloadFamily, Scribe
from scribe.adapters.local.outbox import LocalOutbox
from scribe.config import ScribeConfig
from scribe.sinks import Sink


class AlwaysFailSink(Sink):
    name = "always-fail"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        raise RuntimeError(f"cannot store {family.value}")


class FlakySink(Sink):
    name = "flaky"
    supported_families = frozenset(PayloadFamily)

    def __init__(self, *, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.attempts = 0

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            raise RuntimeError(f"transient failure #{self.attempts}")


class RecordOnlySuccessSink(Sink):
    name = "record-only-success"
    supported_families = frozenset(PayloadFamily)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        if family == PayloadFamily.DEGRADATION:
            raise RuntimeError("degradation rejected")


def test_all_sink_failures_are_durably_queued_to_outbox(tmp_path: Path) -> None:
    outbox_root = tmp_path / "outbox"
    scribe = Scribe(
        project_name="demo-project",
        sinks=[AlwaysFailSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        result = run.event("run.note", message="captured with recovery")

    assert result.status == DeliveryStatus.DEGRADED
    assert result.recovered_to_outbox is True
    assert result.replay_refs
    outbox = LocalOutbox(outbox_root)
    entries = outbox.read_entries()
    assert entries
    assert any(entry["family"] == "record" for entry in entries)


def test_retry_recovers_transient_sink_failure_without_outbox(tmp_path: Path) -> None:
    sink = FlakySink(failures_before_success=2)
    scribe = Scribe(
        project_name="demo-project",
        sinks=[sink],
        config=ScribeConfig(
            retry_attempts=2,
            retry_backoff_seconds=0.0,
            outbox_root=tmp_path / "outbox",
        ),
    )

    with scribe.run("training") as run:
        result = run.event("run.note", message="captured after retries")

    assert result.status == DeliveryStatus.SUCCESS
    assert result.recovered_to_outbox is False
    assert sink.attempts >= 3


def test_degradation_evidence_can_fall_back_to_outbox(tmp_path: Path) -> None:
    outbox_root = tmp_path / "outbox"
    memory = InMemorySink()
    scribe = Scribe(
        project_name="demo-project",
        sinks=[memory, AlwaysFailSink(), RecordOnlySuccessSink()],
        config=ScribeConfig(outbox_root=outbox_root),
    )

    with scribe.run("training") as run:
        result = run.emit_events(
            [EventEmission("run.note", "captured with degraded delivery")]
        ).results[0]

    assert result.status == DeliveryStatus.DEGRADED
    assert result.degradation_payload is not None
    assert result.recovered_to_outbox is True
    outbox = LocalOutbox(outbox_root)
    entries = outbox.read_entries()
    assert any(entry["family"] == "degradation" for entry in entries)
