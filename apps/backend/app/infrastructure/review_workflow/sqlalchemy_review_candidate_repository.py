from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.review_workflow.review_candidate_repository import (
    ReviewCandidateRepository,
)
from app.domain.review_workflow.review_status import (
    OPEN_STATUSES,
    ReviewStatus,
)
from app.domain.review_workflow.review_workflow_exceptions import (
    ReviewCandidateNotFoundError,
)
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
    ReviewComment,
)
from app.models.review_workflow import (
    ReviewCandidateRecord,
)


class SqlAlchemyReviewCandidateRepository(ReviewCandidateRepository):
    """
    SQLAlchemy adapter for the ``ReviewCandidateRepository`` port,
    backed by ``app.models.review_workflow.ReviewCandidateRecord``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, candidate: ReviewCandidate) -> ReviewCandidate:
        record = ReviewCandidateRecord(
            project_id=candidate.project_id,
            proposed_claim_id=candidate.proposed_claim_id,
            status=candidate.status,
            review_comment=(
                candidate.review_comment.text
                if candidate.review_comment is not None
                else None
            ),
            reviewed_by=candidate.reviewed_by,
            reviewed_at=candidate.reviewed_at,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
        )

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def update(self, candidate: ReviewCandidate) -> ReviewCandidate:
        record = self._session.get(
            ReviewCandidateRecord,
            candidate.id,
        )

        if record is None:
            raise ReviewCandidateNotFoundError(candidate.id)  # type: ignore[arg-type]

        record.project_id = candidate.project_id
        record.proposed_claim_id = candidate.proposed_claim_id
        record.status = candidate.status
        record.review_comment = (
            candidate.review_comment.text
            if candidate.review_comment is not None
            else None
        )
        record.reviewed_by = candidate.reviewed_by
        record.reviewed_at = candidate.reviewed_at
        record.created_at = candidate.created_at
        record.updated_at = candidate.updated_at

        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, candidate_id: int) -> ReviewCandidate | None:
        record = self._session.get(ReviewCandidateRecord, candidate_id)

        return self._to_domain(record) if record is not None else None

    def get_open_by_claim(
        self,
        proposed_claim_id: int,
    ) -> ReviewCandidate | None:
        record = (
            self._session.query(ReviewCandidateRecord)
            .filter(
                ReviewCandidateRecord.proposed_claim_id
                == proposed_claim_id,
                ReviewCandidateRecord.status.in_(
                    [status.value for status in OPEN_STATUSES]
                ),
            )
            .first()
        )

        return self._to_domain(record) if record is not None else None

    def list_pending(self) -> list[ReviewCandidate]:
        records = (
            self._session.query(ReviewCandidateRecord)
            .filter(
                ReviewCandidateRecord.status == ReviewStatus.PENDING
            )
            .order_by(ReviewCandidateRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def list_by_project(
        self,
        project_id: int,
        *,
        status: ReviewStatus | None = None,
    ) -> list[ReviewCandidate]:
        query = self._session.query(ReviewCandidateRecord).filter(
            ReviewCandidateRecord.project_id == project_id
        )

        if status is not None:
            query = query.filter(ReviewCandidateRecord.status == status)

        records = query.order_by(
            ReviewCandidateRecord.created_at.asc()
        ).all()

        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_domain(record: ReviewCandidateRecord) -> ReviewCandidate:
        return ReviewCandidate(
            id=record.id,
            project_id=record.project_id,
            proposed_claim_id=record.proposed_claim_id,
            status=record.status,
            review_comment=(
                ReviewComment(text=record.review_comment)
                if record.review_comment is not None
                else None
            ),
            reviewed_by=record.reviewed_by,
            reviewed_at=record.reviewed_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
