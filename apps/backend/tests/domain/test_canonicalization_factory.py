from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.canonicalization.canonicalization_exceptions import (
    CrossProjectCanonicalizationError,
    ReviewCandidateNotApprovedError,
)
from app.domain.canonicalization.canonicalization_factory import (
    CanonicalizationFactory,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
REVIEWED_AT = datetime(2026, 1, 2, 9, 0, 0)


def _evidence() -> tuple[EvidenceReference, ...]:
    return (
        EvidenceReference(
            engineering_index_entry_id=1,
            document_id=5,
            locator=IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE,
                value="3",
            ),
        ),
    )


def _claim(
    *,
    project_id: int = 10,
    claim_type: ClaimType = ClaimType.RELATIONSHIP,
    subject: str = "Cable 295",
    predicate: str | None = "feeds",
    object_: str | None = "Transformer 2",
) -> ProposedClaim:
    return ProposedClaim(
        id=1,
        project_id=project_id,
        claim_type=claim_type,
        subject=ClaimSubject(value=subject),
        predicate=(
            ClaimPredicate(value=predicate)
            if predicate is not None
            else None
        ),
        object=(
            ClaimObject(value=object_) if object_ is not None else None
        ),
        evidence=_evidence(),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _candidate(
    *,
    project_id: int = 10,
    status: ReviewStatus = ReviewStatus.APPROVED,
    reviewed_by: str | None = "engineer.smith",
    reviewed_at: datetime | None = REVIEWED_AT,
) -> ReviewCandidate:
    return ReviewCandidate(
        id=1,
        project_id=project_id,
        proposed_claim_id=1,
        status=status,
        review_comment=None,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        created_at=CREATED_AT,
        updated_at=REVIEWED_AT,
    )


def test_canonicalize_a_relationship_claim() -> None:
    fact = CanonicalizationFactory.canonicalize_claim(
        claim=_claim(),
        candidate=_candidate(),
        now=REVIEWED_AT,
    )

    assert fact.subject.value == "CABLE:C-295"
    assert fact.predicate_value == "FEEDS"
    assert fact.object_entity is not None
    assert fact.object_entity.value == "TRANSFORMER:TR-02"
    assert fact.object_value is None
    assert fact.reviewed_by == "engineer.smith"
    assert fact.reviewed_at == REVIEWED_AT
    assert fact.evidence == _evidence()


def test_canonicalize_an_attribute_claim() -> None:
    claim = _claim(
        claim_type=ClaimType.ATTRIBUTE,
        subject="Transformer 2",
        predicate="Rated Voltage",
        object_="132kV",
    )

    fact = CanonicalizationFactory.canonicalize_claim(
        claim=claim,
        candidate=_candidate(),
        now=REVIEWED_AT,
    )

    assert fact.subject.value == "TRANSFORMER:TR-02"
    assert fact.predicate_value == "rated_voltage"
    assert fact.object_entity is None
    assert fact.object_value == "132kV"


def test_canonicalize_an_existence_claim() -> None:
    claim = _claim(
        claim_type=ClaimType.EXISTENCE,
        subject="TR2",
        predicate=None,
        object_=None,
    )

    fact = CanonicalizationFactory.canonicalize_claim(
        claim=claim,
        candidate=_candidate(),
        now=REVIEWED_AT,
    )

    assert fact.subject.value == "TRANSFORMER:TR-02"
    assert fact.predicate_value is None
    assert fact.object_entity is None
    assert fact.object_value is None


def test_canonicalize_rejects_a_non_approved_candidate() -> None:
    with pytest.raises(ReviewCandidateNotApprovedError):
        CanonicalizationFactory.canonicalize_claim(
            claim=_claim(),
            candidate=_candidate(status=ReviewStatus.PENDING),
            now=REVIEWED_AT,
        )


def test_canonicalize_rejects_a_cross_project_mismatch() -> None:
    with pytest.raises(CrossProjectCanonicalizationError):
        CanonicalizationFactory.canonicalize_claim(
            claim=_claim(project_id=10),
            candidate=_candidate(project_id=20),
            now=REVIEWED_AT,
        )
