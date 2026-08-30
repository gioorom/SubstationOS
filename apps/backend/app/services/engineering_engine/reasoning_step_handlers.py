"""
The Engineering Engine's deterministic reasoning step (EPIC 32.1).

Like every other handler, this one reimplements nothing: it derives the
typed reasoning question from the execution request, delegates to the
reasoning service, and maps the result into the typed execution context.

---

## Why the question is derived here and not classified

The reasoning query is **typed**, never free text. Its subject is the
designation the Retrieval Bridge already resolved onto the execution
request - the same designation retrieval matched on - so the question
reasoning answers is always about the equipment the engine actually
retrieved. Deriving it from the request text instead would let reasoning
answer about something the context does not contain.

The quantity kind is not derived at all: governed semantics produces one
relationship kind, so there is one question to ask. The day a second
governed quantity kind exists, choosing between them becomes a real
decision and belongs in a rule, not in this handler.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.engineering_reasoning.reasoning_models import (
    QuantityConsistencyQuery,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.services import engineering_reasoning_service
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.governed_retrieval_step_handlers import (
    designation_of,
)
from app.services.engineering_engine.step_handler import (
    BaseStepHandler,
    StepHandlerError,
)

#: The one governed quantity kind. Stated as a constant so the day a
#: second exists, this line is where the choice becomes visible.
REASONED_QUANTITY_KIND = GraphEdgeKind.HAS_RATED_POWER


def subject_designation_of(request) -> str:
    """
    The designation reasoning asks about.

    The same one retrieval resolved: a canonical entity reference if the
    bridge produced one, otherwise the first lexical designation the
    request named. Empty when the request named none - and the rule then
    concludes `INSUFFICIENT_KNOWLEDGE`, which is the honest answer to a
    question that named no subject.
    """

    if request.retrieval_canonical_entity_id:
        return designation_of(request.retrieval_canonical_entity_id)

    for term in request.retrieval_lexical_terms:
        if term.strip():
            return term

    return ""


class ExecuteEngineeringReasoningStepHandler(BaseStepHandler):
    """
    Runs deterministic reasoning over the assembled governed context.

    Holds **no dependency at all** - no repository, no session, no
    provider - because the reasoning service needs none. That absence is
    the boundary: this step cannot reach knowledge the context does not
    already carry.
    """

    step_type = WorkflowStepType.EXECUTE_ENGINEERING_REASONING

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request

        query = QuantityConsistencyQuery(
            subject_designation=subject_designation_of(request),
            quantity_kind=REASONED_QUANTITY_KIND,
            project_id=request.project_id,
        )

        try:
            result = engineering_reasoning_service.evaluate_quantity_consistency(
                context.context_package, query, now=request.executed_at
            )
        except ValueError as error:  # pragma: no cover - defensive
            raise StepHandlerError(
                EngineeringEngineFailureCode.CONTEXT_BUILD_FAILURE,
                "Deterministic engineering reasoning failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.REASONING_RESULT, result
        )
