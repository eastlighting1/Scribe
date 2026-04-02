"""Kafka-backed sink for canonical Scribe payloads."""

from __future__ import annotations

import json
from typing import Any

from scribe.results import PayloadFamily
from scribe.serialization.json_ready import to_json_ready
from scribe.sinks.base import Sink


def _topic_for(topic_prefix: str, family: PayloadFamily) -> str:
    return f"{topic_prefix}.{family.value}"


def _key_for(payload: Any, family: PayloadFamily) -> str:
    if family is PayloadFamily.ARTIFACT and hasattr(payload, "manifest"):
        manifest = payload.manifest
        if hasattr(manifest, "artifact_ref"):
            return str(manifest.artifact_ref)
    if hasattr(payload, "envelope") and hasattr(payload.envelope, "run_ref"):
        return str(payload.envelope.run_ref)
    for field_name in ("run_ref", "stage_execution_ref", "operation_context_ref", "project_ref"):
        value = getattr(payload, field_name, None)
        if value is not None:
            return str(value)
    return family.value


class KafkaSink(Sink):
    """Publish captured payloads to Kafka topics by family."""

    def __init__(
        self,
        *,
        producer: Any | None = None,
        topic_prefix: str = "scribe",
        delivery_timeout_seconds: float = 10.0,
        name: str = "kafka",
    ) -> None:
        if not topic_prefix.strip():
            raise ValueError("topic_prefix must not be empty.")
        if delivery_timeout_seconds <= 0:
            raise ValueError("delivery_timeout_seconds must be > 0.")

        self.name = name
        self.topic_prefix = topic_prefix
        self.delivery_timeout_seconds = delivery_timeout_seconds
        self.supported_families = frozenset(PayloadFamily)
        if producer is None:
            try:
                from kafka import KafkaProducer  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "kafka-python is required when no producer is supplied."
                ) from exc
            producer = KafkaProducer()
        self._producer = producer

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Publish a single payload and wait for broker acknowledgement."""
        entry = {
            "family": family.value,
            "payload": to_json_ready(payload),
        }
        future = self._producer.send(
            _topic_for(self.topic_prefix, family),
            key=_key_for(payload, family).encode("utf-8"),
            value=json.dumps(entry, sort_keys=True).encode("utf-8"),
        )
        future.get(timeout=self.delivery_timeout_seconds)
