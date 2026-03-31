"""Local runtime and canonical payload models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActiveContext:
    """Resolved capture context for an emission."""

    project_name: str
    run_ref: str | None = None
    run_name: str | None = None
    stage_execution_ref: str | None = None
    stage_name: str | None = None
    operation_context_ref: str | None = None
    operation_name: str | None = None
    trace_id: str | None = None
    session_id: str | None = None
    code_revision: str | None = None
    config_snapshot_ref: str | None = None
    dataset_ref: str | None = None


@dataclass(slots=True)
class CanonicalRecord:
    """Canonical envelope for emitted record-family payloads."""

    record_id: str
    record_type: str
    schema_version: str
    recorded_at: str
    observed_at: str
    producer_ref: str
    project_name: str
    run_ref: str | None
    stage_execution_ref: str | None
    operation_context_ref: str | None
    completeness_marker: str
    degradation_marker: str
    tags: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
