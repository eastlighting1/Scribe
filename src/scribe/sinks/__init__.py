"""Sink interfaces and built-in implementations."""

from scribe.adapters.local import LocalJsonlSink
from scribe.sinks.base import Sink
from scribe.sinks.composite import CompositeSink
from scribe.sinks.memory import InMemorySink

__all__ = ["CompositeSink", "InMemorySink", "LocalJsonlSink", "Sink"]
