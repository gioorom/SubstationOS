from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.canonicalization.canonicalization_factory import (
    CanonicalizationFactory,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_factory import (
    EvidenceReferenceFactory,
    ProposedClaimFactory,
)
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimSubject,
)
from app.infrastructure.canonicalization.sqlalchemy_canonical_fact_repository import (
    SqlAlchemyCanonicalFactRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.proposed_claims.sqlalchemy_proposed_claim_repository import (
    SqlAlchemyProposedClaimRepository,
)
from app.infrastructure.review_workflow.sqlalchemy_review_candidate_repository import (
    SqlAlchemyReviewCandidateRepository,
)
from app.infrastructure.review_workflow.sqlalchemy_review_history_repository import (
    SqlAlchemyReviewHistoryRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.services import review_workflow_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
APPROVED_AT = datetime(2026, 1, 2, 9, 0, 0)


def _persist_approved_relationship_fact_inputs(
    db_session: Session,
) -> tuple[int, int, int]:
    """Persists Project -> Document -> Engineering Index entries ->
    Proposed Claim -> approved Review Candidate, and returns
    ``(project_id, claim_id, approved_candidate_id)``."""

    project = ProjectRecord(
        name="Alpha Substation",
        code="ALPHA-001",
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
    entry = index_repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=project.id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="C-295",
            created_at=CREATED_AT,
        )
    )

    claim_repository = SqlAlchemyProposedClaimRepository(db_session)
    claim = claim_repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="Cable 295"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(entry),
            ),
            now=CREATED_AT,
        )
    )

    candidate_repository = SqlAlchemyReviewCandidateRepository(db_session)
    history_repository = SqlAlchemyReviewHistoryRepository(db_session)
    project_repository = SqlAlchemyProjectRepository(db_session)

    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=claim.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    approved = review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer.smith",
        now=APPROVED_AT,
    )

    return project.id, claim.id, approved.id  # type: ignore[return-value]


def test_save_persists_a_fact_with_its_evidence(
    db_session: Session,
) -> None:
    project_id, claim_id, candidate_id = (
        _persist_approved_relationship_fact_inputs(db_session)
    )
    claim = SqlAlchemyProposedClaimRepository(db_session).get_by_id(
        claim_id
    )
    candidate = SqlAlchemyReviewCandidateRepository(
        db_session
    ).get_by_id(candidate_id)
    fact = CanonicalizationFactory.canonicalize_claim(
        claim=claim,  # type: ignore[arg-type]
        candidate=candidate,  # type: ignore[arg-type]
        now=APPROVED_AT,
    )

    repository = SqlAlchemyCanonicalFactRepository(db_session)
    saved = repository.save(fact)

    assert saved.id is not None
    assert saved.subject.value == "CABLE:C-295"
    assert len(saved.evidence) == 1
    assert saved.reviewed_by == "engineer.smith"


def test_get_by_review_candidate_returns_the_persisted_fact(
    db_session: Session,
) -> None:
    project_id, claim_id, candidate_id = (
        _persist_approved_relationship_fact_inputs(db_session)
    )
    claim = SqlAlchemyProposedClaimRepository(db_session).get_by_id(
        claim_id
    )
    candidate = SqlAlchemyReviewCandidateRepository(
        db_session
    ).get_by_id(candidate_id)
    repository = SqlAlchemyCanonicalFactRepository(db_session)
    repository.save(
        CanonicalizationFactory.canonicalize_claim(
            claim=claim,  # type: ignore[arg-type]
            candidate=candidate,  # type: ignore[arg-type]
            now=APPROVED_AT,
        )
    )

    found = repository.get_by_review_candidate(candidate_id)

    assert found is not None
    assert found.review_candidate_id == candidate_id


def test_get_by_review_candidate_returns_none_when_absent(
    db_session: Session,
) -> None:
    repository = SqlAlchemyCanonicalFactRepository(db_session)

    assert repository.get_by_review_candidate(999) is None


def test_list_by_project_and_list_by_document(
    db_session: Session,
) -> None:
    project_id, claim_id, candidate_id = (
        _persist_approved_relationship_fact_inputs(db_session)
    )
    claim = SqlAlchemyProposedClaimRepository(db_session).get_by_id(
        claim_id
    )
    candidate = SqlAlchemyReviewCandidateRepository(
        db_session
    ).get_by_id(candidate_id)
    repository = SqlAlchemyCanonicalFactRepository(db_session)
    repository.save(
        CanonicalizationFactory.canonicalize_claim(
            claim=claim,  # type: ignore[arg-type]
            candidate=candidate,  # type: ignore[arg-type]
            now=APPROVED_AT,
        )
    )

    by_project = repository.list_by_project(project_id)
    document_id = claim.evidence[0].document_id  # type: ignore[union-attr]
    by_document = repository.list_by_document(document_id)

    assert len(by_project) == 1
    assert len(by_document) == 1
    assert by_project[0].id == by_document[0].id
