"""
The Step Handler Registry (Milestone 23A) - maps a
``WorkflowStepType`` to the one handler that executes it.

Like the Workflow Registry, this is what keeps the engine core free of
branching: the executor asks the registry for a handler and gets one or
a typed "not registered" failure. It also lets a plan be checked for
handler availability *before* execution starts, so a missing dependency
fails at validation rather than halfway through a workflow.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_exceptions import (
    StepHandlerNotRegisteredError,
)
from app.domain.engineering_engine.engineering_engine_models import (
    WorkflowPlan,
    WorkflowStepType,
)
from app.services.engineering_engine.step_handler import WorkflowStepHandler


class StepHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[WorkflowStepType, WorkflowStepHandler] = {}
        self._frozen = False

    def register(
        self, step_type: WorkflowStepType, handler: WorkflowStepHandler
    ) -> None:
        if self._frozen:
            raise RuntimeError(
                "This StepHandlerRegistry is frozen and accepts no further "
                "registrations."
            )
        if step_type in self._handlers:
            raise RuntimeError(
                f"A handler is already registered for step type "
                f"'{step_type.value}'."
            )
        if not handler.supports(step_type):
            raise RuntimeError(
                f"The supplied handler does not support step type "
                f"'{step_type.value}'."
            )

        self._handlers[step_type] = handler

    def freeze(self) -> "StepHandlerRegistry":
        self._frozen = True
        return self

    def is_registered(self, step_type: WorkflowStepType) -> bool:
        return step_type in self._handlers

    def resolve(self, step_type: WorkflowStepType) -> WorkflowStepHandler:
        handler = self._handlers.get(step_type)
        if handler is None:
            raise StepHandlerNotRegisteredError(step_type.value)

        return handler

    def missing_handlers(
        self, plan: WorkflowPlan
    ) -> tuple[WorkflowStepType, ...]:
        """Every step type in the plan with no registered handler -
        checked before execution begins."""

        return tuple(
            step.step_type
            for step in plan.steps
            if step.step_type not in self._handlers
        )
