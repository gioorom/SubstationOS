"""
SQLAlchemy adapter for the ``ReviewRepository`` port.

Writes ``engineering_reviews`` and nothing else. It never issues an
``UPDATE`` or a ``DELETE`` against that table - not because a rule says
so, but because the port declares no operation that would need one, and
an architecture test asserts this module contains neither statement.

It touches no engineering table. A review is appended by naming a key;
resolving that key to a statement is the application service's job, using
the engineering context's own repository.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.human_review.review_models import (
    Review,
    ReviewComment,
    ReviewerIdentity,
)
from app.domain.human_review.review_repository import ReviewRepository
from app.domain.human_review.review_snapshot import ReviewSnapshot
from app.domain.human_review.review_target import (
    ReviewTarget,
    ReviewTargetType,
)
from app.domain.human_review.review_vocabulary import (
    ReviewDecision,
    ReviewReason,
)
from app.domain.shared_kernel.pagination import Page, PageRequest
from app.models.human_review import ReviewRecord


class SqlAlchemyReviewRepository(ReviewRepository):
    """The default ``ReviewRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, review: Review) -> Review:
        record = ReviewRecord(
            target_type=review.target.target_type.value,
            target_key=review.target.target_key,
            document_id=review.target.document_id,
            decision=review.decision.value,
            reason=review.reason.value,
            comment=None if review.comment is None else review.comment.text,
            reviewer_user_id=review.reviewer.user_id,
            reviewer_display_name=review.reviewer.display_name,
            reviewer_email=review.reviewer.email,
            reviewer_role=review.reviewer.role,
            recorded_at=review.recorded_at,
            record_version=review.record_version,
            content_checksum=review.snapshot.content_checksum,
            semantic_rule_id=review.snapshot.semantic_rule_id,
            semantic_rule_version=review.snapshot.semantic_rule_version,
            semantic_contract_version=(
                review.snapshot.semantic_contract_version
            ),
            resolution_policy_version=(
                review.snapshot.resolution_policy_version
            ),
            fact_policy_version=review.snapshot.fact_policy_version,
            semantic_policy_version=review.snapshot.semantic_policy_version,
            support_fingerprint=review.snapshot.support_fingerprint,
            support_count=review.snapshot.support_count,
        )

        self._session.add(record)
        self._session.commit()

        return _to_domain(record)

    def history_for(
        self, target: ReviewTarget, page: PageRequest
    ) -> Page[Review]:
        criteria = (
            ReviewRecord.document_id == target.document_id,
            ReviewRecord.target_key == target.target_key,
            ReviewRecord.target_type == target.target_type.value,
        )

        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(*criteria)
            )
            or 0
        )

        records = self._session.scalars(
            select(ReviewRecord)
            .where(*criteria)
            .order_by(*_newest_first())
            .offset(page.offset)
            .limit(page.limit)
        ).all()

        return Page.of(
            items=tuple(_to_domain(record) for record in records),
            total=total,
            request=page,
        )

    def latest_for(self, target: ReviewTarget) -> Review | None:
        record = self._session.scalar(
            select(ReviewRecord)
            .where(
                ReviewRecord.document_id == target.document_id,
                ReviewRecord.target_key == target.target_key,
                ReviewRecord.target_type == target.target_type.value,
            )
            .order_by(*_newest_first())
            .limit(1)
        )

        return None if record is None else _to_domain(record)

    def latest_for_document(self, document_id: int) -> tuple[Review, ...]:
        """
        One review per reviewed target: the newest of each.

        Read as a single ordered pass rather than one query per target -
        a document with two hundred reviewed statements would otherwise
        cost two hundred round trips to badge one screen.
        """

        records = self._session.scalars(
            select(ReviewRecord)
            .where(ReviewRecord.document_id == document_id)
            .order_by(
                ReviewRecord.target_key.asc(),
                ReviewRecord.recorded_at.desc(),
                ReviewRecord.id.desc(),
            )
        ).all()

        latest: list[ReviewRecord] = []
        seen: set[tuple[str, str]] = set()

        for record in records:
            identity = (record.target_type, record.target_key)

            if identity in seen:
                continue

            seen.add(identity)
            latest.append(record)

        return tuple(_to_domain(record) for record in latest)

    def count_for(self, target: ReviewTarget) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(ReviewRecord)
                .where(
                    ReviewRecord.document_id == target.document_id,
                    ReviewRecord.target_key == target.target_key,
                    ReviewRecord.target_type == target.target_type.value,
                )
            )
            or 0
        )


def _newest_first():
    """
    The ordering the port declares.

    ``id`` breaks the tie so two reviews recorded in the same clock tick
    have a stable order rather than one the database chose - and so
    "which is current?" cannot change between two reads.
    """

    return (ReviewRecord.recorded_at.desc(), ReviewRecord.id.desc())


def _to_domain(record: ReviewRecord) -> Review:
    return Review(
        review_id=record.id,
        target=ReviewTarget(
            target_type=ReviewTargetType(record.target_type),
            target_key=record.target_key,
            document_id=record.document_id,
        ),
        decision=ReviewDecision(record.decision),
        reason=ReviewReason(record.reason),
        comment=(
            None if record.comment is None else ReviewComment(record.comment)
        ),
        reviewer=ReviewerIdentity(
            user_id=record.reviewer_user_id,
            display_name=record.reviewer_display_name,
            email=record.reviewer_email,
            role=record.reviewer_role,
        ),
        snapshot=ReviewSnapshot(
            content_checksum=record.content_checksum,
            semantic_rule_id=record.semantic_rule_id,
            semantic_rule_version=record.semantic_rule_version,
            semantic_contract_version=record.semantic_contract_version,
            resolution_policy_version=record.resolution_policy_version,
            fact_policy_version=record.fact_policy_version,
            semantic_policy_version=record.semantic_policy_version,
            support_fingerprint=record.support_fingerprint,
            support_count=record.support_count,
        ),
        recorded_at=record.recorded_at,
        record_version=record.record_version,
    )
