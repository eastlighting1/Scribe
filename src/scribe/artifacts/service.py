"""Artifact registration logic."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scribe.artifacts.models import (
    ArtifactBinding,
    ArtifactBindingStatus,
    ArtifactRegistrationRequest,
    ArtifactSource,
    ArtifactSourceKind,
    ArtifactVerificationPolicy,
)
from scribe.exceptions import ValidationError
from scribe.results import CaptureResult
from scribe.runtime.builders import build_artifact_manifest
from scribe.runtime.dispatch import dispatch_artifact
from scribe.utils import file_sha256, iso_utc_now, new_ref

if TYPE_CHECKING:
    from scribe.runtime.session import RuntimeSession


def register_artifact(
    runtime: RuntimeSession,
    *,
    artifact_kind: str,
    path: str | Path,
    artifact_ref: str | None = None,
    attributes: Mapping[str, Any] | None = None,
    compute_hash: bool = True,
    allow_missing: bool = False,
) -> CaptureResult:
    """Register an artifact binding and dispatch it to artifact-capable sinks."""
    runtime.require_run()

    if not artifact_kind.strip():
        raise ValidationError("artifact_kind must not be empty.")

    artifact_path = Path(path).expanduser()
    resolved_path = artifact_path.resolve(strict=False)
    exists = resolved_path.exists()
    verification_policy = ArtifactVerificationPolicy(
        compute_hash=compute_hash,
        require_existing_source=not allow_missing,
    )
    source = ArtifactSource(
        kind=ArtifactSourceKind.PATH,
        uri=str(resolved_path),
        exists=exists,
    )
    request = ArtifactRegistrationRequest(
        artifact_ref=artifact_ref or new_ref("artifact"),
        artifact_kind=artifact_kind,
        source=source,
        verification_policy=verification_policy,
        attributes=dict(attributes or {}),
    )

    if not exists and verification_policy.require_existing_source:
        raise ValidationError(f"Artifact path does not exist: {resolved_path}")

    hash_value = None
    degradation_reasons: list[str] = []
    warnings: list[str] = []

    if exists and verification_policy.compute_hash:
        try:
            hash_value = file_sha256(resolved_path)
        except OSError as exc:
            degradation_reasons.append("artifact_hash_unavailable")
            warnings.append(f"Artifact hash computation failed: {exc}")
    elif not exists:
        degradation_reasons.append("artifact_missing_at_registration")
        warnings.append("Artifact path was registered before the file existed.")

    size_bytes = resolved_path.stat().st_size if exists else None
    context = runtime.resolve_context()
    manifest = build_artifact_manifest(
        runtime,
        artifact_ref=request.artifact_ref,
        artifact_kind=artifact_kind,
        location_ref=str(resolved_path),
        hash_value=hash_value,
        size_bytes=size_bytes,
        attributes=request.attributes,
        created_at=iso_utc_now(),
    )
    binding = ArtifactBinding(
        request=request,
        manifest=manifest,
        project_name=context.project_name,
        operation_context_ref=context.operation_context_ref,
        source=source,
        binding_status=(
            ArtifactBindingStatus.DEGRADED
            if degradation_reasons
            else ArtifactBindingStatus.BOUND
        ),
        completeness_marker="partial" if degradation_reasons else "complete",
        degradation_marker="degraded" if degradation_reasons else "none",
        attributes=request.attributes,
    )

    return dispatch_artifact(
        runtime,
        binding,
        degradation_reasons=degradation_reasons,
        warnings=warnings,
    )
