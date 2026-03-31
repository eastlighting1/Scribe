"""Utility helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def iso_utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def new_ref(prefix: str) -> str:
    """Create a readable unique identifier."""
    return f"{prefix}_{uuid4().hex}"


def stable_value(raw: str) -> str:
    """Normalize a human label into a Spine-friendly stable ref value."""
    normalized = re.sub(r"[^A-Za-z0-9._:/-]+", "-", raw.strip()).strip("-")
    return normalized or uuid4().hex


def file_sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def stable_mapping_ref(prefix: str, payload: dict[str, Any]) -> str:
    """Create a deterministic ref value from structured mapping content."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{prefix}.{digest[:16]}"
