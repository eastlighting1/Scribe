"""Sink interfaces and built-in implementations."""

from scribe.sinks.base import Sink
from scribe.sinks.composite import CompositeSink
from scribe.sinks.memory import InMemorySink

__all__ = ["CompositeSink", "InMemorySink", "LocalJsonlSink", "Sink"]


def __getattr__(name: str) -> object:
    if name == "LocalJsonlSink":
        from scribe.adapters.local.jsonl import LocalJsonlSink

        return LocalJsonlSink
    raise AttributeError(f"module 'scribe.sinks' has no attribute {name!r}")
