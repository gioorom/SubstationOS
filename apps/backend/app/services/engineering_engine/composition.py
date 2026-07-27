"""
The Engineering Engine composition root (Milestone 23A).

**All** concrete dependency wiring happens here - never scattered
through engine code. The engine core depends on the two registry
abstractions; this module is the one place that knows which concrete
workflow and which concrete handlers exist.

``build_engineering_engine`` is deliberately parameterized over every
external dependency (the Graph Query repository, the LLM provider
registry, runtime configuration, the sleeper, the clock), so test
composition is a one-line call with fakes and needs no monkeypatching.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import datetime

from app.application.models.llm_invocation import LLMRuntimeConfiguration
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.domain.engineering_engine.engineering_engine_models import (
    WorkflowStepType,
)
from app.domain.engineering_engine.workflow_definitions import (
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.services.engineering_engine.engineering_engine_service import (
    EngineeringEngineService,
)
from app.services.engineering_engine.step_handler_registry import (
    StepHandlerRegistry,
)
from app.services.engineering_engine.step_handlers import (
    BuildContextStepHandler,
    BuildPromptStepHandler,
    BuildRetrievalRequestStepHandler,
    EngineeringResponseBuildStepHandler,
    ExecuteRetrievalStepHandler,
    PrepareConversationUpdateStepHandler,
    PrepareSessionUpdateStepHandler,
    RuntimeInvocationStepHandler,
    ValidateEngineeringResponseStepHandler,
    ValidateExecutionRequestStepHandler,
)
from app.services.engineering_engine.workflow_registry import WorkflowRegistry


def build_workflow_registry() -> WorkflowRegistry:
    """Milestone 23A registers exactly one workflow. Milestone 23B adds
    more here - and nowhere else in the engine."""

    registry = WorkflowRegistry()
    registry.register(KNOWLEDGE_QUERY_WORKFLOW)

    return registry.freeze()


def build_step_handler_registry(
    *,
    graph_query_repository,
    provider_registry: LLMProviderRegistry,
    runtime_configuration: LLMRuntimeConfiguration,
    credential_present: bool,
    credential_environment_variable_name: str,
    sleeper=None,
    random_source: random.Random | None = None,
) -> StepHandlerRegistry:
    registry = StepHandlerRegistry()

    registry.register(
        WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
        ValidateExecutionRequestStepHandler(),
    )
    registry.register(
        WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
        BuildRetrievalRequestStepHandler(),
    )
    registry.register(
        WorkflowStepType.EXECUTE_RETRIEVAL,
        ExecuteRetrievalStepHandler(graph_query_repository),
    )
    registry.register(
        WorkflowStepType.BUILD_CONTEXT, BuildContextStepHandler()
    )
    registry.register(WorkflowStepType.BUILD_PROMPT, BuildPromptStepHandler())
    registry.register(
        WorkflowStepType.INVOKE_LLM_RUNTIME,
        RuntimeInvocationStepHandler(
            provider_registry=provider_registry,
            runtime_configuration=runtime_configuration,
            credential_present=credential_present,
            credential_environment_variable_name=(
                credential_environment_variable_name
            ),
            sleeper=sleeper or asyncio.sleep,
            random_source=random_source,
        ),
    )
    registry.register(
        WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
        EngineeringResponseBuildStepHandler(),
    )
    registry.register(
        WorkflowStepType.VALIDATE_ENGINEERING_RESPONSE,
        ValidateEngineeringResponseStepHandler(),
    )
    registry.register(
        WorkflowStepType.PREPARE_CONVERSATION_UPDATE,
        PrepareConversationUpdateStepHandler(),
    )
    registry.register(
        WorkflowStepType.PREPARE_SESSION_UPDATE,
        PrepareSessionUpdateStepHandler(),
    )

    return registry.freeze()


def build_engineering_engine(
    *,
    graph_query_repository,
    provider_registry: LLMProviderRegistry,
    runtime_configuration: LLMRuntimeConfiguration,
    credential_present: bool,
    credential_environment_variable_name: str,
    clock: Callable[[], datetime],
    sleeper=None,
    random_source: random.Random | None = None,
) -> EngineeringEngineService:
    return EngineeringEngineService(
        workflow_registry=build_workflow_registry(),
        step_handler_registry=build_step_handler_registry(
            graph_query_repository=graph_query_repository,
            provider_registry=provider_registry,
            runtime_configuration=runtime_configuration,
            credential_present=credential_present,
            credential_environment_variable_name=(
                credential_environment_variable_name
            ),
            sleeper=sleeper,
            random_source=random_source,
        ),
        clock=clock,
    )
