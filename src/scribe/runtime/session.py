"""Runtime session and lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

from scribe.canonical import ActiveContext
from scribe.config import ScribeConfig
from scribe.context.state import ContextState
from scribe.exceptions import ContextError, ValidationError
from scribe.runtime.builders import (
    build_environment_snapshot,
    build_event_record,
    build_operation,
    build_project,
    build_run,
    build_stage,
)
from scribe.runtime.dispatch import dispatch_context, dispatch_record
from scribe.runtime.scopes import OperationScope, RunScope, StageScope
from scribe.sinks import Sink
from scribe.utils import iso_utc_now, new_ref, stable_mapping_ref, stable_value

if TYPE_CHECKING:
    from scribe.runtime.scopes import BaseScope


class RuntimeSession:
    """Owns explicit lifecycle state and sink dispatch configuration."""

    def __init__(
        self,
        *,
        project_name: str,
        sinks: Sequence[Sink],
        config: ScribeConfig,
    ) -> None:
        if not project_name.strip():
            raise ValidationError("project_name must not be empty.")

        self.project_name = project_name
        self.sinks = list(sinks)
        self.config = config
        self._state: ContextVar[ContextState | None] = ContextVar(
            "scribe_context_state",
            default=None,
        )
        self._state.set(ContextState.initial(project_name))
        self._scope_tokens: dict[int, Token[ContextState | None]] = {}
        self._project = build_project(project_name=self.project_name, created_at=iso_utc_now())
        self._stage_counter = 0
        self._session_id = new_ref("session")

    def resolve_context(self) -> ActiveContext:
        """Return the current active context."""
        state = self._current_state()
        return state.current

    def _current_state(self) -> ContextState:
        """Return the current task-local state."""
        state = self._state.get()
        if state is None:
            state = ContextState.initial(self.project_name)
            self._state.set(state)
        return state

    def require_run(self) -> None:
        """Ensure a run is active."""
        if self.resolve_context().run_ref is None:
            raise ContextError("An active run scope is required for this operation.")

    def current_run_scope(self) -> RunScope | None:
        """Return the active run scope if present."""
        return self._current_state().run_scope

    def current_stage_scope(self) -> StageScope | None:
        """Return the active stage scope if present."""
        return self._current_state().stage_scope

    def current_operation_scope(self) -> OperationScope | None:
        """Return the active operation scope if present."""
        return self._current_state().operation_scope

    def start_run(
        self,
        *,
        name: str,
        run_id: str | None = None,
        tags: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        code_revision: str | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        dataset_ref: str | None = None,
    ) -> RunScope:
        """Create a run scope."""
        if self.current_run_scope() is not None:
            raise ContextError("Nested runs are not allowed in the same session.")
        config_snapshot_dict = dict(config_snapshot) if config_snapshot is not None else None
        config_snapshot_ref = None
        if config_snapshot_dict:
            config_snapshot_ref = stable_mapping_ref("config", config_snapshot_dict)
        normalized_dataset_ref = stable_value(dataset_ref) if dataset_ref is not None else None
        return RunScope(
            self,
            scope_kind="run",
            ref=run_id or new_ref("run"),
            name=name,
            code_revision=code_revision,
            config_snapshot_ref=config_snapshot_ref,
            config_snapshot=config_snapshot_dict,
            dataset_ref=normalized_dataset_ref,
            tags=tags,
            metadata=metadata,
        )

    def start_stage(
        self,
        *,
        name: str,
        stage_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> StageScope:
        """Create a stage scope."""
        self.require_run()
        if self.current_stage_scope() is not None:
            raise ContextError("Nested stages are not allowed in the same session.")
        return StageScope(
            self,
            scope_kind="stage",
            ref=stage_ref or new_ref("stage"),
            name=name,
            metadata=metadata,
        )

    def start_operation(
        self,
        *,
        name: str,
        operation_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> OperationScope:
        """Create an operation scope."""
        self.require_run()
        return OperationScope(
            self,
            scope_kind="operation",
            ref=operation_ref or new_ref("op"),
            name=name,
            metadata=metadata,
        )

    def enter_scope(self, scope: BaseScope) -> None:
        """Push a scope into the active context."""
        current_state = self._current_state()
        current = current_state.current
        next_context = ActiveContext(
            project_name=current.project_name,
            run_ref=current.run_ref,
            run_name=current.run_name,
            stage_execution_ref=current.stage_execution_ref,
            stage_name=current.stage_name,
            operation_context_ref=current.operation_context_ref,
            operation_name=current.operation_name,
            trace_id=current.trace_id,
            session_id=current.session_id or self._session_id,
            code_revision=current.code_revision,
            config_snapshot_ref=current.config_snapshot_ref,
            dataset_ref=current.dataset_ref,
        )

        next_state = ContextState(
            current=next_context,
            run_scope=current_state.run_scope,
            stage_scope=current_state.stage_scope,
            operation_scope=current_state.operation_scope,
        )

        token = None
        if isinstance(scope, RunScope):
            scope.started_at = iso_utc_now()
            next_context.run_ref = scope.ref
            next_context.run_name = scope.name
            next_context.trace_id = scope.ref
            next_context.code_revision = scope.code_revision
            next_context.config_snapshot_ref = scope.config_snapshot_ref
            next_context.dataset_ref = scope.dataset_ref
            next_state.run_scope = scope
            token = self._state.set(next_state)
            try:
                dispatch_context(self, self._project)
                dispatch_context(
                    self,
                    build_run(
                        project_name=self.project_name,
                        run_ref=scope.ref,
                        name=scope.name,
                        status="running",
                        started_at=scope.started_at,
                        ended_at=None,
                        code_revision=scope.code_revision,
                        config_snapshot_ref=scope.config_snapshot_ref,
                        dataset_ref=scope.dataset_ref,
                        config_snapshot=scope.config_snapshot,
                        tags=scope.tags,
                        metadata=scope.metadata,
                    ),
                )
                if self.config.capture_environment:
                    dispatch_context(
                        self,
                        build_environment_snapshot(
                            run_ref=scope.ref,
                            captured_at=scope.started_at,
                            capture_installed_packages=self.config.capture_installed_packages,
                            environment_variable_allowlist=self.config.environment_variable_allowlist,
                            code_revision=scope.code_revision,
                            config_snapshot_ref=scope.config_snapshot_ref,
                            dataset_ref=scope.dataset_ref,
                        ),
                    )
            except Exception:
                self._state.reset(token)
                raise
        elif isinstance(scope, StageScope):
            if next_context.run_ref is None:
                raise ContextError("A stage requires an active run.")
            self._stage_counter += 1
            scope.started_at = iso_utc_now()
            scope.order_index = self._stage_counter
            next_context.stage_execution_ref = scope.ref
            next_context.stage_name = scope.name
            next_state.stage_scope = scope
            next_state.operation_scope = None
            token = self._state.set(next_state)
            try:
                dispatch_context(
                    self,
                    build_stage(
                        run_ref=next_context.run_ref,
                        stage_ref=scope.ref,
                        stage_name=scope.name,
                        status="running",
                        started_at=scope.started_at,
                        ended_at=None,
                        order_index=scope.order_index,
                        metadata=scope.metadata,
                    ),
                )
            except Exception:
                self._state.reset(token)
                raise
        elif isinstance(scope, OperationScope):
            if next_context.run_ref is None:
                raise ContextError("An operation requires an active run.")
            scope.observed_at = iso_utc_now()
            next_context.operation_context_ref = scope.ref
            next_context.operation_name = scope.name
            next_state.operation_scope = scope
            token = self._state.set(next_state)
            try:
                dispatch_context(
                    self,
                    build_operation(
                        run_ref=next_context.run_ref,
                        stage_execution_ref=next_context.stage_execution_ref,
                        operation_ref=scope.ref,
                        operation_name=scope.name,
                        observed_at=scope.observed_at,
                        metadata=scope.metadata,
                    ),
                )
            except Exception:
                self._state.reset(token)
                raise

        if token is None:
            token = self._state.set(next_state)
        self._scope_tokens[id(scope)] = token
        self._emit_lifecycle_event(scope=scope, event="started", level="info")

    def close_scope(self, scope: BaseScope, *, status: str = "completed") -> None:
        """Pop a scope from the active context."""
        token = self._scope_tokens.pop(id(scope), None)
        if token is None:
            raise ContextError(f"Scope `{scope.name}` was never entered.")

        self._emit_lifecycle_event(
            scope=scope,
            event="completed" if status == "completed" else status,
            level="error" if status == "failed" else "info",
        )
        closed_at = iso_utc_now()
        current = self.resolve_context()
        if (
            isinstance(scope, StageScope)
            and scope.started_at is not None
            and current.run_ref is not None
        ):
            dispatch_context(
                self,
                build_stage(
                    run_ref=current.run_ref,
                    stage_ref=scope.ref,
                    stage_name=scope.name,
                    status=status,
                    started_at=scope.started_at,
                    ended_at=closed_at,
                    order_index=scope.order_index,
                    metadata=scope.metadata,
                ),
            )
        elif isinstance(scope, RunScope) and scope.started_at is not None:
            dispatch_context(
                self,
                build_run(
                    project_name=self.project_name,
                    run_ref=scope.ref,
                    name=scope.name,
                    status=status,
                    started_at=scope.started_at,
                    ended_at=closed_at,
                    code_revision=scope.code_revision,
                    config_snapshot_ref=scope.config_snapshot_ref,
                    dataset_ref=scope.dataset_ref,
                    config_snapshot=scope.config_snapshot,
                    tags=scope.tags,
                    metadata=scope.metadata,
                ),
            )

        self._state.reset(token)

    def _emit_lifecycle_event(self, *, scope: BaseScope, event: str, level: str) -> None:
        observed_at = iso_utc_now()
        record = build_event_record(
            self,
            key=f"{scope.scope_kind}.{event}",
            message=f"{scope.scope_kind}:{scope.name} {event}",
            level=level,
            attributes={"scope_ref": scope.ref, "scope_name": scope.name},
            tags=None,
            observed_at=observed_at,
        )
        dispatch_record(self, record)
