"""Session-local context state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from scribe.canonical import ActiveContext

if TYPE_CHECKING:
    from scribe.runtime.scopes import OperationScope, RunScope, StageScope


@dataclass(slots=True)
class ContextState:
    """Mutable state for the current lifecycle stack."""

    current: ActiveContext
    run_scope: RunScope | None = None
    stage_scope: StageScope | None = None
    operation_scope: OperationScope | None = None

    @classmethod
    def initial(cls, project_name: str) -> ContextState:
        return cls(current=ActiveContext(project_name=project_name))
