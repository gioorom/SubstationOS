"""
The Engineering Engine's retrieval steps, on governed knowledge
(EPIC 31.2).

These replace the two handlers that read the Canonical Facts projection
through ``GraphQueryRepository``. The workflow definitions, the step
types, the artifact keys, the planner and the executor are **unchanged**:
a step still builds a retrieval plan and a step still executes it. What
changed is where the knowledge comes from, which is the whole point of
the milestone and is deliberately the only thing that changed.

---

## How an engine request becomes a governed query

The engine's execution request carries the retrieval configuration the
Retrieval Bridge derived from a classified engineering request. That
configuration predates governed knowledge, so the mapping is stated here
once, explicitly, rather than being spread across handlers:

| Request field | Governed query | Why |
|---|---|---|
| `retrieval_canonical_entity_id` (`"CABLE:C-295"`) | `AssetDesignationQuery("C-295")` | The governed graph holds what a document *designates*, never what the equipment *is* - so the type prefix has no governed counterpart and is dropped rather than matched against something that would have to be invented. |
| `retrieval_lexical_terms` | one `AssetDesignationQuery` **per term** | Each designation the engineer named is resolved on its own, so each keeps its own outcome and its own ambiguity. |
| `retrieval_include_neighborhood` | traverse governed relationships from each resolved asset | The governed successor of 1-hop neighbourhood enrichment: a governed edge *is* the neighbourhood. |
| `retrieval_entity_type`, `retrieval_attribute_name` | **nothing** | Neither has a governed counterpart: the graph refuses to classify equipment, and it has no property bag to name an attribute in. A request carrying only these resolves nothing and says so. |

Two rules hold throughout, and both are refusals:

- **No fallback.** A configuration that names no designation retrieves
  nothing and reports ``NO_MATCH``. It is never broadened to the
  project, because answering confidently about the wrong equipment is
  worse here than admitting a gap.
- **Current knowledge only.** Every query the engine issues is scoped
  ``CURRENT_ONLY``, and there is no request field that could widen it.
  Historical knowledge is what the platform used to assert, and it must
  never quietly answer a question an engineer is asking now.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    ComparisonOperandCriteria,
    EngineeringEngineExecutionRequest,
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.governed_retrieval.governed_retrieval_exceptions import (
    GovernedRetrievalError,
)
from app.domain.governed_retrieval.governed_retrieval_factory import (
    GovernedRetrievalQueryFactory,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalQuery,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    RetrievalScope,
)
from app.services import governed_retrieval_service
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.governed_retrieval_artifacts import (
    GovernedRetrievalOutcome,
    GovernedRetrievalPlan,
)
from app.services.engineering_engine.step_handler import (
    BaseStepHandler,
    StepHandlerError,
)

#: The engine never reads what the graph used to assert. Stated as a
#: constant so the decision is visible at the one place it is made.
ENGINE_RETRIEVAL_SCOPE = RetrievalScope.CURRENT_ONLY


def designation_of(canonical_entity_id: str) -> str:
    """
    The designation inside a legacy canonical entity reference.

    ``"CABLE:C-295"`` designates ``C-295``. The ``CABLE`` prefix is a
    classification, and the governed graph refuses to make one - so it
    is dropped rather than matched against a governed field that would
    have to be invented to receive it.
    """

    _, _, tail = canonical_entity_id.rpartition(":")

    return tail or canonical_entity_id


def _designations(
    canonical_entity_id: str | None, lexical_terms: tuple[str, ...]
) -> tuple[str, ...]:
    """
    Every designation the request names, strongest source first, in a
    fixed order and without duplicates.
    """

    named: list[str] = []

    if canonical_entity_id:
        named.append(designation_of(canonical_entity_id))

    named.extend(term for term in lexical_terms if term.strip())

    return tuple(dict.fromkeys(named))


def _unsupported(
    entity_type: str | None, attribute_name: str | None
) -> tuple[str, ...]:
    reported: list[str] = []

    if entity_type:
        reported.append(
            f"retrieval_entity_type='{entity_type}' (the governed graph "
            "holds designations, never equipment classifications)"
        )

    if attribute_name:
        reported.append(
            f"retrieval_attribute_name='{attribute_name}' (the governed "
            "graph has no attribute bag; quantities are governed "
            "relationships)"
        )

    return tuple(reported)


def build_plan(
    *,
    project_id: int,
    canonical_entity_id: str | None,
    lexical_terms: tuple[str, ...],
    entity_type: str | None,
    attribute_name: str | None,
    limit: int,
    include_relationships: bool,
) -> GovernedRetrievalPlan:
    """
    The one mapping from engine criteria to governed queries.

    Shared by the single-subject and the comparison workflows so the two
    can never diverge about what a given configuration means.
    """

    designations = _designations(canonical_entity_id, lexical_terms)

    queries: list[GovernedRetrievalQuery] = []

    for designation in designations:
        queries.append(
            GovernedRetrievalQueryFactory.asset_by_designation(
                designation=designation,
                scope=ENGINE_RETRIEVAL_SCOPE,
                limit=limit,
                project_id=project_id,
            )
        )

        if include_relationships:
            queries.append(
                GovernedRetrievalQueryFactory.quantity_for_asset(
                    designation=designation,
                    scope=ENGINE_RETRIEVAL_SCOPE,
                    limit=limit,
                    project_id=project_id,
                )
            )

    return GovernedRetrievalPlan(
        project_id=project_id,
        queries=tuple(queries),
        unsupported_criteria=_unsupported(entity_type, attribute_name),
    )


def _plan_for_request(
    request: EngineeringEngineExecutionRequest,
) -> GovernedRetrievalPlan:
    return build_plan(
        project_id=request.project_id,
        canonical_entity_id=request.retrieval_canonical_entity_id,
        lexical_terms=tuple(request.retrieval_lexical_terms),
        entity_type=request.retrieval_entity_type,
        attribute_name=request.retrieval_attribute_name,
        limit=request.retrieval_limit,
        include_relationships=request.retrieval_include_neighborhood,
    )


def _plan_for_operand(
    operand: ComparisonOperandCriteria, project_id: int
) -> GovernedRetrievalPlan:
    return build_plan(
        project_id=project_id,
        canonical_entity_id=operand.retrieval_canonical_entity_id,
        lexical_terms=tuple(operand.retrieval_lexical_terms),
        entity_type=operand.retrieval_entity_type,
        attribute_name=operand.retrieval_attribute_name,
        limit=operand.retrieval_limit,
        include_relationships=operand.retrieval_include_neighborhood,
    )


class BuildGovernedRetrievalPlanStepHandler(BaseStepHandler):
    """Maps the engine's retrieval configuration onto typed governed
    queries. Pure: no read happens in this step, so a caller can inspect
    what a request would ask before anything runs."""

    step_type = WorkflowStepType.BUILD_RETRIEVAL_REQUEST

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            plan = _plan_for_request(context.execution_request)
        except GovernedRetrievalError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RETRIEVAL_FAILURE,
                "Could not build a valid governed retrieval plan.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.RETRIEVAL_REQUEST, plan
        )


class ExecuteGovernedRetrievalStepHandler(BaseStepHandler):
    """
    Runs the plan against the governed graph.

    Reads through ``GovernedKnowledgeReader``, a port with **no write
    method** - so this handler could not write engineering knowledge
    even if a later change tried to.
    """

    step_type = WorkflowStepType.EXECUTE_RETRIEVAL

    def __init__(self, governed_knowledge_reader) -> None:
        self._reader = governed_knowledge_reader

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        outcome = execute_plan(
            self._reader,
            context.retrieval_request,
            now=context.execution_request.executed_at,
            failure_description="Governed structured retrieval failed.",
        )

        return context.with_artifact(
            WorkflowArtifactKey.RETRIEVAL_RESULT, outcome
        )


def execute_plan(
    reader,
    plan: GovernedRetrievalPlan,
    *,
    now,
    failure_description: str,
) -> GovernedRetrievalOutcome:
    """Executes every query in a plan, in the plan's own order, and
    keeps each result whole."""

    try:
        return GovernedRetrievalOutcome(
            results=tuple(
                governed_retrieval_service.retrieve(reader, query, now=now)
                for query in plan.queries
            )
        )
    except GovernedRetrievalError as error:
        raise StepHandlerError(
            EngineeringEngineFailureCode.RETRIEVAL_FAILURE,
            failure_description,
            detail=str(error),
        ) from error


class BuildComparisonGovernedRetrievalPlansStepHandler(BaseStepHandler):
    """Builds **both** operands' governed plans in one step - building is
    pure, and an operand set that cannot produce a plan is an invalid
    request whichever side it came from."""

    step_type = WorkflowStepType.BUILD_COMPARISON_RETRIEVAL_REQUESTS

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request
        left = request.comparison_left
        right = request.comparison_right

        missing = [
            name
            for name, operand in (("left", left), ("right", right))
            if operand is None
        ]
        if missing:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                "A comparison requires exactly two operands.",
                detail=(
                    "Missing operand(s): "
                    + ", ".join(missing)
                    + ". A comparison is never run against a single "
                    "subject, and the second is never inferred."
                ),
            )

        return context.with_artifact(
            WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST,
            self._plan(left, request.project_id, "left"),
        ).with_artifact(
            WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST,
            self._plan(right, request.project_id, "right"),
        )

    @staticmethod
    def _plan(
        operand: ComparisonOperandCriteria, project_id: int, side: str
    ) -> GovernedRetrievalPlan:
        try:
            return _plan_for_operand(operand, project_id)
        except GovernedRetrievalError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                f"Could not build a valid governed retrieval plan for the "
                f"{side} comparison operand.",
                detail=f"{side} operand '{operand.designation}': {error}",
            ) from error


class _ExecuteSideGovernedRetrievalStepHandler(BaseStepHandler):
    """Shared body for the two comparison retrieval steps. The side is
    fixed per subclass rather than resolved at runtime, so no code path
    can read one side's plan and write the other's result."""

    request_key: WorkflowArtifactKey
    result_key: WorkflowArtifactKey
    side: str

    def __init__(self, governed_knowledge_reader) -> None:
        self._reader = governed_knowledge_reader

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        outcome = execute_plan(
            self._reader,
            context.get_artifact(self.request_key),
            now=context.execution_request.executed_at,
            failure_description=(
                f"Governed structured retrieval failed for the "
                f"{self.side} comparison operand."
            ),
        )

        return context.with_artifact(self.result_key, outcome)


class ExecuteLeftGovernedRetrievalStepHandler(
    _ExecuteSideGovernedRetrievalStepHandler
):
    step_type = WorkflowStepType.EXECUTE_LEFT_RETRIEVAL
    request_key = WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST
    result_key = WorkflowArtifactKey.LEFT_RETRIEVAL_RESULT
    side = "left"


class ExecuteRightGovernedRetrievalStepHandler(
    _ExecuteSideGovernedRetrievalStepHandler
):
    step_type = WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL
    request_key = WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST
    result_key = WorkflowArtifactKey.RIGHT_RETRIEVAL_RESULT
    side = "right"
