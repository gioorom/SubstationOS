"""
The step-handler **contract** - the one abstraction the engine's executor
and handler registry depend on.

Deliberately a module of its own, separate from any concrete handler.
Every workflow's handlers implement this contract
(``step_handlers.py`` for KNOWLEDGE_QUERY,
``document_lookup_step_handlers.py`` for DOCUMENT_LOOKUP), so the engine
core can depend on the contract without ever importing a module that
knows what a prompt, a document or a graph is. That is precisely what
lets a new workflow arrive without the core changing.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailureCode,
    WorkflowStep,
    WorkflowStepType,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)


class StepHandlerError(Exception):
    """Raised by a handler to signal a typed, stage-specific failure.
    The executor converts it into a ``WorkflowStepFailure`` - a raw
    provider or service exception never escapes into the engine
    domain."""

    def __init__(
        self,
        code: EngineeringEngineFailureCode,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail

        super().__init__(message)


class WorkflowStepHandler(Protocol):
    """The one abstraction the engine core depends on.

    ``async`` because one genuine dependency (the provider-neutral LLM
    Runtime) is async. Making only that one handler async would force the
    executor to special-case it; handlers with no awaiting to do simply
    return without awaiting.
    """

    def supports(self, step_type: WorkflowStepType) -> bool: ...

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext: ...


class BaseStepHandler:
    """The one line of shared handler mechanics: a handler declares the
    single step type it serves, and ``supports`` answers the registry's
    "does this handler really serve this step?" check."""

    step_type: WorkflowStepType

    def supports(self, step_type: WorkflowStepType) -> bool:
        return step_type is self.step_type
