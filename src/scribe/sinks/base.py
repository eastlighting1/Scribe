"""Sink interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from typing import Any

from scribe.results import PayloadFamily


class Sink(ABC):
    """Abstract sink that receives canonical payloads by family."""

    name: str
    supported_families: Collection[PayloadFamily]

    def supports(self, family: PayloadFamily) -> bool:
        """Return whether the sink supports a payload family."""
        return family in self.supported_families

    @abstractmethod
    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Capture a canonical payload."""
