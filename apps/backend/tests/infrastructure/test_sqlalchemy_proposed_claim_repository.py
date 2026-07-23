from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_exceptions import (
    DuplicateEvidenceError,
    DuplicateProposedClaimError,
)
from app.domain.proposed_claims.proposed_claim_factory import (
    EvidenceReferenceFactory,
    ProposedClaimFactory,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.proposed_claims.sqlalchemy_proposed_claim_repository import (
    SqlAlchemyProposedClaimRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project_and_entries(
    db_session: Session,
    *,
    code: str = "ALPHA-001",
    identifiers: tuple[str, ...] = ("C-295", "TR-02"),
) -> tuple[ProjectRecord, DocumentRecord, list]:
    project = ProjectRecord(
        name="Alpha Substation",
        code=code,
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    document = DocumentRecord(
        filename="functional-schematic.pdf",
        file_path="/tmp/functional-schematic.pdf",
        project_id=project.id,
        project_name=project.name,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    index_repository = SqlAlchemyEngineeringIndexRepository(db_session)
    entries = [
        index_repository.save(
            EngineeringIndexEntryFactory.create(
                project_id=project.id,
                document_id=document.id,
                kind=EngineeringIndexEntryKind.EQUIPMENT,
                identifier=identifier,
                created_at=CREATED_AT,
            )
        )
        for identifier in identifiers
    ]

    return project, document, entries


def test_create_persists_a_claim_with_its_evidence(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(db_session)
    repository = SqlAlchemyProposedClaimRepository(db_session)

    claim = repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.RELATIONSHIP,
            subject=ClaimSubject(value="Cable C-295"),
            predicate=ClaimPredicate(value="FEEDS"),
            object_=ClaimObject(value="Transformer TR-02"),
            evidence=tuple(
                EvidenceReferenceFactory.from_index_entry(entry)
                for entry in entries
            ),
            now=CREATED_AT,
        )
    )

    assert claim.id is not None
    assert len(claim.evidence) == 2
    assert {
        reference.engineering_index_entry_id
        for reference in claim.evidence
    } == {entry.id for entry in entries}


def test_create_rejects_a_duplicate_natural_key(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(db_session)
    repository = SqlAlchemyProposedClaimRepository(db_session)

    def _build():
        return ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.RELATIONSHIP,
            subject=ClaimSubject(value="Cable C-295"),
            predicate=ClaimPredicate(value="FEEDS"),
            object_=ClaimObject(value="Transformer TR-02"),
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )

    repository.create(_build())

    with pytest.raises(DuplicateProposedClaimError):
        repository.create(_build())


def test_get_by_id_returns_none_for_a_missing_claim(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProposedClaimRepository(db_session)

    assert repository.get_by_id(999) is None


def test_find_duplicate_returns_the_matching_claim(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(db_session)
    repository = SqlAlchemyProposedClaimRepository(db_session)

    subject = ClaimSubject(value="Transformer TR-02")
    repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=subject,
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )
    )

    found = repository.find_duplicate(
        project.id,
        ClaimType.EXISTENCE,
        subject,
        None,
        None,
    )

    assert found is not None
    assert found.subject == subject


def test_find_duplicate_returns_none_when_nothing_matches(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProposedClaimRepository(db_session)

    found = repository.find_duplicate(
        1,
        ClaimType.EXISTENCE,
        ClaimSubject(value="Transformer TR-02"),
        None,
        None,
    )

    assert found is None


def test_list_by_project_returns_only_that_projects_claims(
    db_session: Session,
) -> None:
    project_a, _, entries_a = _persist_project_and_entries(
        db_session,
        code="ALPHA-001",
        identifiers=("T1",),
    )
    project_b, _, entries_b = _persist_project_and_entries(
        db_session,
        code="ALPHA-002",
        identifiers=("T2",),
    )
    repository = SqlAlchemyProposedClaimRepository(db_session)

    repository.create(
        ProposedClaimFactory.create(
            project_id=project_a.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries_a[0]),
            ),
            now=CREATED_AT,
        )
    )
    repository.create(
        ProposedClaimFactory.create(
            project_id=project_b.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T2"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries_b[0]),
            ),
            now=CREATED_AT,
        )
    )

    claims_a = repository.list_by_project(project_a.id)

    assert len(claims_a) == 1
    assert claims_a[0].subject == ClaimSubject(value="T1")


def test_list_by_document_returns_claims_citing_that_document(
    db_session: Session,
) -> None:
    project, document, entries = _persist_project_and_entries(
        db_session,
        identifiers=("T1",),
    )
    repository = SqlAlchemyProposedClaimRepository(db_session)

    repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )
    )

    claims = repository.list_by_document(document.id)
    other_document_claims = repository.list_by_document(999)

    assert len(claims) == 1
    assert other_document_claims == []


def test_replace_evidence_swaps_in_new_references(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(
        db_session,
        identifiers=("T1", "T2"),
    )
    repository = SqlAlchemyProposedClaimRepository(db_session)

    claim = repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )
    )

    updated = repository.replace_evidence(
        claim.id,  # type: ignore[arg-type]
        [EvidenceReferenceFactory.from_index_entry(entries[1])],
    )

    assert [
        reference.engineering_index_entry_id
        for reference in updated.evidence
    ] == [entries[1].id]


def test_replace_evidence_rolls_back_on_a_duplicate_within_the_batch(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(
        db_session,
        identifiers=("T1", "T2"),
    )
    repository = SqlAlchemyProposedClaimRepository(db_session)

    claim = repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )
    )

    duplicate_reference = EvidenceReferenceFactory.from_index_entry(
        entries[1]
    )

    with pytest.raises(DuplicateEvidenceError):
        repository.replace_evidence(
            claim.id,  # type: ignore[arg-type]
            [duplicate_reference, duplicate_reference],
        )

    reloaded = repository.get_by_id(claim.id)  # type: ignore[arg-type]

    assert reloaded is not None
    assert [
        reference.engineering_index_entry_id
        for reference in reloaded.evidence
    ] == [entries[0].id]


def test_delete_removes_the_claim_and_its_evidence(
    db_session: Session,
) -> None:
    project, _, entries = _persist_project_and_entries(
        db_session,
        identifiers=("T1",),
    )
    repository = SqlAlchemyProposedClaimRepository(db_session)

    claim = repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entries[0]),
            ),
            now=CREATED_AT,
        )
    )

    repository.delete(claim.id)  # type: ignore[arg-type]

    assert repository.get_by_id(claim.id) is None  # type: ignore[arg-type]
