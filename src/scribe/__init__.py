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
from scribe.results import BatchCaptureResult, CaptureResult, DeliveryStatus, PayloadFamily
from scribe.sinks import CompositeSink, InMemorySink, LocalJsonlSink, Sink

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
    "LocalJsonlSink",
    "MetricEmission",
    "PayloadFamily",
    "Scribe",
    "ScribeError",
    "Sink",
    "SinkDispatchError",
    "ValidationError",
]
