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
    ReviewHistoryEventFactory,
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
from app.infrastructure.review_workflow.sqlalchemy_review_history_repository import (
    SqlAlchemyReviewHistoryRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_candidate(db_session: Session) -> int:
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

    candidate_repository = SqlAlchemyReviewCandidateRepository(db_session)
    candidate = candidate_repository.create(
        ReviewCandidateFactory.create(
            project_id=project.id,
            proposed_claim_id=claim.id,  # type: ignore[arg-type]
            now=CREATED_AT,
        )
    )

    return candidate.id  # type: ignore[return-value]


def test_append_persists_an_event_and_assigns_an_id(
    db_session: Session,
) -> None:
    candidate_id = _persist_candidate(db_session)
    repository = SqlAlchemyReviewHistoryRepository(db_session)

    event = repository.append(
        ReviewHistoryEventFactory.create(
            review_candidate_id=candidate_id,
            from_status=ReviewStatus.PENDING,
            decision=ReviewDecisionFactory.create(
                status=ReviewStatus.NEEDS_CHANGES,
                reviewed_by="engineer@acme.com",
                comment="Please confirm the rated voltage.",
            ),
            occurred_at=CREATED_AT,
        )
    )

    assert event.id is not None
    assert event.to_status is ReviewStatus.NEEDS_CHANGES
    assert (
        event.comment is not None
        and event.comment.text == "Please confirm the rated voltage."
    )


def test_list_by_candidate_returns_events_in_chronological_order(
    db_session: Session,
) -> None:
    candidate_id = _persist_candidate(db_session)
    repository = SqlAlchemyReviewHistoryRepository(db_session)

    first_at = datetime(2026, 1, 2, 9, 0, 0)
    second_at = datetime(2026, 1, 3, 9, 0, 0)

    repository.append(
        ReviewHistoryEventFactory.create(
            review_candidate_id=candidate_id,
            from_status=ReviewStatus.PENDING,
            decision=ReviewDecisionFactory.create(
                status=ReviewStatus.NEEDS_CHANGES,
                reviewed_by="engineer@acme.com",
                comment="Please confirm the rated voltage.",
            ),
            occurred_at=first_at,
        )
    )
    repository.append(
        ReviewHistoryEventFactory.create(
            review_candidate_id=candidate_id,
            from_status=ReviewStatus.NEEDS_CHANGES,
            decision=ReviewDecisionFactory.create(
                status=ReviewStatus.APPROVED,
                reviewed_by="lead-engineer@acme.com",
            ),
            occurred_at=second_at,
        )
    )

    events = repository.list_by_candidate(candidate_id)

    assert [event.to_status for event in events] == [
        ReviewStatus.NEEDS_CHANGES,
        ReviewStatus.APPROVED,
    ]
    assert [event.occurred_at for event in events] == [
        first_at,
        second_at,
    ]


def test_list_by_candidate_returns_nothing_for_an_unknown_candidate(
    db_session: Session,
) -> None:
    repository = SqlAlchemyReviewHistoryRepository(db_session)

    assert repository.list_by_candidate(999) == []
