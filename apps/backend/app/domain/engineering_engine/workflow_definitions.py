"""
Declarative workflow definitions (Milestone 23A). A definition
describes *what steps a workflow has*, in order, with the capability
each requires and the artifacts each consumes and produces - it never
invokes a service. The planner
(``workflow_planner.py``) turns a definition plus an execution request
into an immutable ``WorkflowPlan``; step handlers (application layer)
do the actual work.

Milestone 23A defined one workflow; Milestone 23B.1 added
``DOCUMENT_LOOKUP_WORKFLOW`` here and registered it in the composition
root - and nothing in the engine core changed to accommodate it. That is
the whole point of this module: workflows are **data**, added by
declaring and **registering** them, never by editing the engine.
"""

from __future__ import annotations

from dataclasses import replace

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

ENGINEERING_EXPLANATION_WORKFLOW_ID = "engineering-explanation"
ENGINEERING_EXPLANATION_WORKFLOW_VERSION = "1.0"

# The second LLM-powered workflow. Its pipeline is deliberately the
# *same* pipeline as KNOWLEDGE_QUERY - same retrieval, same context
# building, same runtime, same response building - differing in exactly
# one step: it asks Prompt Builder for the ENGINEERING_EXPLANATION
# objective instead of DIRECT_ANSWER.
#
# That is the whole difference, and it is deliberate. "Spiegami il
# funzionamento della protezione 87T" and "quale TA è installato sul
# montante T2?" need the same governed graph evidence; what differs is
# what the engineer wants done with it. Modelling that as a different
# retrieval strategy, a different context budget or a second response
# builder would invent distinctions the domain does not have.
ENGINEERING_EXPLANATION_WORKFLOW = WorkflowDefinition(
    workflow_id=WorkflowId(value=ENGINEERING_EXPLANATION_WORKFLOW_ID),
    workflow_type=WorkflowType.ENGINEERING_EXPLANATION,
    supported_intent_type=EngineeringIntentType.ENGINEERING_EXPLANATION,
    workflow_version=ENGINEERING_EXPLANATION_WORKFLOW_VERSION,
    description=(
        "Explains retrieved engineering knowledge - 'spiegami il "
        "funzionamento della protezione 87T', 'descrivi lo schema "
        "funzionale del trasformatore T1' - through the same Structured "
        "Retrieval, Context Builder, provider-neutral LLM Runtime and "
        "Engineering Response pipeline the knowledge-query workflow "
        "uses, asking Prompt Builder for its explanation objective "
        "rather than a direct answer."
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
        # The one step that differs from KNOWLEDGE_QUERY.
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_EXPLANATION_PROMPT,
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

ENGINEERING_VERIFICATION_WORKFLOW_ID = "engineering-verification"
#: 2.0: EPIC 32.1 added the deterministic reasoning step.
ENGINEERING_VERIFICATION_WORKFLOW_VERSION = "2.0"

# The first workflow that **evaluates** rather than presents: it decides
# whether the project's own evidence supports a statement.
#
# Its pipeline is again the knowledge-query pipeline, differing in one
# step - the prompt objective. That is not a shortcut; it is the finding.
# "Verify that transformer T1 has differential protection" needs exactly
# the same governed graph evidence as asking what T1 is protected by. What
# differs is what the engineer wants done with it, and *that* belongs in
# the prompt (Prompt Builder) and in reading the result back
# (Engineering Response) - not in a second retrieval strategy, a second
# context budget, or engine logic.
#
# Note the intent type: this system's classifier has published
# ``VERIFICATION_REQUEST`` since Milestone 22, and an intent-type value is
# a contract (CLAUDE.md §16). The workflow, workflow type and prompt
# objective are named "engineering verification"; the intent it serves
# keeps its published name.
ENGINEERING_VERIFICATION_WORKFLOW = WorkflowDefinition(
    workflow_id=WorkflowId(value=ENGINEERING_VERIFICATION_WORKFLOW_ID),
    workflow_type=WorkflowType.ENGINEERING_VERIFICATION,
    supported_intent_type=EngineeringIntentType.VERIFICATION_REQUEST,
    workflow_version=ENGINEERING_VERIFICATION_WORKFLOW_VERSION,
    description=(
        "Evaluates whether the project's retrieved evidence supports a "
        "specific engineering statement - 'verify that protection 87T is "
        "present', 'check whether cable C-295 is connected to TA-12' - "
        "through the same Structured Retrieval, Context Builder, "
        "provider-neutral LLM Runtime and Engineering Response pipeline "
        "the knowledge-query workflow uses, asking Prompt Builder for its "
        "verification objective. The outcome vocabulary is Prompt "
        "Builder's and Engineering Response's, never this definition's - "
        "the engine coordinates the workflow and evaluates nothing."
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
        # EPIC 32.1: deterministic reasoning, **before** the prompt.
        #
        # The verification workflow is where it belongs, and that is a
        # repository finding rather than a convenience: this system's
        # classifier has routed "incoerenza", "coerente", "inconsistency"
        # to VERIFICATION_REQUEST since Milestone 22. A second intent
        # owning the same vocabulary would make a deterministic
        # classifier ambiguous, so the deterministic rule joins the
        # workflow the words already reach.
        #
        # It runs before the prompt so the model is *told* what the
        # governed knowledge does, rather than asked to work it out.
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_ENGINEERING_REASONING,
            required_capability=WorkflowCapability.ENGINEERING_REASONING,
            required_artifacts=(WorkflowArtifactKey.CONTEXT_PACKAGE,),
            produced_artifacts=(WorkflowArtifactKey.REASONING_RESULT,),
        ),
        # The step that differs from KNOWLEDGE_QUERY.
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_VERIFICATION_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(
                WorkflowArtifactKey.CONTEXT_PACKAGE,
                WorkflowArtifactKey.REASONING_RESULT,
            ),
            produced_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.INVOKE_LLM_RUNTIME,
            required_capability=WorkflowCapability.LLM_RUNTIME_INVOCATION,
            required_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
            produced_artifacts=(WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,),
        ),
        # Reused unchanged. The verdict is read here, by Engineering
        # Response, from the prompt objective the package already carries -
        # so this step needed no new type and no new handler.
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_ENGINEERING_RESPONSE,
            required_capability=(
                WorkflowCapability.ENGINEERING_RESPONSE_BUILDING
            ),
            required_artifacts=(
                WorkflowArtifactKey.CONTEXT_PACKAGE,
                WorkflowArtifactKey.PROMPT_PACKAGE,
                WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,
                # EPIC 32.1: this workflow reasons, so its response
                # must carry the conclusion. Declared here so a
                # future edit that drops the reasoning step fails
                # the plan rather than quietly answering without it.
                WorkflowArtifactKey.REASONING_RESULT,
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
        WorkflowCapability.ENGINEERING_REASONING,
        WorkflowCapability.PROMPT_BUILDING,
        WorkflowCapability.LLM_RUNTIME_INVOCATION,
        WorkflowCapability.ENGINEERING_RESPONSE_BUILDING,
        WorkflowCapability.AGGREGATE_UPDATE_PREPARATION,
    ),
)

ENGINEERING_COMPARISON_WORKFLOW_ID = "engineering-comparison"
ENGINEERING_COMPARISON_WORKFLOW_VERSION = "1.0"

# The first workflow with **two subjects**, and the first whose pipeline
# genuinely differs rather than only its prompt.
#
# Two retrievals run independently and their results stay distinct
# artifacts from retrieval through context, prompt and response. Nothing
# merges them: a comparison whose evidence has been flattened cannot say
# which side a finding came from, and a finding reported in the wrong
# direction is an error rather than a wording choice. What the two sides
# mean is decided outside the engine entirely.
#
# Retrieval is deliberately two steps rather than one. Building both
# operands' requests is pure, and an invalid operand set is an invalid
# *request* whichever side it came from - so that is one step. Executing
# them is two, so a failure is attributed to the side that actually
# failed; one combined step would report a left failure and a right
# failure identically, and an engineer needs those told apart.
ENGINEERING_COMPARISON_WORKFLOW = WorkflowDefinition(
    workflow_id=WorkflowId(value=ENGINEERING_COMPARISON_WORKFLOW_ID),
    workflow_type=WorkflowType.ENGINEERING_COMPARISON,
    supported_intent_type=EngineeringIntentType.ENGINEERING_COMPARISON,
    workflow_version=ENGINEERING_COMPARISON_WORKFLOW_VERSION,
    description=(
        "Compares two explicitly named engineering subjects - 'confronta "
        "il trasformatore T1 con T2', 'quali differenze ci sono tra il "
        "montante M1 e M2?' - by retrieving each side's evidence "
        "independently through Structured Retrieval, assembling a "
        "two-sided context that never merges them, and asking Prompt "
        "Builder for its comparison objective. It compares the two sides "
        "against each other only, never against general engineering "
        "knowledge."
    ),
    steps=(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
            required_capability=WorkflowCapability.REQUEST_VALIDATION,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
        WorkflowStepDefinition(
            step_type=(
                WorkflowStepType.BUILD_COMPARISON_RETRIEVAL_REQUESTS
            ),
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(
                WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST,
                WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST,
            ),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_LEFT_RETRIEVAL,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST,),
            produced_artifacts=(WorkflowArtifactKey.LEFT_RETRIEVAL_RESULT,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL,
            required_capability=WorkflowCapability.STRUCTURED_RETRIEVAL,
            required_artifacts=(
                WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST,
            ),
            produced_artifacts=(WorkflowArtifactKey.RIGHT_RETRIEVAL_RESULT,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_COMPARISON_CONTEXT,
            required_capability=WorkflowCapability.CONTEXT_BUILDING,
            required_artifacts=(
                WorkflowArtifactKey.LEFT_RETRIEVAL_RESULT,
                WorkflowArtifactKey.RIGHT_RETRIEVAL_RESULT,
            ),
            produced_artifacts=(WorkflowArtifactKey.COMPARISON_CONTEXT,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_COMPARISON_PROMPT,
            required_capability=WorkflowCapability.PROMPT_BUILDING,
            required_artifacts=(WorkflowArtifactKey.COMPARISON_CONTEXT,),
            produced_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.INVOKE_LLM_RUNTIME,
            required_capability=WorkflowCapability.LLM_RUNTIME_INVOCATION,
            required_artifacts=(WorkflowArtifactKey.PROMPT_PACKAGE,),
            produced_artifacts=(WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_COMPARISON_RESPONSE,
            required_capability=(
                WorkflowCapability.ENGINEERING_RESPONSE_BUILDING
            ),
            required_artifacts=(
                WorkflowArtifactKey.COMPARISON_CONTEXT,
                WorkflowArtifactKey.PROMPT_PACKAGE,
                WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE,
            ),
            produced_artifacts=(
                WorkflowArtifactKey.ENGINEERING_RESPONSE,
                WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            ),
        ),
        # The terminal three are the same step types, served by the same
        # registered handlers, as every other workflow's.
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

DOCUMENT_LOOKUP_WORKFLOW_ID = "document-lookup"
DOCUMENT_LOOKUP_WORKFLOW_VERSION = "1.0"

# The first workflow in this system that answers an engineering request
# **without any LLM**. It stops where the retrieved data already answers
# the question: there is deliberately no Context Builder step, no Prompt
# Builder step and no runtime step, because "which documents mention
# 87T?" is answered by the documents themselves. Summarizing them would
# be a different question, and answering it would require reading their
# contents - which this workflow does not do.
DOCUMENT_LOOKUP_WORKFLOW = WorkflowDefinition(
    workflow_id=WorkflowId(value=DOCUMENT_LOOKUP_WORKFLOW_ID),
    workflow_type=WorkflowType.DOCUMENT_LOOKUP,
    supported_intent_type=EngineeringIntentType.DOCUMENT_LOOKUP,
    workflow_version=DOCUMENT_LOOKUP_WORKFLOW_VERSION,
    description=(
        "Answers a classified DOCUMENT_LOOKUP request - 'trova il "
        "documento del montante T2', 'quali documenti parlano della "
        "protezione 87T?' - by reading the project's Engineering Index "
        "for documents whose recorded mentions match the requested "
        "engineering designations, and returning them as structured "
        "document references. Invokes no LLM, builds no prompt, and never "
        "reads a document's contents."
    ),
    steps=(
        WorkflowStepDefinition(
            step_type=WorkflowStepType.VALIDATE_EXECUTION_REQUEST,
            required_capability=WorkflowCapability.REQUEST_VALIDATION,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_DOCUMENT_RETRIEVAL_REQUEST,
            required_capability=WorkflowCapability.DOCUMENT_RETRIEVAL,
            required_artifacts=(WorkflowArtifactKey.EXECUTION_REQUEST,),
            produced_artifacts=(
                WorkflowArtifactKey.DOCUMENT_RETRIEVAL_REQUEST,
            ),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.EXECUTE_DOCUMENT_RETRIEVAL,
            required_capability=WorkflowCapability.DOCUMENT_RETRIEVAL,
            required_artifacts=(
                WorkflowArtifactKey.DOCUMENT_RETRIEVAL_REQUEST,
            ),
            produced_artifacts=(
                WorkflowArtifactKey.DOCUMENT_RETRIEVAL_RESULT,
            ),
        ),
        WorkflowStepDefinition(
            step_type=WorkflowStepType.BUILD_DOCUMENT_LOOKUP_RESPONSE,
            required_capability=(
                WorkflowCapability.ENGINEERING_RESPONSE_BUILDING
            ),
            required_artifacts=(
                WorkflowArtifactKey.DOCUMENT_RETRIEVAL_RESULT,
            ),
            produced_artifacts=(
                WorkflowArtifactKey.ENGINEERING_RESPONSE,
                WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            ),
        ),
        # The remaining three steps are the *same* step types, and are
        # served by the *same* registered handlers, as the knowledge-query
        # workflow's - reused unchanged rather than duplicated.
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
        WorkflowCapability.DOCUMENT_RETRIEVAL,
        WorkflowCapability.ENGINEERING_RESPONSE_BUILDING,
        WorkflowCapability.AGGREGATE_UPDATE_PREPARATION,
    ),
)


# --- Structural relationship (EPIC 32.2) ---------------------------------

STRUCTURAL_RELATIONSHIP_WORKFLOW_ID = "structural-relationship"

STRUCTURAL_RELATIONSHIP_WORKFLOW_VERSION = "1.0"

#: "Are these two governed assets in the same structural location?"
#:
#: **The verification pipeline, step for step**, and built from it with
#: `replace` rather than copied: the two definitions cannot drift, and a
#: reader can see at a glance that this workflow introduced no new
#: machinery. Validate, retrieve, assemble context, reason, prompt,
#: invoke, respond - the same steps in the same order, under the same
#: capabilities.
#:
#: What differs is not the pipeline but the question. The reasoning step
#: dispatches on the request's intent type, so this workflow reaches the
#: shared-structural-location rule where the verification workflow
#: reaches quantity consistency. Nothing else needed to change, which is
#: the point: a second reasoning family cost a workflow definition and a
#: branch, not a subsystem.
STRUCTURAL_RELATIONSHIP_WORKFLOW = replace(
    ENGINEERING_VERIFICATION_WORKFLOW,
    workflow_id=WorkflowId(value=STRUCTURAL_RELATIONSHIP_WORKFLOW_ID),
    workflow_type=WorkflowType.STRUCTURAL_RELATIONSHIP,
    supported_intent_type=(
        EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
    ),
    workflow_version=STRUCTURAL_RELATIONSHIP_WORKFLOW_VERSION,
    description=(
        "Determines whether governed knowledge establishes that two "
        "engineering assets stand in the same governed structural "
        "location - 'are +E01-QA1 and +E01-QB1 in the same location?'. "
        "The answer is computed deterministically by a versioned "
        "reasoning rule over the assembled governed context, before any "
        "model is invoked; the model communicates a conclusion it did "
        "not reach. The conclusion is a derived inference, never governed "
        "knowledge, and it says only that the two assets share a "
        "location context - never that they are connected, adjacent, on "
        "one circuit, or in any particular kind of place."
    ),
)
