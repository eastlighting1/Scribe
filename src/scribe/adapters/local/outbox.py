"""Durable local outbox for failed sink deliveries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scribe.results import PayloadFamily
from scribe.serialization.json_ready import to_json_ready
from scribe.utils import iso_utc_now, new_ref


class LocalOutbox:
    """Append-only durable store for failed sink deliveries."""

    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root).expanduser().resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._target = self.storage_root / "failed_deliveries.jsonl"
        self._ack_target = self.storage_root / "acked_deliveries.jsonl"
        self._replay_failure_target = self.storage_root / "replay_failures.jsonl"
        self._dead_letter_target = self.storage_root / "dead_letters.jsonl"

    def persist_failure(
        self,
        *,
        sink_name: str,
        family: PayloadFamily,
        payload: Any,
        error: str,
        attempts: int,
    ) -> str:
        """Persist a failed delivery for later replay."""
        replay_ref = new_ref("replay")
        entry = {
            "replay_ref": replay_ref,
            "failed_at": iso_utc_now(),
            "sink_name": sink_name,
            "family": family.value,
            "payload_type": type(payload).__name__,
            "error": error,
            "attempts": attempts,
            "payload": to_json_ready(payload),
        }
        with self._target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True))
            handle.write("\n")
        return replay_ref

    def read_entries(self) -> list[dict[str, Any]]:
        """Read all outbox entries."""
        if not self._target.exists():
            return []
        with self._target.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def read_acknowledged_refs(self) -> set[str]:
        """Read replay refs that were already acknowledged."""
        if not self._ack_target.exists():
            return set()
        with self._ack_target.open("r", encoding="utf-8") as handle:
            return {
                entry["replay_ref"]
                for line in handle
                if line.strip()
                for entry in [json.loads(line)]
                if "replay_ref" in entry
            }

    def read_pending_entries(self) -> list[dict[str, Any]]:
        """Read entries that were not yet acknowledged."""
        acknowledged = self.read_acknowledged_refs()
        return [
            entry
            for entry in self.read_entries()
            if entry.get("replay_ref") not in acknowledged
        ]

    def acknowledge(self, replay_refs: list[str]) -> None:
        """Mark replay refs as successfully re-delivered."""
        if not replay_refs:
            return
        with self._ack_target.open("a", encoding="utf-8") as handle:
            for replay_ref in replay_refs:
                handle.write(
                    json.dumps(
                        {"replay_ref": replay_ref, "acknowledged_at": iso_utc_now()},
                        sort_keys=True,
                    )
                )
                handle.write("\n")

    def record_replay_failure(self, replay_ref: str, detail: str) -> None:
        """Record a replay failure attempt for a replay ref."""
        with self._replay_failure_target.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "replay_ref": replay_ref,
                        "failed_at": iso_utc_now(),
                        "detail": detail,
                    },
                    sort_keys=True,
                )
            )
            handle.write("\n")

    def replay_failure_counts(self) -> dict[str, int]:
        """Return replay failure counts by replay ref."""
        counts: dict[str, int] = {}
        if not self._replay_failure_target.exists():
            return counts
        with self._replay_failure_target.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                replay_ref = entry.get("replay_ref")
                if isinstance(replay_ref, str):
                    counts[replay_ref] = counts.get(replay_ref, 0) + 1
        return counts

    def dead_letter(self, entry: dict[str, Any], *, reason: str) -> None:
        """Move an unrecoverable replay entry to the dead-letter log."""
        with self._dead_letter_target.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "dead_lettered_at": iso_utc_now(),
                        "reason": reason,
                        "entry": entry,
                    },
                    sort_keys=True,
                )
            )
            handle.write("\n")
        replay_ref = entry.get("replay_ref")
        if isinstance(replay_ref, str):
            self.acknowledge([replay_ref])

    def read_dead_letters(self) -> list[dict[str, Any]]:
        """Read dead-lettered replay entries."""
        if not self._dead_letter_target.exists():
            return []
        with self._dead_letter_target.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
