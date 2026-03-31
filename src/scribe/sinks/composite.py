"""Composite sink implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scribe.results import PayloadFamily
from scribe.sinks.base import Sink


class CompositeSink(Sink):
    """Forward payloads to multiple child sinks."""

    def __init__(self, sinks: Sequence[Sink], *, name: str = "composite") -> None:
        self.name = name
        self._sinks = list(sinks)
        self.supported_families = frozenset(
            family for sink in self._sinks for family in sink.supported_families
        )

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Forward a payload to all child sinks."""
        for sink in self._sinks:
            if sink.supports(family):
                sink.capture(family=family, payload=payload)
