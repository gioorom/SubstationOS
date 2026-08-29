"""
The Classification-to-Retrieval Bridge itself (Milestone 23B.3):

    EngineeringIntent
            |
       input validation
            |
       policy lookup            (retrieval_bridge_policy.py - a table)
            |
       designation extraction   (designation_extraction.py)
            |
       evidence resolution      (this module)
            |
       configuration validation (retrieval_bridge_validation.py)
            |
       RetrievalBridgeResult

Pure and deterministic: no I/O, no persistence, no network, no wall-clock
read (``derived_at`` is caller-supplied), **no LLM, no embeddings, no
provider call, and no fuzzy matching**. Given the same
``EngineeringIntent`` and the same policy version, always produces the
same result.

There is deliberately **no fallback**. Every path that cannot produce
criteria the engineer actually evidenced returns a typed unresolved
result. Broadening retrieval to "everything in the project" when a
request is under-specified would answer a question nobody asked, and in
this domain a confident answer about the wrong equipment is worse than
an admitted gap.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntent,
)
from app.domain.retrieval_bridge.designation_extraction import (
    extract_designations,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RequestDesignation,
    RetrievalBridgeFailure,
    RetrievalBridgeFailureCode,
    RetrievalBridgeMetadata,
    RetrievalBridgeResult,
    RetrievalBridgeStatistics,
    RetrievalConfiguration,
)
from app.domain.retrieval_bridge.retrieval_bridge_policy import (
    BRIDGE_POLICY_VERSION,
    RETRIEVAL_BRIDGE_VERSION,
    SUPPORTED_INTENT_TYPES,
    IntentRetrievalPolicy,
    policy_for,
)
from app.domain.retrieval_bridge.retrieval_bridge_validation import (
    validate_configuration,
)
from app.domain.retrieval_bridge.retrieval_mode import (
    RetrievalMode,
)


def derive_retrieval_configuration(
    intent: EngineeringIntent, *, derived_at: datetime
) -> RetrievalBridgeResult:
    """
    The one entry point. Reads only the classified intent - its type, its
    project, and the request text it was classified from - and never
    re-classifies, never re-normalizes for classification purposes, and
    never consults anything outside the fixed vocabularies.
    """

    metadata = _metadata(intent, derived_at)

    input_failure = _input_failure(intent)
    if input_failure is not None:
        return _unresolved(metadata, (), input_failure)

    policy = policy_for(intent.intent_type)
    if policy is None:
        return _unresolved(
            metadata,
            (),
            RetrievalBridgeFailure(
                code=RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING,
                message=(
                    "This bridge maps no retrieval configuration for "
                    f"intent type '{intent.intent_type.value}'."
                ),
                detail=(
                    "Mapped intent types: "
                    + ", ".join(
                        supported.value for supported in SUPPORTED_INTENT_TYPES
                    )
                ),
            ),
        )

    designations = extract_designations(intent.metadata.original_request_text)

    if not designations:
        return _unresolved(
            metadata,
            designations,
            RetrievalBridgeFailure(
                code=RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE,
                message=(
                    "The request names no equipment designation, so no "
                    "retrieval criteria can be derived from it."
                ),
                detail=(
                    "A designation is a token containing both letters and "
                    "digits (for example 'T2', '87T', 'C-295'). Retrieval "
                    "is deliberately not broadened when none is present."
                ),
            ),
        )

    configuration, conflict = _configuration_for(policy, designations)
    if conflict is not None:
        return _unresolved(metadata, designations, conflict)

    validation = validate_configuration(configuration)
    if not validation.valid:
        return _unresolved(
            metadata,
            designations,
            RetrievalBridgeFailure(
                code=(
                    RetrievalBridgeFailureCode.INVALID_RETRIEVAL_CONFIGURATION
                ),
                message=(
                    "The derived retrieval configuration is structurally "
                    "invalid and was not returned."
                ),
                detail="; ".join(validation.errors),
            ),
        )

    return RetrievalBridgeResult(
        resolved=True,
        metadata=metadata,
        statistics=_statistics(designations),
        designations=designations,
        configuration=configuration,
    )


# --- Evidence resolution ---------------------------------------------------


def _canonical_designations(
    designations: tuple[RequestDesignation, ...],
) -> tuple[RequestDesignation, ...]:
    return tuple(
        designation
        for designation in designations
        if designation.resolution is DesignationResolution.CANONICAL_REFERENCE
    )


def _configuration_for(
    policy: IntentRetrievalPolicy,
    designations: tuple[RequestDesignation, ...],
) -> tuple[RetrievalConfiguration | None, RetrievalBridgeFailure | None]:
    """
    Entity lookup when the policy allows it and the request resolved to
    exactly one canonical reference; a lexical search over the
    designations as written otherwise.

    Two *distinct* canonical references is a genuine conflict, not a
    choice to make: retrieval accepts one canonical entity, and picking
    either would silently answer about one piece of equipment while the
    engineer named two.
    """

    canonical = _canonical_designations(designations)

    if policy.allows_canonical_entity_lookup and canonical:
        distinct = {
            designation.canonical_reference for designation in canonical
        }
        if len(distinct) > 1:
            return None, RetrievalBridgeFailure(
                code=RetrievalBridgeFailureCode.CONFLICTING_EVIDENCE,
                message=(
                    "The request names more than one canonical entity, and "
                    "retrieval resolves one."
                ),
                detail="Named entities: " + ", ".join(sorted(distinct)),
            )

        reference = canonical[0]

        # entity_type is deliberately left unset even though the resolved
        # reference carries one: Structured Retrieval's ENTITY_LOOKUP mode
        # admits the canonical-id criterion *only*, so adding an entity
        # type would make the request it builds invalid. The type is not
        # lost - it is reported on the RequestDesignation, which is where
        # provenance belongs.
        return (
            RetrievalConfiguration(
                mode=RetrievalMode.ENTITY_LOOKUP,
                limit=policy.result_limit,
                include_neighborhood=policy.include_neighborhood,
                neighborhood_depth=policy.neighborhood_depth,
                lexical_terms=(),
                canonical_entity_id=reference.canonical_reference,
            ),
            None,
        )

    return (
        RetrievalConfiguration(
            mode=policy.lexical_mode,
            limit=policy.result_limit,
            include_neighborhood=policy.include_neighborhood,
            neighborhood_depth=policy.neighborhood_depth,
            lexical_terms=tuple(
                designation.text for designation in designations
            ),
        ),
        None,
    )


# --- Input validation ------------------------------------------------------


def _input_failure(intent: EngineeringIntent) -> RetrievalBridgeFailure | None:
    errors: list[str] = []

    if intent.project_id <= 0:
        errors.append("project_id is not positive.")

    if intent.project_id != intent.metadata.project_id:
        errors.append(
            "The intent's project_id disagrees with its own metadata."
        )

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


# --- Result assembly -------------------------------------------------------


def _metadata(
    intent: EngineeringIntent, derived_at: datetime
) -> RetrievalBridgeMetadata:
    return RetrievalBridgeMetadata(
        retrieval_bridge_version=RETRIEVAL_BRIDGE_VERSION,
        bridge_policy_version=BRIDGE_POLICY_VERSION,
        project_id=intent.project_id,
        engineering_intent_id=intent.engineering_intent_id.value,
        intent_type=intent.intent_type,
        derived_at=derived_at,
    )


def _statistics(
    designations: tuple[RequestDesignation, ...],
) -> RetrievalBridgeStatistics:
    canonical = _canonical_designations(designations)

    return RetrievalBridgeStatistics(
        designation_count=len(designations),
        canonical_reference_count=len(canonical),
        lexical_term_count=len(designations) - len(canonical),
    )


def _unresolved(
    metadata: RetrievalBridgeMetadata,
    designations: tuple[RequestDesignation, ...],
    failure: RetrievalBridgeFailure,
) -> RetrievalBridgeResult:
    return RetrievalBridgeResult(
        resolved=False,
        metadata=metadata,
        statistics=_statistics(designations),
        designations=designations,
        failure=failure,
    )
