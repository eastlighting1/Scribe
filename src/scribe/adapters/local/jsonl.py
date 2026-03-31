"""Inspectable JSONL-based local sink."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from scribe.results import PayloadFamily
from scribe.sinks.base import Sink


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        serialized = asdict(value)  # type: ignore[arg-type]
        return {key: _json_ready(inner) for key, inner in serialized.items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


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
            "payload": _json_ready(payload),
        }
        target = self.storage_root / self._FILENAMES[family]
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True))
            handle.write("\n")

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
