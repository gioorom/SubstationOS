"""
The Engineering Engine's deterministic reasoning step
(EPIC 32.1, extended by EPIC 32.2).

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

## Two reasoning families, one step (EPIC 32.2)

There is **one** reasoning step and **one** handler. It chooses between
the two rules on `request.intent_type` - a typed field the request
already carries, decided upstream by the intent classifier and recorded
on the workflow definition that was selected.

Deliberately not a registry, a rule table or a plugin lookup. Two rules
are two branches; a registry would be indirection whose only effect is
that nobody can tell from this file which rules exist. The day there are
five, this is still readable, and the day it is not, the refactor is
visible rather than pre-emptive.

The dispatch is on **intent**, not on the shape of the request. A step
that inferred "two designations means the structural question" would
answer a different question than the engineer asked whenever a
verification request happened to mention two pieces of equipment.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.engineering_reasoning.reasoning_exceptions import (
    EngineeringReasoningError,
    SameAssetComparisonError,
)
from app.domain.engineering_reasoning.reasoning_models import (
    QuantityConsistencyQuery,
    SharedStructuralLocationQuery,
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
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedResultKind,
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


def subject_designations_of(request) -> tuple[str, ...]:
    """
    Every designation the request names, in a fixed order, without
    duplicates.

    The same designations retrieval resolved, read from the same fields
    in the same order, so the question reasoning answers is always about
    equipment the engine actually retrieved.
    """

    named: list[str] = []

    if request.retrieval_canonical_entity_id:
        named.append(designation_of(request.retrieval_canonical_entity_id))

    named.extend(
        term for term in request.retrieval_lexical_terms if term.strip()
    )

    return tuple(dict.fromkeys(named))


def _asset_node_id(context, designation: str) -> str | None:
    """
    The governed asset identity retrieval matched for this designation.

    Read from the **assembled context**, never re-resolved: retrieval
    decided what this designation names, under the caller's scope, and a
    second opinion here could disagree with the first.

    Where a designation matched several governed assets this returns the
    first by governed identity, deterministically. That choice does not
    decide the answer: the rule reads the retrieval outcome the context
    carries and reports `AMBIGUOUS` before it compares anything.
    """

    normalized = designation.strip().casefold()
    matches = sorted(
        item.result.node.node_id
        for item in context.context_package.selected_assets
        if item.kind is GovernedResultKind.ASSET
        and item.result.node is not None
        and item.result.node.label.strip().casefold() == normalized
    )

    return matches[0] if matches else None


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

        try:
            if (
                request.intent_type
                is EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
            ):
                result = self._reason_about_structure(context)
            else:
                result = self._reason_about_quantities(context)
        except EngineeringReasoningError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.CONTEXT_BUILD_FAILURE,
                "The structural question could not be formed.",
                detail=str(error),
            ) from error
        except ValueError as error:  # pragma: no cover - defensive
            raise StepHandlerError(
                EngineeringEngineFailureCode.CONTEXT_BUILD_FAILURE,
                "Deterministic engineering reasoning failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.REASONING_RESULT, result
        )

    @staticmethod
    def _reason_about_quantities(context):
        request = context.execution_request

        return engineering_reasoning_service.evaluate_quantity_consistency(
            context.context_package,
            QuantityConsistencyQuery(
                subject_designation=subject_designation_of(request),
                quantity_kind=REASONED_QUANTITY_KIND,
                project_id=request.project_id,
            ),
            now=request.executed_at,
        )

    @staticmethod
    def _reason_about_structure(context):
        """
        The structural question needs two governed assets, and says so.

        A request that named fewer than two designations, or whose two
        designations resolved to one governed asset, is a request from
        which this question cannot be formed. That is reported as a step
        failure rather than as a reasoning outcome: "governed knowledge
        does not establish this" and "there was no question" are
        different things, and giving them the same shape would let the
        second be read as the first.
        """

        request = context.execution_request
        designations = subject_designations_of(request)

        if len(designations) < 2:
            raise SameAssetComparisonError(
                designations[0] if designations else ""
            )

        left, right = designations[0], designations[1]

        return (
            engineering_reasoning_service.evaluate_shared_structural_location(
                context.context_package,
                SharedStructuralLocationQuery(
                    left_asset_node_id=(
                        _asset_node_id(context, left) or f"unresolved:{left}"
                    ),
                    right_asset_node_id=(
                        _asset_node_id(context, right)
                        or f"unresolved:{right}"
                    ),
                    left_designation=left,
                    right_designation=right,
                    project_id=request.project_id,
                ),
                now=request.executed_at,
            )
        )
