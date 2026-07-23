from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    ClaimPredicateRequiredError,
    DuplicateEvidenceError,
    EmptyEvidenceError,
    InvalidClaimSubjectError,
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
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
_LOCATOR = IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value="3")


def _evidence(entry_id: int) -> EvidenceReference:
    return EvidenceReference(
        engineering_index_entry_id=entry_id,
        document_id=1,
        locator=_LOCATOR,
    )


def test_create_builds_an_unpersisted_claim() -> None:
    claim = ProposedClaimFactory.create(
        project_id=10,
        claim_type=ClaimType.RELATIONSHIP,
        subject=ClaimSubject(value="Cable C-295"),
        predicate=ClaimPredicate(value="FEEDS"),
        object_=ClaimObject(value="Transformer TR-02"),
        evidence=(_evidence(1), _evidence(2)),
        now=CREATED_AT,
    )

    assert claim.id is None
    assert claim.project_id == 10
    assert claim.claim_type is ClaimType.RELATIONSHIP
    assert claim.subject == ClaimSubject(value="Cable C-295")
    assert claim.predicate == ClaimPredicate(value="FEEDS")
    assert claim.object == ClaimObject(value="Transformer TR-02")
    assert len(claim.evidence) == 2
    assert claim.created_at == CREATED_AT
    assert claim.updated_at == CREATED_AT


def test_create_accepts_an_existence_claim_with_no_predicate_or_object() -> (
    None
):
    claim = ProposedClaimFactory.create(
        project_id=10,
        claim_type=ClaimType.EXISTENCE,
        subject=ClaimSubject(value="Transformer TR-02"),
        predicate=None,
        object_=None,
        evidence=(_evidence(1),),
        now=CREATED_AT,
    )

    assert claim.predicate is None
    assert claim.object is None


def test_create_rejects_a_blank_subject() -> None:
    with pytest.raises(InvalidClaimSubjectError):
        ProposedClaimFactory.create(
            project_id=10,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="   "),
            predicate=None,
            object_=None,
            evidence=(_evidence(1),),
            now=CREATED_AT,
        )


def test_create_rejects_a_relationship_with_no_predicate() -> None:
    with pytest.raises(ClaimPredicateRequiredError):
        ProposedClaimFactory.create(
            project_id=10,
            claim_type=ClaimType.RELATIONSHIP,
            subject=ClaimSubject(value="Cable C-295"),
            predicate=None,
            object_=ClaimObject(value="Transformer TR-02"),
            evidence=(_evidence(1),),
            now=CREATED_AT,
        )


def test_create_rejects_empty_evidence() -> None:
    with pytest.raises(EmptyEvidenceError):
        ProposedClaimFactory.create(
            project_id=10,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="Transformer TR-02"),
            predicate=None,
            object_=None,
            evidence=(),
            now=CREATED_AT,
        )


def test_create_rejects_duplicate_evidence() -> None:
    with pytest.raises(DuplicateEvidenceError):
        ProposedClaimFactory.create(
            project_id=10,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="Transformer TR-02"),
            predicate=None,
            object_=None,
            evidence=(_evidence(1), _evidence(1)),
            now=CREATED_AT,
        )


def test_with_evidence_replaces_evidence_without_mutating_the_original() -> (
    None
):
    claim = ProposedClaimFactory.create(
        project_id=10,
        claim_type=ClaimType.EXISTENCE,
        subject=ClaimSubject(value="Transformer TR-02"),
        predicate=None,
        object_=None,
        evidence=(_evidence(1),),
        now=CREATED_AT,
    )
    later = datetime(2026, 1, 2, 9, 0, 0)

    updated = ProposedClaimFactory.with_evidence(
        claim,
        (_evidence(2), _evidence(3)),
        later,
    )

    assert [
        reference.engineering_index_entry_id for reference in claim.evidence
    ] == [1]
    assert [
        reference.engineering_index_entry_id
        for reference in updated.evidence
    ] == [2, 3]
    assert updated.updated_at == later
    assert updated.created_at == CREATED_AT


def test_with_evidence_rejects_empty_evidence() -> None:
    claim = ProposedClaimFactory.create(
        project_id=10,
        claim_type=ClaimType.EXISTENCE,
        subject=ClaimSubject(value="Transformer TR-02"),
        predicate=None,
        object_=None,
        evidence=(_evidence(1),),
        now=CREATED_AT,
    )

    with pytest.raises(EmptyEvidenceError):
        ProposedClaimFactory.with_evidence(claim, (), CREATED_AT)


def test_evidence_reference_factory_snapshots_document_and_locator() -> (
    None
):
    entry = IndexEntry(
        id=5,
        project_id=10,
        document_id=7,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        locator=_LOCATOR,
        label=None,
        created_at=CREATED_AT,
    )

    reference = EvidenceReferenceFactory.from_index_entry(entry)

    assert reference.engineering_index_entry_id == 5
    assert reference.document_id == 7
    assert reference.locator == _LOCATOR
