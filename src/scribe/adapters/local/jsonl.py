"""Inspectable JSONL-based local sink."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scribe.results import PayloadFamily
from scribe.serialization.json_ready import to_json_ready
from scribe.sinks.base import Sink


class LocalJsonlSink(Sink):
    """Persist payload families to local JSONL files."""

    _FILENAMES = {
        PayloadFamily.CONTEXT: "contexts.jsonl",
        PayloadFamily.RECORD: "records.jsonl",
        PayloadFamily.ARTIFACT: "artifacts.jsonl",
        PayloadFamily.DEGRADATION: "degradations.jsonl",
    }

    def __init__(self, storage_root: str | Path, *, name: str = "local-jsonl") -> None:
        self.name = name
        self.supported_families = frozenset(PayloadFamily)
        self.storage_root = Path(storage_root).expanduser().resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Append a serialized payload to the family-specific JSONL file."""
        entry = {
            "captured_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
            "family": family.value,
            "payload": to_json_ready(payload),
        }
        target = self.storage_root / self._FILENAMES[family]
        try:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True))
                handle.write("\n")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to persist {family.value} payload to {target}"
            ) from exc

    def path_for(self, family: PayloadFamily) -> Path:
        """Return the on-disk file path for a payload family."""
        return self.storage_root / self._FILENAMES[family]

    def read_family(self, family: PayloadFamily) -> list[dict[str, Any]]:
        """Read all captured entries for a payload family."""
        target = self.path_for(family)
        if not target.exists():
            return []
        with target.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
