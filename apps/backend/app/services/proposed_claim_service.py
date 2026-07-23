"""
Application services for Proposed Claims (Milestone 10.1). Each
function is a single use case, orchestrating the domain
(``app.domain.proposed_claims``) through the ``ProposedClaimRepository``
port - never a raw database session.

A Proposed Claim references the Engineering Index (``EngineeringIndexRepository``)
and the Document/Project scoping context (``DocumentLookupPort``, reused
from ``app.domain.engineering_index`` - CLAUDE.md SS14 forbids
copy-pasting domain logic) purely to read: a claim is built from
existing Engineering Index entries, and every write here validates that
each cited entry's document is PROJECT-scoped and its Project is
mutable, exactly as the Engineering Index and Review Workflow do for
their own writes. Nothing in this module writes into the Engineering
Index, and nothing here knows about Review Workflow - the dependency
runs the other way (Review Workflow depends on this module, never the
reverse).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_index.document_lookup import (
    DocumentIndexContext,
    DocumentLookupPort,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import MUTABLE_STATES
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    CrossProjectEvidenceError,
    DocumentNotClaimableError,
    DuplicateProposedClaimError,
    EvidenceEntryNotFoundError,
    ProjectNotClaimableError,
    ProposedClaimNotFoundError,
)
from app.domain.proposed_claims.proposed_claim_factory import (
    EvidenceReferenceFactory,
    ProposedClaimFactory,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.domain.proposed_claims.proposed_claim_validator import (
    ProposedClaimValidator,
)


def _require_claimable_document(
    document_lookup: DocumentLookupPort,
    document_id: int,
) -> DocumentIndexContext:
    context = document_lookup.find(document_id)

    if context is None or context.scope is not DocumentScope.PROJECT:
        raise DocumentNotClaimableError(
            document_id,
            context.scope
            if context is not None
            else DocumentScope.CANONICAL_LIBRARY,
        )

    if context.project_lifecycle_state not in MUTABLE_STATES:
        raise ProjectNotClaimableError(
            context.project_id,  # type: ignore[arg-type]
            context.project_lifecycle_state,  # type: ignore[arg-type]
        )

    return context


def _resolve_evidence(
    engineering_index_repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    engineering_index_entry_ids: list[int],
    *,
    allow_cross_document_evidence: bool,
) -> tuple[int, tuple[EvidenceReference, ...]]:
    """
    Fetches and validates every cited Engineering Index entry, and
    returns the single project id they all belong to together with the
    ``EvidenceReference`` tuple built from them.
    """

    entries: list[IndexEntry] = []

    for entry_id in engineering_index_entry_ids:
        entry = engineering_index_repository.get_by_id(entry_id)

        if entry is None:
            raise EvidenceEntryNotFoundError(entry_id)

        entries.append(entry)

    ProposedClaimValidator.validate_evidence_same_project(
        [entry.project_id for entry in entries]
    )
    ProposedClaimValidator.validate_evidence_documents(
        [entry.document_id for entry in entries],
        allow_cross_document_evidence=allow_cross_document_evidence,
    )

    for document_id in {entry.document_id for entry in entries}:
        _require_claimable_document(document_lookup, document_id)

    evidence = tuple(
        EvidenceReferenceFactory.from_index_entry(entry)
        for entry in entries
    )

    return entries[0].project_id, evidence


def create_proposed_claim(
    claim_repository: ProposedClaimRepository,
    engineering_index_repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    claim_type: ClaimType,
    subject: str,
    predicate: str | None,
    object_: str | None,
    engineering_index_entry_ids: list[int],
    now: datetime,
    allow_cross_document_evidence: bool = False,
) -> ProposedClaim:
    """
    Proposes a new claim from one or more Engineering Index entries.
    Every entry is validated once, before anything is built or
    persisted: unknown entries raise ``EvidenceEntryNotFoundError``,
    entries whose document is not PROJECT-scoped or whose Project is not
    mutable raise ``DocumentNotClaimableError``/``ProjectNotClaimableError``,
    evidence from more than one project raises
    ``CrossProjectEvidenceError``, and evidence from more than one
    document raises ``CrossDocumentEvidenceNotAllowedError`` unless
    ``allow_cross_document_evidence`` is set. Raises
    ``DuplicateProposedClaimError`` if this exact statement has already
    been proposed in this project.
    """

    project_id, evidence = _resolve_evidence(
        engineering_index_repository,
        document_lookup,
        engineering_index_entry_ids,
        allow_cross_document_evidence=allow_cross_document_evidence,
    )

    subject_value = ClaimSubject(value=subject)
    predicate_value = (
        ClaimPredicate(value=predicate) if predicate is not None else None
    )
    object_value = (
        ClaimObject(value=object_) if object_ is not None else None
    )

    duplicate = claim_repository.find_duplicate(
        project_id,
        claim_type,
        subject_value,
        predicate_value,
        object_value,
    )
    if duplicate is not None:
        raise DuplicateProposedClaimError(
            project_id,
            claim_type,
            subject,
        )

    claim = ProposedClaimFactory.create(
        project_id=project_id,
        claim_type=claim_type,
        subject=subject_value,
        predicate=predicate_value,
        object_=object_value,
        evidence=evidence,
        now=now,
    )

    return claim_repository.create(claim)


def get_proposed_claim(
    claim_repository: ProposedClaimRepository,
    claim_id: int,
) -> ProposedClaim:
    claim = claim_repository.get_by_id(claim_id)

    if claim is None:
        raise ProposedClaimNotFoundError(claim_id)

    return claim


def list_proposed_claims_for_project(
    claim_repository: ProposedClaimRepository,
    project_id: int,
) -> list[ProposedClaim]:
    return claim_repository.list_by_project(project_id)


def list_proposed_claims_for_document(
    claim_repository: ProposedClaimRepository,
    document_id: int,
) -> list[ProposedClaim]:
    return claim_repository.list_by_document(document_id)


def replace_claim_evidence(
    claim_repository: ProposedClaimRepository,
    engineering_index_repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    claim_id: int,
    engineering_index_entry_ids: list[int],
    now: datetime,
    allow_cross_document_evidence: bool = False,
) -> ProposedClaim:
    """
    Atomically replaces every evidence reference for an existing claim.
    The claim's own project is fixed: new evidence must belong to the
    same project the claim was proposed in, or
    ``CrossProjectEvidenceError`` is raised - a claim cannot be moved
    between projects by replacing its evidence.
    """

    claim = claim_repository.get_by_id(claim_id)

    if claim is None:
        raise ProposedClaimNotFoundError(claim_id)

    evidence_project_id, evidence = _resolve_evidence(
        engineering_index_repository,
        document_lookup,
        engineering_index_entry_ids,
        allow_cross_document_evidence=allow_cross_document_evidence,
    )

    if evidence_project_id != claim.project_id:
        raise CrossProjectEvidenceError(
            frozenset({claim.project_id, evidence_project_id})
        )

    updated = ProposedClaimFactory.with_evidence(claim, evidence, now)

    return claim_repository.replace_evidence(
        claim_id,
        list(updated.evidence),
    )


def delete_proposed_claim(
    claim_repository: ProposedClaimRepository,
    claim_id: int,
) -> None:
    if claim_repository.get_by_id(claim_id) is None:
        raise ProposedClaimNotFoundError(claim_id)

    claim_repository.delete(claim_id)
