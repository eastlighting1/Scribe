"""S3-backed object sink for canonical Scribe payloads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from scribe.results import PayloadFamily
from scribe.serialization.json_ready import to_json_ready
from scribe.sinks.base import Sink
from scribe.utils import stable_value


def _captured_at_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _payload_ref(payload: Any, family: PayloadFamily) -> str:
    if family is PayloadFamily.ARTIFACT and hasattr(payload, "manifest"):
        manifest = payload.manifest
        if hasattr(manifest, "artifact_ref"):
            return str(manifest.artifact_ref)
    if hasattr(payload, "envelope") and hasattr(payload.envelope, "record_ref"):
        return str(payload.envelope.record_ref)
    for field_name in (
        "operation_context_ref",
        "stage_execution_ref",
        "run_ref",
        "project_ref",
    ):
        value = getattr(payload, field_name, None)
        if value is not None:
            return str(value)
    return stable_value(type(payload).__name__)


class S3ObjectSink(Sink):
    """Persist each captured payload as a standalone JSON object in S3."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "scribe",
        client: Any | None = None,
        name: str = "s3-object",
    ) -> None:
        if not bucket.strip():
            raise ValueError("bucket must not be empty.")
        if not prefix.strip():
            raise ValueError("prefix must not be empty.")

        self.name = name
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.supported_families = frozenset(PayloadFamily)
        if client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "boto3 is required when no S3 client is supplied."
                ) from exc
            client = boto3.client("s3")
        self._client = client

    def capture(self, *, family: PayloadFamily, payload: Any) -> None:
        """Upload a single payload object to S3."""
        captured_at = _captured_at_now()
        entry = {
            "captured_at": captured_at,
            "family": family.value,
            "payload": to_json_ready(payload),
        }
        primary_ref = stable_value(_payload_ref(payload, family)).replace(":", "_")
        year, month, day = captured_at[:10].split("-")
        timestamp = captured_at.replace(":", "-").replace(".", "-")
        key = (
            f"{self.prefix}/{family.value}/{year}/{month}/{day}/"
            f"{timestamp}_{primary_ref}.json"
        )
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(entry, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
        )
