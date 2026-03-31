"""In-memory sink for tests and local experimentation."""

from __future__ import annotations

from typing import Any

from scribe.results import PayloadFamily
from scribe.sinks.base import Sink


class InMemorySink(Sink):
    """Store captured payloads in memory."""

    def __init__(self, *, name: str = "memory") -> None:
        self.name = name
        self.supported_families = frozenset(PayloadFamily)
        self.actions: list[tuple[PayloadFamily, Any]] = []

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Store the action and payload."""
        self.actions.append((family, payload))
