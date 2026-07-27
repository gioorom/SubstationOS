"""
Declarative workflow definitions (Milestone 23A). A definition
describes *what steps a workflow has*, in order, with the capability
each requires and the artifacts each consumes and produces - it never
invokes a service. The planner
(``workflow_planner.py``) turns a definition plus an execution request
into an immutable ``WorkflowPlan``; step handlers (application layer)
do the actual work.

Milestone 23A defines exactly one workflow. Milestone 23B adds more by
defining and **registering** them - never by editing the engine core.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    WorkflowArtifactKey,
    WorkflowCapability,
    WorkflowDefinition,
    WorkflowId,
    WorkflowStepDefinition,
    WorkflowStepType,
    WorkflowType,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)

KNOWLEDGE_QUERY_WORKFLOW_ID = "knowledge-query"
KNOWLEDGE_QUERY_WORKFLOW_VERSION = "1.0"

# The real pipeline, step by step. Note the deliberate absence of a
# separate graph-query step: Structured Retrieval already reads through
# GraphQueryRepository internally, so modelling it here would duplicate
# it artificially (Milestone 23A's own instruction).
KNOWLEDGE_QUERY_WORKFLOW = WorkflowDefinition(
    workflow_id=WorkflowId(value=KNOWLEDGE_QUERY_WORKFLOW_ID),
    workflow_type=WorkflowType.KNOWLEDGE_QUERY,
    supported_intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
    workflow_version=KNOWLEDGE_QUERY_WORKFLOW_VERSION,
    description=(
        "Answers a classified KNOWLEDGE_QUERY request from governed "
        "project graph state, through Structured Retrieval, Context "
        "Builder, Prompt Builder, the provider-neutral LLM Runtime, and "
        "the Engineering Response builder."
    ),
    steps=(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
            required_capability=WorkflowCapability.REQUEST_VALIDATION,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_RETRIEVAL_REQUEST,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.RETRIEVAL_REQUEST,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_RETRIEVAL,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.RETRIEVAL_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.RETRIEVAL_RESULT,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_CONTEXT,
            required_capability=WorkflowCapability.CONTEXT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.RETRIEVAL_RESULT,),
            produced_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
            produced_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.INVOKE_LLM_RUNTIME,
            required_capability=WorkflowCapability.LLM_RUNTIME_INVOCATION,
            required_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
            produced_artifacts=(WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
            required_capability=(
                WorkflowCapability.ENGINEERING_RESPONSE_BUILDING
            ),
            required_artifacts=(
                WorkflowArtifactKey.CONTEXT_PACKAGE,
                WorkflowArtifactKey.PROMPT_PACKAGE,
                WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,
            ),
            produced_artifacts=(
                WorkflowArtifactKey.ENGINEERING_RESPONSE,
                WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            ),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.VALIDATE_ENGINEERING_RESPONSE,
            required_capability=(
                WorkflowCapability.ENGINEERING_RESPONSE_BUILDING
            ),
            required_artifacts=(
                WorkflowArtifactKey.ENGINEERING_RESPONSE,
                WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            ),
            produced_artifacts=(),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.PREPARE_CONVERSATION_UPDATE,
            required_capability=(
                WorkflowCapability.AGGREGATE_UPDATE_PREPARATION
            ),
            required_artifacts=(WorkflowArtifactKey.ENGINEERING_RESPONSE,),
            produced_artifacts=(
                WorkflowArtifactKey.CONVERSATION_UPDATE_PROPOSAL,
            ),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.PREPARE_SESSION_UPDATE,
            required_capability=(
                WorkflowCapability.AGGREGATE_UPDATE_PREPARATION
            ),
            required_artifacts=(WorkflowArtifactKey.ENGINEERING_RESPONSE,),
            produced_artifacts=(WorkflowArtifactKey.SESSION_UPDATE_PROPOSAL,),
        ),
    ),
    required_capabilities=(
        WorkflowCapability.REQUEST_VALIDATION,
        WorkflowCapability.STRUCTURED_RETRIEVAL,
        WorkflowCapability.CONTEXT_BUILDING,
        WorkflowCapability.PROMPT_BUILDING,
        WorkflowCapability.LLM_RUNTIME_INVOCATION,
        WorkflowCapability.ENGINEERING_RESPONSE_BUILDING,
        WorkflowCapability.AGGREGATE_UPDATE_PREPARATION,
    ),
)
