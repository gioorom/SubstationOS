from __future__ import annotations

import pytest

from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    ClaimObjectRequiredError,
    ClaimPredicateRequiredError,
    CrossDocumentEvidenceNotAllowedError,
    CrossProjectEvidenceError,
    DuplicateEvidenceError,
    EmptyEvidenceError,
    InvalidClaimObjectError,
    InvalidClaimPredicateError,
    InvalidClaimSubjectError,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
)
from app.domain.proposed_claims.proposed_claim_validator import (
    ProposedClaimValidator,
)

_LOCATOR = IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value=None)


def _evidence(entry_id: int, document_id: int = 1) -> EvidenceReference:
    return EvidenceReference(
        engineering_index_entry_id=entry_id,
        document_id=document_id,
        locator=_LOCATOR,
    )


@pytest.mark.parametrize("value", ["", "   "])
def test_validate_subject_rejects_blank_values(value: str) -> None:
    with pytest.raises(InvalidClaimSubjectError):
        ProposedClaimValidator.validate_subject(ClaimSubject(value=value))


def test_validate_subject_accepts_real_text() -> None:
    ProposedClaimValidator.validate_subject(ClaimSubject(value="Cable C-295"))


def test_validate_predicate_accepts_none() -> None:
    ProposedClaimValidator.validate_predicate(None)


def test_validate_predicate_rejects_blank_text() -> None:
    with pytest.raises(InvalidClaimPredicateError):
        ProposedClaimValidator.validate_predicate(ClaimPredicate(value="  "))


def test_validate_object_accepts_none() -> None:
    ProposedClaimValidator.validate_object(None)


def test_validate_object_rejects_blank_text() -> None:
    with pytest.raises(InvalidClaimObjectError):
        ProposedClaimValidator.validate_object(ClaimObject(value="  "))


def test_validate_shape_accepts_existence_with_no_predicate_or_object() -> (
    None
):
    ProposedClaimValidator.validate_shape(ClaimType.EXISTENCE, None, None)


def test_validate_shape_rejects_relationship_with_no_predicate() -> None:
    with pytest.raises(ClaimPredicateRequiredError):
        ProposedClaimValidator.validate_shape(
            ClaimType.RELATIONSHIP,
            None,
            ClaimObject(value="Transformer TR-02"),
        )


def test_validate_shape_rejects_attribute_with_no_object() -> None:
    with pytest.raises(ClaimObjectRequiredError):
        ProposedClaimValidator.validate_shape(
            ClaimType.ATTRIBUTE,
            ClaimPredicate(value="rated_voltage"),
            None,
        )


def test_validate_shape_accepts_a_complete_relationship() -> None:
    ProposedClaimValidator.validate_shape(
        ClaimType.RELATIONSHIP,
        ClaimPredicate(value="FEEDS"),
        ClaimObject(value="Transformer TR-02"),
    )


def test_validate_evidence_not_empty_rejects_an_empty_tuple() -> None:
    with pytest.raises(EmptyEvidenceError):
        ProposedClaimValidator.validate_evidence_not_empty(())


def test_validate_evidence_not_empty_accepts_at_least_one_reference() -> (
    None
):
    ProposedClaimValidator.validate_evidence_not_empty((_evidence(1),))


def test_validate_no_duplicate_evidence_rejects_a_repeated_entry_id() -> (
    None
):
    with pytest.raises(DuplicateEvidenceError):
        ProposedClaimValidator.validate_no_duplicate_evidence(
            (_evidence(1), _evidence(1))
        )


def test_validate_no_duplicate_evidence_accepts_distinct_entry_ids() -> (
    None
):
    ProposedClaimValidator.validate_no_duplicate_evidence(
        (_evidence(1), _evidence(2))
    )


def test_validate_evidence_same_project_accepts_a_single_project() -> None:
    ProposedClaimValidator.validate_evidence_same_project([10, 10, 10])


def test_validate_evidence_same_project_rejects_more_than_one_project() -> (
    None
):
    with pytest.raises(CrossProjectEvidenceError):
        ProposedClaimValidator.validate_evidence_same_project([10, 20])


def test_validate_evidence_documents_accepts_one_document() -> None:
    ProposedClaimValidator.validate_evidence_documents(
        [1, 1],
        allow_cross_document_evidence=False,
    )


def test_validate_evidence_documents_rejects_multiple_documents_by_default() -> (
    None
):
    with pytest.raises(CrossDocumentEvidenceNotAllowedError):
        ProposedClaimValidator.validate_evidence_documents(
            [1, 2],
            allow_cross_document_evidence=False,
        )


def test_validate_evidence_documents_accepts_multiple_documents_when_allowed() -> (
    None
):
    ProposedClaimValidator.validate_evidence_documents(
        [1, 2],
        allow_cross_document_evidence=True,
    )
