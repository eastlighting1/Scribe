"""Composite sink implementation."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Any

from scribe.exceptions import PartialSinkFailureError
from scribe.results import PayloadFamily
from scribe.sinks.base import Sink


class CompositeSink(Sink):
    """Forward payloads to multiple child sinks."""

    def __init__(self, sinks: Sequence[Sink], *, name: str = "composite") -> None:
        warnings.warn(
            "CompositeSink is deprecated; prefer passing multiple sinks directly to "
            "Scribe(..., sinks=[...]) so dispatch can report per-sink outcomes.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.name = name
        self._sinks = list(sinks)
        self.supported_families = frozenset(
            family for sink in self._sinks for family in sink.supported_families
        )

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Forward a payload to all child sinks."""
        failures: list[str] = []
        delivered = 0
        for sink in self._sinks:
            if sink.supports(family):
                try:
                    sink.capture(family=family, payload=payload)
                except Exception as exc:
                    failures.append(f"{sink.name}: {exc}")
                else:
                    delivered += 1
        if failures:
            message = "Composite sink child failures: " + "; ".join(failures)
            if delivered > 0:
                raise PartialSinkFailureError(message)
            raise RuntimeError(message)
