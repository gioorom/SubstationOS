from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.review_workflow.review_history_repository import (
    ReviewHistoryRepository,
)
from app.domain.review_workflow.review_workflow_models import (
    ReviewComment,
    ReviewHistoryEvent,
)
from app.models.review_workflow import ReviewHistoryEventRecord


class SqlAlchemyReviewHistoryRepository(ReviewHistoryRepository):
    """
    SQLAlchemy adapter for the ``ReviewHistoryRepository`` port, backed
    by ``app.models.review_workflow.ReviewHistoryEventRecord``. Only
    ever inserts - never updates or deletes a row, matching the port's
    append-only contract.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: ReviewHistoryEvent) -> ReviewHistoryEvent:
        record = ReviewHistoryEventRecord(
            review_candidate_id=event.review_candidate_id,
            from_status=event.from_status,
            to_status=event.to_status,
            reviewed_by=event.reviewed_by,
            comment=(
                event.comment.text if event.comment is not None else None
            ),
            occurred_at=event.occurred_at,
        )

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def list_by_candidate(
        self,
        review_candidate_id: int,
    ) -> list[ReviewHistoryEvent]:
        records = (
            self._session.query(ReviewHistoryEventRecord)
            .filter(
                ReviewHistoryEventRecord.review_candidate_id
                == review_candidate_id
            )
            .order_by(ReviewHistoryEventRecord.occurred_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_domain(
        record: ReviewHistoryEventRecord,
    ) -> ReviewHistoryEvent:
        return ReviewHistoryEvent(
            id=record.id,
            review_candidate_id=record.review_candidate_id,
            from_status=record.from_status,
            to_status=record.to_status,
            reviewed_by=record.reviewed_by,
            comment=(
                ReviewComment(text=record.comment)
                if record.comment is not None
                else None
            ),
            occurred_at=record.occurred_at,
        )
