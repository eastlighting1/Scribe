"""Vendor-agnostic artifact registration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from scribe.spine_bridge import ArtifactManifest


class ArtifactSourceKind(StrEnum):
    """Source kinds for artifact body discovery."""

    PATH = "path"
    STAGED_PATH = "staged_path"
    URI = "uri"


class ArtifactBindingStatus(StrEnum):
    """Operational binding status for an artifact registration."""

    BOUND = "bound"
    PENDING = "pending"
    DEGRADED = "degraded"


@dataclass(slots=True, frozen=True)
class ArtifactSource:
    """Abstract description of where artifact bytes currently come from."""

    kind: ArtifactSourceKind
    uri: str
    exists: bool


@dataclass(slots=True, frozen=True)
class ArtifactVerificationPolicy:
    """Verification expectations for a registration request."""

    compute_hash: bool = True
    require_existing_source: bool = True


@dataclass(slots=True, frozen=True)
class ArtifactRegistrationRequest:
    """Vendor-agnostic request to register artifact identity and source."""

    artifact_ref: str
    artifact_kind: str
    source: ArtifactSource
    verification_policy: ArtifactVerificationPolicy
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ArtifactBinding:
    """Binding-oriented artifact registration payload."""

    request: ArtifactRegistrationRequest
    manifest: ArtifactManifest
    source: ArtifactSource
    project_name: str
    operation_context_ref: str | None
    binding_status: ArtifactBindingStatus = ArtifactBindingStatus.BOUND
    completeness_marker: str = "complete"
    degradation_marker: str = "none"
    attributes: dict[str, Any] = field(default_factory=dict)
