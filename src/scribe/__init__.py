"""Public package exports for Scribe."""

from scribe.api import Scribe
from scribe.artifacts import (
    ArtifactBinding,
    ArtifactBindingStatus,
    ArtifactRegistrationRequest,
    ArtifactSource,
    ArtifactSourceKind,
    ArtifactVerificationPolicy,
)
from scribe.events import EventEmission
from scribe.exceptions import (
    ClosedScopeError,
    ContextError,
    ScribeError,
    SinkDispatchError,
    ValidationError,
)
from scribe.metrics import MetricEmission
from scribe.replay import ReplayBatchResult, ReplayEntryResult, replay_cli_main, replay_outbox
from scribe.results import BatchCaptureResult, CaptureResult, DeliveryStatus, PayloadFamily
from scribe.sinks import CompositeSink, InMemorySink, Sink
from scribe.adapters.kafka.producer import KafkaSink
from scribe.adapters.local.jsonl import LocalJsonlSink
from scribe.adapters.s3.json_objects import S3ObjectSink

__all__ = [
    "ArtifactBinding",
    "ArtifactBindingStatus",
    "ArtifactRegistrationRequest",
    "ArtifactSource",
    "ArtifactSourceKind",
    "ArtifactVerificationPolicy",
    "BatchCaptureResult",
    "CaptureResult",
    "ClosedScopeError",
    "CompositeSink",
    "ContextError",
    "DeliveryStatus",
    "EventEmission",
    "InMemorySink",
    "KafkaSink",
    "LocalJsonlSink",
    "MetricEmission",
    "PayloadFamily",
    "ReplayBatchResult",
    "ReplayEntryResult",
    "replay_cli_main",
    "replay_outbox",
    "Scribe",
    "ScribeError",
    "S3ObjectSink",
    "Sink",
    "SinkDispatchError",
    "ValidationError",
]
