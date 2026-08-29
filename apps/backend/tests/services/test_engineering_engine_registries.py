from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.engineering_engine.engineering_engine_exceptions import (
    DuplicateWorkflowRegistrationError,
    StepHandlerNotRegisteredError,
    WorkflowNotRegisteredError,
)
from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailureCode,
    WorkflowStepType,
)
from app.domain.engineering_engine.workflow_definitions import (
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_engine.workflow_planner import build_plan
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.services.engineering_engine.composition import (
    build_step_handler_registry,
    build_workflow_registry,
)
from app.services.engineering_engine.step_handler_registry import (
    StepHandlerRegistry,
)
from app.services.engineering_engine.step_handlers import (
    ValidateExecutionRequestStepHandler,
)
from app.services.engineering_engine.workflow_registry import WorkflowRegistry
from tests.services._engineering_engine_support import (
    FakeGovernedKnowledgeReader,
    execution_request,
    no_op_sleeper,
    provider_registry,
    runtime_configuration,
)

# --- WorkflowRegistry ------------------------------------------------------


# Deliberately spelled out rather than read from the registry: this is
# the one place that asserts *which* workflows exist, so adding one must
# be a visible, reviewed edit here.
REGISTERED_INTENT_TYPES = (
    EngineeringIntentType.DOCUMENT_LOOKUP,
    EngineeringIntentType.ENGINEERING_COMPARISON,
    EngineeringIntentType.ENGINEERING_EXPLANATION,
    EngineeringIntentType.KNOWLEDGE_QUERY,
    EngineeringIntentType.VERIFICATION_REQUEST,
)


def test_the_composed_registry_registers_exactly_the_known_workflows() -> None:
    registry = build_workflow_registry()

    assert registry.registered_intent_types() == REGISTERED_INTENT_TYPES


def test_resolving_a_registered_workflow_returns_its_definition() -> None:
    registry = build_workflow_registry()

    definition = registry.resolve(EngineeringIntentType.KNOWLEDGE_QUERY)

    assert definition is KNOWLEDGE_QUERY_WORKFLOW


def test_resolving_an_unregistered_workflow_raises() -> None:
    registry = build_workflow_registry()

    with pytest.raises(WorkflowNotRegisteredError):
        registry.resolve(EngineeringIntentType.DRAWING_REQUEST)


def test_duplicate_registration_is_rejected() -> None:
    registry = WorkflowRegistry()
    registry.register(KNOWLEDGE_QUERY_WORKFLOW)

    with pytest.raises(DuplicateWorkflowRegistrationError):
        registry.register(KNOWLEDGE_QUERY_WORKFLOW)


def test_a_frozen_registry_refuses_further_registration() -> None:
    registry = build_workflow_registry()

    other = replace(
        KNOWLEDGE_QUERY_WORKFLOW,
        supported_intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
    )
    with pytest.raises(RuntimeError):
        registry.register(other)


def test_selecting_a_registered_workflow_succeeds() -> None:
    registry = build_workflow_registry()

    result = registry.select_workflow(EngineeringIntentType.KNOWLEDGE_QUERY)

    assert result.selected is True
    assert result.failure is None
    assert result.selection.workflow_id.value == "knowledge-query"


@pytest.mark.parametrize(
    "intent_type",
    [
        intent
        for intent in EngineeringIntentType
        if intent not in REGISTERED_INTENT_TYPES
    ],
)
def test_selecting_an_unregistered_workflow_yields_a_typed_failure(
    intent_type: EngineeringIntentType,
) -> None:
    registry = build_workflow_registry()

    result = registry.select_workflow(intent_type)

    assert result.selected is False
    assert result.selection is None
    assert result.failure.code is (
        EngineeringEngineFailureCode.UNSUPPORTED_INTENT
    )


def test_registered_intent_types_are_deterministically_ordered() -> None:
    registry = WorkflowRegistry()
    registry.register(
        replace(
            KNOWLEDGE_QUERY_WORKFLOW,
            supported_intent_type=EngineeringIntentType.NAVIGATION_REQUEST,
        )
    )
    registry.register(KNOWLEDGE_QUERY_WORKFLOW)

    assert registry.registered_intent_types() == (
        EngineeringIntentType.KNOWLEDGE_QUERY,
        EngineeringIntentType.NAVIGATION_REQUEST,
    )


# --- StepHandlerRegistry ----------------------------------------------------


def _handler_registry() -> StepHandlerRegistry:
    return build_step_handler_registry(
        governed_knowledge_reader=FakeGovernedKnowledgeReader(),
        provider_registry=provider_registry(),
        runtime_configuration=runtime_configuration(),
        credential_present=True,
        credential_environment_variable_name="FAKE_API_KEY",
        sleeper=no_op_sleeper,
    )


def test_the_composed_handler_registry_covers_every_knowledge_query_step() -> (
    None
):
    registry = _handler_registry()
    plan = build_plan(
        definition=KNOWLEDGE_QUERY_WORKFLOW, request=execution_request()
    )

    assert registry.missing_handlers(plan) == ()


def test_resolving_an_unregistered_handler_raises() -> None:
    registry = StepHandlerRegistry()

    with pytest.raises(StepHandlerNotRegisteredError):
        registry.resolve(WorkflowStepType.BUILD_PROMPT)


def test_missing_handlers_are_reported_before_execution() -> None:
    registry = StepHandlerRegistry()
    registry.register(
        WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
        ValidateExecutionRequestStepHandler(),
    )
    plan = build_plan(
        definition=KNOWLEDGE_QUERY_WORKFLOW, request=execution_request()
    )

    missing = registry.missing_handlers(plan)

    assert WorkflowStepType.BUILD_PROMPT in missing
    assert WorkflowStepType.VALIDATE_EXECUTION_REQUEST not in missing


def test_duplicate_handler_registration_is_rejected() -> None:
    registry = StepHandlerRegistry()
    registry.register(
        WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
        ValidateExecutionRequestStepHandler(),
    )

    with pytest.raises(RuntimeError):
        registry.register(
            WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
            ValidateExecutionRequestStepHandler(),
        )


def test_registering_a_handler_that_does_not_support_the_step_is_rejected() -> (
    None
):
    registry = StepHandlerRegistry()

    with pytest.raises(RuntimeError):
        registry.register(
            WorkflowStepType.BUILD_PROMPT,
            ValidateExecutionRequestStepHandler(),
        )


def test_a_frozen_handler_registry_refuses_further_registration() -> None:
    registry = _handler_registry()

    with pytest.raises(RuntimeError):
        registry.register(
            WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
            ValidateExecutionRequestStepHandler(),
        )
