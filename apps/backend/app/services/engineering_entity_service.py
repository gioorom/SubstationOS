"""
Application service for Engineering Entity Resolution (EPIC 2,
Milestone 29.1).

    Engineering Evidence      (28.1, through its own repository port)
        -> Check the policy    this resolver understands that evidence
        -> Resolve             a pure domain function
        -> Validate the set    every entity traces to evidence in the source
        -> Persist or reuse    never overwriting an earlier set

**Its only input is engineering evidence.** It has no canonical text
repository, no content port, no parser and no PDF library: it could not
look at the document if it wanted to. It writes no Knowledge Graph node
and no Engineering Index record - a later milestone will generate graph
nodes from entities, with its own review obligations, and this one
deliberately stops at the hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.artifact_identity.artifact_identity_exceptions import (  # noqa: E501
    InvalidArtifactIdentityError,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
)
from app.domain.engineering_entities.entity_policy import (
    ENTITY_MODEL_VERSION,
)
from app.domain.engineering_entities.entity_identity import (
    entity_set_identity,
)
from app.domain.engineering_entities.engineering_entity_repository import (
    EngineeringEntityRepository,
)
from app.domain.engineering_entities.entity_failures import (
    EntityResolutionFailure,
    EntityResolutionFailureCode,
)
from app.domain.engineering_entities.entity_models import (
    EngineeringEntitySet,
)
from app.domain.engineering_entities.entity_policy import (
    RESOLUTION_POLICY_VERSION,
    SUPPORTED_EXTRACTION_POLICY_VERSIONS,
    is_supported_extraction_policy_version,
)
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_entities.entity_validation import (
    validate_entity_set,
)
from app.domain.engineering_evidence.engineering_evidence_repository import (
    EngineeringEvidenceRepository,
)


@dataclass(frozen=True, slots=True)
class EntityResolutionResult:
    """
    What one resolution concluded.

    ``reused`` distinguishes "this evidence was already resolved under
    these rules" from "it was resolved now". Both are successes returning
    the same value - but re-running must be observably free of work, and
    a test can prove idempotency from it.
    """

    succeeded: bool
    entity_set: EngineeringEntitySet | None = None
    reused: bool = False
    failure: EntityResolutionFailure | None = None

    @property
    def found_entities(self) -> bool:
        """Whether anything resolved. ``False`` is a successful outcome,
        not a failure: a document may contain no observations these rules
        group into anything."""

        return self.entity_set is not None and not self.entity_set.is_empty


def resolve_document_entities(
    evidence_repository: EngineeringEvidenceRepository,
    entity_repository: EngineeringEntityRepository,
    *,
    document_id: int,
    resolution_policy_version: str = RESOLUTION_POLICY_VERSION,
) -> EntityResolutionResult:
    """
    Resolve - or re-use - the engineering entities of one document.

    Checks run in order and the first failure is returned: there is no
    point complaining about an evidence set's policy version when there
    is no evidence set.
    """

    evidence_set = evidence_repository.find_latest_for_document(document_id)

    if evidence_set is None:
        return _failed(
            EntityResolutionFailureCode.EVIDENCE_SET_MISSING,
            f"Document '{document_id}' has no engineering evidence; "
            "there is nothing to resolve into entities.",
            detail="Entity resolution is the step after evidence "
            "extraction. Evidence is its only input - it never reads "
            "canonical text or the original document.",
        )

    if evidence_set.document_id != document_id:
        return _failed(
            EntityResolutionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The evidence returned for document '{document_id}' "
            f"describes document '{evidence_set.document_id}'.",
            detail="Continuing would attach a hypothesis to the wrong "
            "document.",
        )

    if not is_supported_extraction_policy_version(
        evidence_set.extraction_policy_version
    ):
        return _failed(
            EntityResolutionFailureCode.UNSUPPORTED_EXTRACTION_POLICY_VERSION,
            f"The evidence for document '{document_id}' was extracted "
            f"under policy "
            f"'{evidence_set.extraction_policy_version}', which this "
            "resolver does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_EXTRACTION_POLICY_VERSIONS))
                + ". A newer policy may carry evidence types this code "
                "would silently drop, and an entity set missing half its "
                "evidence is worse than a visible refusal."
            ),
        )

    if evidence_set.artifact_identity is None:
        return _failed(
            EntityResolutionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The evidence set of document '{document_id}' was stored "
            "before the derivation identity chain existed.",
            detail="Its provenance cannot be reconstructed, so anything "
            "derived from it could never prove its own reuse is valid, "
            "and nothing could deduplicate it. Re-run the extraction "
            "stage to give it a current identity.",
        )

    # What this stage produces from that artifact under its own
    # contract. Everything further upstream reaches this digest through
    # the upstream identity; this layer names no other layer's versions.
    try:
        expected_identity = entity_set_identity(
            evidence_set=ArtifactIdentity(
                value=evidence_set.artifact_identity,
                kind=ArtifactKind.EVIDENCE_SET,
                contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
            ),
            resolution_policy_version=resolution_policy_version,
            entity_model_version=ENTITY_MODEL_VERSION,
        )
    except InvalidArtifactIdentityError as error:
        return _failed(
            EntityResolutionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The upstream artifact of document '{document_id}' "
            "carries a malformed derivation identity.",
            detail=f"{type(error).__name__}: {error}",
        )

    existing = entity_repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        return EntityResolutionResult(
            succeeded=True, entity_set=existing, reused=True
        )

    try:
        entity_set = resolve_entities(
            evidence_set,
            resolution_policy_version=resolution_policy_version,
        )
    except Exception as error:  # noqa: BLE001 - see below
        # The resolver is pure and total by design, so reaching here
        # means a rule defect rather than a data condition. Caught
        # anyway: a caller needs one honest answer instead of an
        # exception crossing the boundary, and the cause is carried in
        # ``detail`` rather than swallowed.
        return _failed(
            EntityResolutionFailureCode.RESOLUTION_FAILURE,
            f"A rule failed while resolving entities for document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    violation = validate_entity_set(entity_set, evidence_set)

    if violation is not None:
        return _failed(
            violation.code, violation.message, detail=violation.detail
        )

    try:
        entity_repository.save(entity_set)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            EntityResolutionFailureCode.ENTITY_PERSISTENCE_FAILURE,
            f"The entity set for document '{document_id}' was resolved "
            "and could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return EntityResolutionResult(
        succeeded=True, entity_set=entity_set, reused=False
    )


def get_entity_set(
    entity_repository: EngineeringEntityRepository, document_id: int
) -> EngineeringEntitySet | None:
    """
    The current entity set of one document - the **only** thing a future
    Knowledge Graph population milestone should consume.

    ``None`` means no resolution has run. Not an error: most documents
    have not been resolved, and an empty set would be indistinguishable
    from a document in which nothing was found.
    """

    return entity_repository.find_latest_for_document(document_id)


def _failed(
    code: EntityResolutionFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> EntityResolutionResult:
    return EntityResolutionResult(
        succeeded=False,
        failure=EntityResolutionFailure(
            code=code, message=message, detail=detail
        ),
    )
