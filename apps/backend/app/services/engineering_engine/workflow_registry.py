"""
The Workflow Registry (Milestone 23A) - the **only** place that maps an
``EngineeringIntentType`` to a workflow.

This is what replaces core intent branching: the engine core never
contains ``if intent is KNOWLEDGE_QUERY ... elif intent is
DOCUMENT_LOOKUP ...``. It asks the registry to resolve a workflow and
gets either a definition or a typed "not registered" failure. Milestone
23B.1 added the DOCUMENT_LOOKUP workflow by *registering* it in the
composition root - this module was not changed to accommodate it, and
neither was any other engine module (see ADR-0020).

The unsupported-intent message names whichever intent types are actually
registered, read from the registry itself, so it can never drift out of
date as workflows are added.

Immutable after construction: ``register`` is only callable during
composition, and ``freeze()`` returns a registry that refuses further
registration.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_exceptions import (
    DuplicateWorkflowRegistrationError,
    WorkflowNotRegisteredError,
)
from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailure,
    EngineeringEngineFailureCode,
    WorkflowDefinition,
    WorkflowSelection,
    WorkflowSelectionResult,
)
from app.domain.engineering_engine.engineering_engine_policy import (
    WORKFLOW_REGISTRY_VERSION,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)


class WorkflowRegistry:
    """An explicit ``EngineeringIntentType -> WorkflowDefinition`` map.
    The mapping is encapsulated here; no consumer branches over intent
    types itself."""

    def __init__(self) -> None:
        self._definitions: dict[EngineeringIntentType, WorkflowDefinition] = {}
        self._frozen = False

    @property
    def registry_version(self) -> str:
        return WORKFLOW_REGISTRY_VERSION

    def register(self, definition: WorkflowDefinition) -> None:
        if self._frozen:
            raise RuntimeError(
                "This WorkflowRegistry is frozen and accepts no further "
                "registrations."
            )

        intent_type = definition.supported_intent_type
        if intent_type in self._definitions:
            raise DuplicateWorkflowRegistrationError(intent_type.value)

        self._definitions[intent_type] = definition

    def freeze(self) -> "WorkflowRegistry":
        self._frozen = True
        return self

    def is_registered(self, intent_type: EngineeringIntentType) -> bool:
        return intent_type in self._definitions

    def registered_intent_types(self) -> tuple[EngineeringIntentType, ...]:
        """Deterministically ordered by intent-type value, so registry
        metadata never depends on registration order."""

        return tuple(
            sorted(self._definitions, key=lambda intent: intent.value)
        )

    def registered_definitions(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(
            self._definitions[intent_type]
            for intent_type in self.registered_intent_types()
        )

    def resolve(
        self, intent_type: EngineeringIntentType
    ) -> WorkflowDefinition:
        """Raises ``WorkflowNotRegisteredError`` when nothing is
        registered - callers wanting a typed result instead should use
        ``select_workflow``."""

        definition = self._definitions.get(intent_type)
        if definition is None:
            raise WorkflowNotRegisteredError(intent_type.value)

        return definition

    def select_workflow(
        self, intent_type: EngineeringIntentType
    ) -> WorkflowSelectionResult:
        """
        The registry-driven selection the engine core uses. An intent
        with no registered workflow yields an explicit
        ``UNSUPPORTED_INTENT`` failure - never a silent reroute through
        another workflow, and never an LLM fallback.
        """

        definition = self._definitions.get(intent_type)

        if definition is None:
            supported = ", ".join(
                registered.value
                for registered in self.registered_intent_types()
            )

            return WorkflowSelectionResult(
                selected=False,
                failure=EngineeringEngineFailure(
                    code=EngineeringEngineFailureCode.UNSUPPORTED_INTENT,
                    message=(
                        f"No workflow is registered for intent type "
                        f"'{intent_type.value}'. Registered intent types: "
                        f"{supported or 'none'}."
                    ),
                ),
            )

        return WorkflowSelectionResult(
            selected=True,
            selection=WorkflowSelection(
                workflow_id=definition.workflow_id,
                workflow_type=definition.workflow_type,
                workflow_version=definition.workflow_version,
                intent_type=intent_type,
            ),
        )
