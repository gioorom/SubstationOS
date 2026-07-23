from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_factory import (
    EvidenceReferenceFactory,
    ProposedClaimFactory,
)
from app.domain.proposed_claims.proposed_claim_models import ClaimSubject
from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_factory import (
    ReviewCandidateFactory,
    ReviewDecisionFactory,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.proposed_claims.sqlalchemy_proposed_claim_repository import (
    SqlAlchemyProposedClaimRepository,
)
from app.infrastructure.review_workflow.sqlalchemy_review_candidate_repository import (
    SqlAlchemyReviewCandidateRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project_document_and_claim(
    db_session: Session,
    *,
    code: str = "ALPHA-001",
) -> tuple[ProjectRecord, DocumentRecord, int]:
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
    entry = index_repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=project.id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )

    claim_repository = SqlAlchemyProposedClaimRepository(db_session)
    claim = claim_repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="T1"),
            predicate=None,
            object_=None,
            evidence=(EvidenceReferenceFactory.from_index_entry(entry),),
            now=CREATED_AT,
        )
    )

    return project, document, claim.id  # type: ignore[return-value]


def test_create_persists_a_new_candidate_and_assigns_an_id(
    db_session: Session,
) -> None:
    project, _, claim_id = _persist_project_document_and_claim(db_session)
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    candidate = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )

    assert candidate.id is not None
    assert candidate.status is ReviewStatus.PENDING


def test_get_by_id_returns_none_for_a_missing_candidate(
    db_session: Session,
) -> None:
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    assert repository.get_by_id(999) is None


def test_update_persists_a_new_status_and_reviewer(
    db_session: Session,
) -> None:
    project, _, claim_id = _persist_project_document_and_claim(db_session)
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    candidate = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )

    decided_at = datetime(2026, 1, 2, 9, 0, 0)
    updated = ReviewCandidateFactory.apply_decision(
        candidate,
        ReviewDecisionFactory.create(
            status=ReviewStatus.APPROVED,
            reviewed_by="engineer@acme.com",
        ),
        decided_at,
    )

    persisted = repository.update(updated)
    reloaded = repository.get_by_id(candidate.id)  # type: ignore[arg-type]

    assert persisted.status is ReviewStatus.APPROVED
    assert reloaded is not None
    assert reloaded.status is ReviewStatus.APPROVED
    assert reloaded.reviewed_by == "engineer@acme.com"
    assert reloaded.reviewed_at == decided_at


def test_get_open_by_claim_returns_a_pending_candidate(
    db_session: Session,
) -> None:
    project, _, claim_id = _persist_project_document_and_claim(db_session)
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    created = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )

    found = repository.get_open_by_claim(claim_id)

    assert found is not None
    assert found.id == created.id


def test_get_open_by_claim_returns_none_once_the_candidate_is_terminal(
    db_session: Session,
) -> None:
    project, _, claim_id = _persist_project_document_and_claim(db_session)
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    candidate = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )
    repository.update(
        ReviewCandidateFactory.apply_decision(
            candidate,
            ReviewDecisionFactory.create(
                status=ReviewStatus.APPROVED,
                reviewed_by="engineer@acme.com",
            ),
            CREATED_AT,
        )
    )

    assert repository.get_open_by_claim(claim_id) is None


def test_list_pending_returns_only_pending_candidates(
    db_session: Session,
) -> None:
    project, document, claim_id = _persist_project_document_and_claim(
        db_session
    )
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    pending_candidate = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )

    index_repository = SqlAlchemyEngineeringIndexRepository(db_session)
    second_entry = index_repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=project.id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.CABLE,
            identifier="W-152",
            created_at=CREATED_AT,
        )
    )
    claim_repository = SqlAlchemyProposedClaimRepository(db_session)
    second_claim = claim_repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="W-152"),
            predicate=None,
            object_=None,
            evidence=(
                EvidenceReferenceFactory.from_index_entry(second_entry),
            ),
            now=CREATED_AT,
        )
    )
    approved_candidate = repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=second_claim.id,  # type: ignore[arg-type]
            now=CREATED_AT,
        )
    )
    repository.update(
        ReviewCandidateFactory.apply_decision(
            approved_candidate,
            ReviewDecisionFactory.create(
                status=ReviewStatus.APPROVED,
                reviewed_by="engineer@acme.com",
            ),
            CREATED_AT,
        )
    )

    pending = repository.list_pending()

    assert [candidate.id for candidate in pending] == [
        pending_candidate.id
    ]


def test_list_by_project_filters_by_status(db_session: Session) -> None:
    project, _, claim_id = _persist_project_document_and_claim(db_session)
    repository = SqlAlchemyReviewCandidateRepository(db_session)

    repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim_id,
            now=CREATED_AT,
        )
    )

    pending_only = repository.list_by_project(
        project.id,
        status=ReviewStatus.PENDING,
    )
    approved_only = repository.list_by_project(
        project.id,
        status=ReviewStatus.APPROVED,
    )

    assert len(pending_only) == 1
    assert approved_only == []
