"""
The Engineering Engine composition root (Milestone 23A).

**All** concrete dependency wiring happens here - never scattered
through engine code. The engine core depends on the two registry
abstractions; this module is the one place that knows which concrete
workflow and which concrete handlers exist.

``build_engineering_engine`` is deliberately parameterized over every
external dependency (the Graph Query repository, the Engineering Index
repository, the document metadata port, the LLM provider registry,
runtime configuration, the sleeper, the clock), so test composition is a
one-line call with fakes and needs no monkeypatching.

Milestone 23B.1 added the DOCUMENT_LOOKUP workflow by changing **only
this file** on the engine side: one ``register`` call for the workflow,
three for its handlers. Milestone 23B.2 added ENGINEERING_EXPLANATION for
even less - one ``register`` call for the workflow and one more for an
already-existing handler class, parameterized with a different Prompt
Builder objective. Milestone 24.1 added ENGINEERING_VERIFICATION for the
same cost again. No engine module that selects, plans, validates or
executes was touched by any of them.
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
    DOCUMENT_LOOKUP_WORKFLOW,
    ENGINEERING_COMPARISON_WORKFLOW,
    ENGINEERING_EXPLANATION_WORKFLOW,
    ENGINEERING_VERIFICATION_WORKFLOW,
    KNOWLEDGE_QUERY_WORKFLOW,
)
from app.domain.engineering_index.document_metadata import (
    DocumentMetadataPort,
)
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.prompt_builder.prompt_builder_models import PromptObjective
from app.services.engineering_engine.comparison_step_handlers import (
    BuildComparisonContextStepHandler,
    BuildComparisonPromptStepHandler,
    BuildComparisonRetrievalRequestsStepHandler,
    ComparisonResponseBuildStepHandler,
    ExecuteLeftRetrievalStepHandler,
    ExecuteRightRetrievalStepHandler,
)
from app.services.engineering_engine.document_lookup_step_handlers import (
    BuildDocumentRetrievalRequestStepHandler,
    DocumentLookupResponseBuildStepHandler,
    ExecuteDocumentRetrievalStepHandler,
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
    """Every registered workflow, and the *only* place the set is
    declared. Adding one is two lines here plus a declarative definition -
    no engine module changes."""

    registry = WorkflowRegistry()
    registry.register(KNOWLEDGE_QUERY_WORKFLOW)
    registry.register(DOCUMENT_LOOKUP_WORKFLOW)
    registry.register(ENGINEERING_EXPLANATION_WORKFLOW)
    registry.register(ENGINEERING_VERIFICATION_WORKFLOW)
    registry.register(ENGINEERING_COMPARISON_WORKFLOW)

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
    engineering_index_repository: EngineeringIndexRepository | None = None,
    document_metadata_port: DocumentMetadataPort | None = None,
) -> StepHandlerRegistry:
    """
    The DOCUMENT_LOOKUP handlers are registered only when both of their
    ports are supplied. A composition that omits them still registers the
    *workflow* - so a document lookup then fails with the existing typed
    ``STEP_HANDLER_NOT_REGISTERED`` failure, before any step runs, rather
    than either pretending the capability exists or silently rerouting the
    request through another workflow.
    """

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
    # One handler class, three registrations: the explanation and
    # verification workflows reuse Prompt Builder through exactly the same
    # handler, asking it for a different objective. Each objective is
    # stated here, declaratively, and never derived inside the handler from
    # an intent or workflow type.
    registry.register(WorkflowStepType.BUILD_PROMPT, BuildPromptStepHandler())
    registry.register(
        WorkflowStepType.BUILD_EXPLANATION_PROMPT,
        BuildPromptStepHandler(
            step_type=WorkflowStepType.BUILD_EXPLANATION_PROMPT,
            objective=PromptObjective.ENGINEERING_EXPLANATION,
        ),
    )
    registry.register(
        WorkflowStepType.BUILD_VERIFICATION_PROMPT,
        BuildPromptStepHandler(
            step_type=WorkflowStepType.BUILD_VERIFICATION_PROMPT,
            objective=PromptObjective.ENGINEERING_VERIFICATION,
        ),
    )
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

    # Engineering comparison (Milestone 24.2). Two retrieval-execution
    # handlers rather than one parameterized instance: the side each
    # serves is fixed by its class, so no code path can read one side's
    # request and write the other's result.
    registry.register(
        WorkflowStepType.BUILD_COMPARISON_RETRIEVAL_REQUESTS,
        BuildComparisonRetrievalRequestsStepHandler(),
    )
    registry.register(
        WorkflowStepType.EXECUTE_LEFT_RETRIEVAL,
        ExecuteLeftRetrievalStepHandler(graph_query_repository),
    )
    registry.register(
        WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL,
        ExecuteRightRetrievalStepHandler(graph_query_repository),
    )
    registry.register(
        WorkflowStepType.BUILD_COMPARISON_CONTEXT,
        BuildComparisonContextStepHandler(),
    )
    registry.register(
        WorkflowStepType.BUILD_COMPARISON_PROMPT,
        BuildComparisonPromptStepHandler(),
    )
    registry.register(
        WorkflowStepType.BUILD_COMPARISON_RESPONSE,
        ComparisonResponseBuildStepHandler(),
    )

    if (
        engineering_index_repository is not None
        and document_metadata_port is not None
    ):
        registry.register(
            WorkflowStepType.BUILD_DOCUMENT_RETRIEVAL_REQUEST,
            BuildDocumentRetrievalRequestStepHandler(),
        )
        registry.register(
            WorkflowStepType.EXECUTE_DOCUMENT_RETRIEVAL,
            ExecuteDocumentRetrievalStepHandler(
                engineering_index_repository, document_metadata_port
            ),
        )
        registry.register(
            WorkflowStepType.BUILD_DOCUMENT_LOOKUP_RESPONSE,
            DocumentLookupResponseBuildStepHandler(),
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
    engineering_index_repository: EngineeringIndexRepository | None = None,
    document_metadata_port: DocumentMetadataPort | None = None,
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
            engineering_index_repository=engineering_index_repository,
            document_metadata_port=document_metadata_port,
        ),
        clock=clock,
    )
