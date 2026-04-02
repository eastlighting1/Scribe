"""Local-first default adapters."""

from scribe.adapters.local.jsonl import LocalJsonlSink
from scribe.adapters.local.outbox import LocalOutbox

__all__ = ["LocalJsonlSink", "LocalOutbox"]
