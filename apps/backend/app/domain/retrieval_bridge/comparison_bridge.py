"""
The comparison arm of the Classification-to-Retrieval Bridge (Milestone
24.2): a classified ``ENGINEERING_COMPARISON`` request becomes two typed
operands, each with its own retrieval configuration.

It reuses the single-operand bridge's own designation extraction and
resolution rather than restating them, and adds exactly one rule the
single-operand path does not have: **the request must name exactly two
designations.**

That rule is where most of this module's value sits:

- **Fewer than two** is ``INSUFFICIENT_EVIDENCE``. A comparison against
  one subject is not a comparison, and the second operand is never
  inferred - not from the conversation, not from the project, not from
  what "usually" gets compared with a T1.
- **More than two** is ``CONFLICTING_EVIDENCE``. Three named subjects
  leave the system choosing which two the engineer meant, and choosing
  silently is how a comparison of the wrong pair gets acted on. The
  surplus is never truncated.

Order is preserved from the request's own token order: the first
designation is LEFT (baseline), the second RIGHT (candidate). Because
findings are directional, that ordering is part of the answer, not a
presentation detail.

Pure and deterministic: no I/O, no wall clock, no LLM, no fuzzy matching.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
)
from app.domain.retrieval_bridge.comparison_models import (
    ComparisonBridgeMetadata,
    ComparisonBridgeResult,
    ComparisonBridgeStatistics,
    ComparisonConfiguration,
    ComparisonOperand,
    ComparisonScope,
)
from app.domain.retrieval_bridge.designation_extraction import (
    extract_designations,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RequestDesignation,
    RetrievalBridgeFailure,
    RetrievalBridgeFailureCode,
    RetrievalConfiguration,
)
from app.domain.retrieval_bridge.retrieval_bridge_policy import (
    BRIDGE_POLICY_VERSION,
    COMPARISON_OPERAND_POLICY,
    REQUIRED_COMPARISON_OPERAND_COUNT,
    RETRIEVAL_BRIDGE_VERSION,
    IntentRetrievalPolicy,
)
from app.domain.retrieval_bridge.retrieval_bridge_validation import (
    validate_configuration,
)
from app.domain.retrieval_bridge.retrieval_mode import (
    RetrievalMode,
)


def derive_comparison_configuration(
    intent: EngineeringIntent, *, derived_at: datetime
) -> ComparisonBridgeResult:
    """The one entry point. Reads only the classified intent, and never
    re-classifies."""

    metadata = _metadata(intent, derived_at)

    if intent.intent_type is not COMPARISON_OPERAND_POLICY.intent_type:
        return _unresolved(
            metadata,
            (),
            RetrievalBridgeFailure(
                code=RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING,
                message=(
                    "Comparison preparation accepts only a classified "
                    "ENGINEERING_COMPARISON request."
                ),
                detail=f"Classified as '{intent.intent_type.value}'.",
            ),
        )

    input_failure = _input_failure(intent)
    if input_failure is not None:
        return _unresolved(metadata, (), input_failure)

    designations = extract_designations(intent.metadata.original_request_text)
    count_failure = _operand_count_failure(designations)
    if count_failure is not None:
        return _unresolved(metadata, designations, count_failure)

    left_designation, right_designation = designations
    left = _operand(left_designation)
    right = _operand(right_designation)

    for side, operand in (("left", left), ("right", right)):
        validation = validate_configuration(operand.configuration)
        if not validation.valid:
            return _unresolved(
                metadata,
                designations,
                RetrievalBridgeFailure(
                    code=(
                        RetrievalBridgeFailureCode
                        .INVALID_RETRIEVAL_CONFIGURATION
                    ),
                    message=(
                        f"The derived retrieval configuration for the "
                        f"{side} operand is structurally invalid."
                    ),
                    detail="; ".join(validation.errors),
                ),
            )

    return ComparisonBridgeResult(
        resolved=True,
        metadata=metadata,
        statistics=_statistics(designations),
        designations=designations,
        configuration=ComparisonConfiguration(
            left=left,
            right=right,
            scope=ComparisonScope(
                project_id=intent.project_id,
                both_operands_resolved_canonically=all(
                    designation.resolution
                    is DesignationResolution.CANONICAL_REFERENCE
                    for designation in designations
                ),
            ),
        ),
    )


# --- Operand derivation -----------------------------------------------------


def _operand(designation: RequestDesignation) -> ComparisonOperand:
    """
    One operand's retrieval configuration, under the shared comparison
    policy.

    A canonicalizable designation becomes an entity lookup for *its own
    side*: unlike the single-operand path, two canonical references here
    are the normal case rather than a conflict, because each side has its
    own configuration to carry one.
    """

    policy: IntentRetrievalPolicy = COMPARISON_OPERAND_POLICY

    if (
        policy.allows_canonical_entity_lookup
        and designation.resolution
        is DesignationResolution.CANONICAL_REFERENCE
    ):
        return ComparisonOperand(
            designation=designation,
            configuration=RetrievalConfiguration(
                mode=RetrievalMode.ENTITY_LOOKUP,
                limit=policy.result_limit,
                include_neighborhood=policy.include_neighborhood,
                neighborhood_depth=policy.neighborhood_depth,
                lexical_terms=(),
                canonical_entity_id=designation.canonical_reference,
            ),
        )

    return ComparisonOperand(
        designation=designation,
        configuration=RetrievalConfiguration(
            mode=policy.lexical_mode,
            limit=policy.result_limit,
            include_neighborhood=policy.include_neighborhood,
            neighborhood_depth=policy.neighborhood_depth,
            lexical_terms=(designation.text,),
        ),
    )


# --- Failures ----------------------------------------------------------------


def _operand_count_failure(
    designations: tuple[RequestDesignation, ...],
) -> RetrievalBridgeFailure | None:
    count = len(designations)

    if count == REQUIRED_COMPARISON_OPERAND_COUNT:
        return None

    named = ", ".join(designation.text for designation in designations) or "none"

    if count < REQUIRED_COMPARISON_OPERAND_COUNT:
        return RetrievalBridgeFailure(
            code=RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE,
            message=(
                "A comparison requires exactly two named subjects; this "
                f"request names {count}."
            ),
            detail=(
                f"Designations found: {named}. The missing subject is never "
                "inferred - a comparison against one subject is not a "
                "comparison."
            ),
        )

    return RetrievalBridgeFailure(
        code=RetrievalBridgeFailureCode.CONFLICTING_EVIDENCE,
        message=(
            "A comparison requires exactly two named subjects; this request "
            f"names {count}."
        ),
        detail=(
            f"Designations found: {named}. Choosing two of them would "
            "compare a pair the request did not ask for, and the surplus is "
            "never truncated."
        ),
    )


def _input_failure(intent: EngineeringIntent) -> RetrievalBridgeFailure | None:
    errors: list[str] = []

    if intent.project_id <= 0:
        errors.append("project_id is not positive.")
    if intent.project_id != intent.metadata.project_id:
        errors.append("The intent's project_id disagrees with its metadata.")
    if not intent.engineering_intent_id.value.strip():
        errors.append("engineering_intent_id is blank.")
    if not intent.metadata.original_request_text.strip():
        errors.append("The classified request text is blank.")

    if not errors:
        return None

    return RetrievalBridgeFailure(
        code=RetrievalBridgeFailureCode.INVALID_BRIDGE_INPUT,
        message="The supplied EngineeringIntent is structurally invalid.",
        detail="; ".join(errors),
    )


# --- Result assembly ---------------------------------------------------------


def _metadata(
    intent: EngineeringIntent, derived_at: datetime
) -> ComparisonBridgeMetadata:
    return ComparisonBridgeMetadata(
        retrieval_bridge_version=RETRIEVAL_BRIDGE_VERSION,
        bridge_policy_version=BRIDGE_POLICY_VERSION,
        project_id=intent.project_id,
        engineering_intent_id=intent.engineering_intent_id.value,
        intent_type=intent.intent_type,
        derived_at=derived_at,
    )


def _statistics(
    designations: tuple[RequestDesignation, ...],
) -> ComparisonBridgeStatistics:
    return ComparisonBridgeStatistics(
        designation_count=len(designations),
        required_operand_count=REQUIRED_COMPARISON_OPERAND_COUNT,
        canonical_reference_count=sum(
            1
            for designation in designations
            if designation.resolution
            is DesignationResolution.CANONICAL_REFERENCE
        ),
    )


def _unresolved(
    metadata: ComparisonBridgeMetadata,
    designations: tuple[RequestDesignation, ...],
    failure: RetrievalBridgeFailure,
) -> ComparisonBridgeResult:
    return ComparisonBridgeResult(
        resolved=False,
        metadata=metadata,
        statistics=_statistics(designations),
        designations=designations,
        failure=failure,
    )
