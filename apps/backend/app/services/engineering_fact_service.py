"""
Application service for Engineering Fact Construction (EPIC 2,
Milestone 29.2).

    Engineering Entities      (29.1, through its own repository port)
        -> Load supporting evidence   to check the support is real
        -> Check source identity      entities and evidence agree
        -> Construct                  a pure domain function
        -> Validate the fact set      every fact traces to entities and support
        -> Persist or reuse           never overwriting an earlier set

## Why the evidence is loaded at all

The entities already carry the locations the same-line rule needs, so
loading evidence is not how the rule is evaluated. It is how the rule is
**checked**: a fact set asserts associations grounded in observations,
and this service confirms that the evidence set exists, describes the
same document version, and actually contains every observation the
entities cite. Without that, a fact could rest on support nobody could
resolve - and it is precisely this pipeline's promise that it never
does.

It reads no canonical text, reopens no PDF, invokes no extractor,
resolves no entities itself, calls no LLM, and writes no graph node or
edge.
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
from app.domain.engineering_facts.fact_policy import (
    FACT_CONTRACT_VERSION,
)
from app.domain.engineering_facts.fact_identity import (
    fact_set_identity,
)
from app.domain.engineering_entities.engineering_entity_repository import (
    EngineeringEntityRepository,
)
from app.domain.engineering_evidence.engineering_evidence_repository import (
    EngineeringEvidenceRepository,
)
from app.domain.engineering_facts.engineering_fact_repository import (
    EngineeringFactRepository,
)
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_facts.fact_failures import (
    FactConstructionFailure,
    FactConstructionFailureCode,
)
from app.domain.engineering_facts.fact_models import EngineeringFactSet
from app.domain.engineering_facts.fact_policy import (
    FACT_POLICY_VERSION,
    SUPPORTED_RESOLUTION_POLICY_VERSIONS,
    is_supported_resolution_policy_version,
)
from app.domain.engineering_facts.fact_validation import validate_fact_set


@dataclass(frozen=True, slots=True)
class FactConstructionResult:
    """
    What one construction concluded.

    The four outcomes a caller must tell apart are all derivable here:
    facts constructed, nothing associated, an existing set re-used, and
    completed-with-ambiguities. A failure is the fifth, and carries a
    typed cause.
    """

    succeeded: bool
    fact_set: EngineeringFactSet | None = None
    reused: bool = False
    failure: FactConstructionFailure | None = None

    @property
    def found_facts(self) -> bool:
        """Whether anything associated. ``False`` is a successful
        outcome: a document may hold no line on which a designation and a
        quantity appear together."""

        return self.fact_set is not None and not self.fact_set.is_empty

    @property
    def has_ambiguities(self) -> bool:
        """Whether any line held candidates the rules declined to pair.
        Not a failure - the rules working."""

        return (
            self.fact_set is not None and self.fact_set.has_ambiguities
        )


def construct_document_facts(
    entity_repository: EngineeringEntityRepository,
    evidence_repository: EngineeringEvidenceRepository,
    fact_repository: EngineeringFactRepository,
    *,
    document_id: int,
    fact_policy_version: str = FACT_POLICY_VERSION,
) -> FactConstructionResult:
    """
    Construct - or re-use - the engineering facts of one document.

    Checks run in order and the first failure is returned: there is no
    point checking support for entities that do not exist.
    """

    entity_set = entity_repository.find_latest_for_document(document_id)

    if entity_set is None:
        return _failed(
            FactConstructionFailureCode.ENTITY_SET_MISSING,
            f"Document '{document_id}' has no engineering entities; "
            "there is nothing to associate.",
            detail="Fact construction is the step after entity "
            "resolution. Entities are its subject matter - it never "
            "reads canonical text or the original document.",
        )

    if not is_supported_resolution_policy_version(
        entity_set.resolution_policy_version
    ):
        return _failed(
            FactConstructionFailureCode.UNSUPPORTED_ENTITY_SET_VERSION,
            f"The entities for document '{document_id}' were resolved "
            f"under policy '{entity_set.resolution_policy_version}', "
            "which this constructor does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_RESOLUTION_POLICY_VERSIONS))
                + ". A newer policy may carry entity types this code "
                "would silently ignore, and a fact set missing half its "
                "subjects is worse than a visible refusal."
            ),
        )

    evidence_set = evidence_repository.find_latest_for_document(document_id)

    if evidence_set is None:
        return _failed(
            FactConstructionFailureCode.ENTITY_EVIDENCE_MISSING,
            f"The entities for document '{document_id}' cite evidence "
            "that is no longer available.",
            detail="Associations would rest on support nobody could "
            "check.",
        )

    # The entities must have been resolved from *this* evidence set, not
    # merely from one that shares a checksum. Comparing lineage rather
    # than provenance fields settles it for every axis at once: a
    # different representation, segmentation or extraction policy is a
    # different evidence identity, and entities carrying another one
    # would be associated using observations that never produced them.
    if entity_set.upstream_identity != evidence_set.artifact_identity:
        return _failed(
            FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The entities and the evidence for document "
            f"'{document_id}' describe different readings of the "
            "document.",
            detail="Continuing would associate entities from one "
            "revision using observations from another. Re-resolve the "
            "entities from the current evidence first.",
        )

    missing = _unresolvable_support(entity_set, evidence_set)

    if missing:
        return _failed(
            FactConstructionFailureCode.ENTITY_EVIDENCE_MISSING,
            f"An entity of document '{document_id}' cites an "
            "observation that its evidence set does not contain.",
            detail=f"First unresolvable evidence key: {missing[:12]}.",
        )

    if entity_set.artifact_identity is None:
        return _failed(
            FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The entity set of document '{document_id}' was stored "
            "before the derivation identity chain existed.",
            detail="Its provenance cannot be reconstructed, so anything "
            "derived from it could never prove its own reuse is valid, "
            "and nothing could deduplicate it. Re-run the entity resolution "
            "stage to give it a current identity.",
        )

    # What this stage produces from that artifact under its own
    # contract. Everything further upstream reaches this digest through
    # the upstream identity; this layer names no other layer's versions.
    try:
        expected_identity = fact_set_identity(
            entity_set=ArtifactIdentity(
                value=entity_set.artifact_identity,
                kind=ArtifactKind.ENTITY_SET,
                contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
            ),
            fact_policy_version=fact_policy_version,
            fact_contract_version=FACT_CONTRACT_VERSION,
        )
    except InvalidArtifactIdentityError as error:
        return _failed(
            FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The upstream artifact of document '{document_id}' "
            "carries a malformed derivation identity.",
            detail=f"{type(error).__name__}: {error}",
        )

    existing = fact_repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        return FactConstructionResult(
            succeeded=True, fact_set=existing, reused=True
        )

    try:
        fact_set = construct_facts(
            entity_set, fact_policy_version=fact_policy_version
        )
    except Exception as error:  # noqa: BLE001 - see below
        # The constructor is pure and total by design, so reaching here
        # means a rule defect rather than a data condition. Caught
        # anyway: a caller needs one honest answer instead of an
        # exception crossing the boundary, and the cause is carried in
        # ``detail`` rather than swallowed.
        return _failed(
            FactConstructionFailureCode.RULE_EXECUTION_FAILURE,
            f"A rule failed while constructing facts for document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    violation = validate_fact_set(fact_set, entity_set)

    if violation is not None:
        return _failed(
            violation.code, violation.message, detail=violation.detail
        )

    try:
        fact_repository.save(fact_set)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            FactConstructionFailureCode.FACT_PERSISTENCE_FAILURE,
            f"The fact set for document '{document_id}' was constructed "
            "and could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return FactConstructionResult(
        succeeded=True, fact_set=fact_set, reused=False
    )


def get_fact_set(
    fact_repository: EngineeringFactRepository, document_id: int
) -> EngineeringFactSet | None:
    """
    The current fact set of one document - the **only** thing a future
    Knowledge Graph population milestone should consume.

    ``None`` means no construction has run. Not an error: most documents
    have not had facts constructed.
    """

    return fact_repository.find_latest_for_document(document_id)


def _unresolvable_support(entity_set, evidence_set) -> str | None:
    """
    The first evidence key an entity cites that its evidence set does not
    contain, or ``None`` if every citation resolves.

    This is the integrity check the whole layer rests on: a fact's
    support must be resolvable through immutable evidence references,
    never reconstructed later by searching text.
    """

    available = {item.evidence_key for item in evidence_set.evidence}

    for entity in entity_set.entities:
        for key in entity.evidence_keys:
            if key not in available:
                return key

    return None


def _failed(
    code: FactConstructionFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> FactConstructionResult:
    return FactConstructionResult(
        succeeded=False,
        failure=FactConstructionFailure(
            code=code, message=message, detail=detail
        ),
    )
