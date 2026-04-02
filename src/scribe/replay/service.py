"""Replay durable outbox entries to sinks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scribe.adapters.local.outbox import LocalOutbox
from scribe.replay.restore import restore_payload
from scribe.results import DeliveryStatus, PayloadFamily
from scribe.sinks import Sink


@dataclass(slots=True)
class ReplayEntryResult:
    """Replay outcome for one outbox entry."""

    replay_ref: str
    family: PayloadFamily
    target_sink: str
    status: DeliveryStatus
    detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == DeliveryStatus.SUCCESS


@dataclass(slots=True)
class ReplayBatchResult:
    """Aggregated replay outcome."""

    results: list[ReplayEntryResult] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def success_count(self) -> int:
        return sum(result.status == DeliveryStatus.SUCCESS for result in self.results)

    @property
    def failure_count(self) -> int:
        return sum(result.status == DeliveryStatus.FAILURE for result in self.results)

    @property
    def omitted_count(self) -> int:
        return sum(result.status == DeliveryStatus.SKIPPED for result in self.results)


def replay_outbox(
    *,
    outbox_root: str,
    sinks: list[Sink],
    sink_name: str | None = None,
    acknowledge_successes: bool = True,
    dead_letter_after_failures: int | None = None,
) -> ReplayBatchResult:
    """Replay pending outbox entries to their original sinks."""
    outbox = LocalOutbox(outbox_root)
    pending_entries = outbox.read_pending_entries()
    replay_failure_counts = outbox.replay_failure_counts()
    results: list[ReplayEntryResult] = []
    acknowledged_refs: list[str] = []
    sink_by_name = {sink.name: sink for sink in sinks}

    for entry in pending_entries:
        target_sink_name = str(entry["sink_name"])
        if sink_name is not None and target_sink_name != sink_name:
            continue

        family = PayloadFamily(str(entry["family"]))
        replay_ref = str(entry["replay_ref"])
        sink = sink_by_name.get(target_sink_name)
        if sink is None:
            results.append(
                ReplayEntryResult(
                    replay_ref=replay_ref,
                    family=family,
                    target_sink=target_sink_name,
                    status=DeliveryStatus.FAILURE,
                    detail="target sink is not configured",
                )
            )
            continue
        if not sink.supports(family):
            results.append(
                ReplayEntryResult(
                    replay_ref=replay_ref,
                    family=family,
                    target_sink=target_sink_name,
                    status=DeliveryStatus.SKIPPED,
                    detail="target sink does not support this payload family",
                )
            )
            continue

        payload: Any = restore_payload(str(entry["payload_type"]), entry["payload"])
        try:
            sink.capture(family=family, payload=payload)
        except Exception as exc:
            outbox.record_replay_failure(replay_ref, str(exc))
            failure_count = replay_failure_counts.get(replay_ref, 0) + 1
            replay_failure_counts[replay_ref] = failure_count
            if (
                dead_letter_after_failures is not None
                and dead_letter_after_failures > 0
                and failure_count >= dead_letter_after_failures
            ):
                outbox.dead_letter(
                    entry,
                    reason=f"replay_failed_{failure_count}_times:{exc}",
                )
            results.append(
                ReplayEntryResult(
                    replay_ref=replay_ref,
                    family=family,
                    target_sink=target_sink_name,
                    status=DeliveryStatus.FAILURE,
                    detail=str(exc),
                )
            )
        else:
            results.append(
                ReplayEntryResult(
                    replay_ref=replay_ref,
                    family=family,
                    target_sink=target_sink_name,
                    status=DeliveryStatus.SUCCESS,
                )
            )
            acknowledged_refs.append(replay_ref)

    if acknowledge_successes:
        outbox.acknowledge(acknowledged_refs)
    return ReplayBatchResult(results=results)
