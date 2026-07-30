"""
The Human Review API (EPIC 30.4).

```
GET  /documents/{id}/engineering-semantics/reviews                    every current decision
GET  /documents/{id}/engineering-semantics/{key}/reviews              one statement's history
POST /documents/{id}/engineering-semantics/{key}/reviews              append a judgement
GET  /documents/{id}/engineering-semantics/{key}/current-review       the effective decision
GET  /engineering-reviews/vocabulary                                  decisions and their reasons
```

Resource-oriented, not RPC. There is no `/approve`, no `/reject` and no
`/supersede`: a judgement is a **member appended to a collection**, and
the decision it carries is a field of that member. The shape is what
makes the append-only rule visible from outside - the collection has a
`POST` and nothing else, and no member has a `PATCH` or a `DELETE`.

`current-review` is a read-only projection of that collection, computed
on every request. It is deliberately a separate resource rather than a
field on the history: it answers a different question, it is what the
Workspace polls, and giving it its own URL keeps "the effective decision"
from ever looking like something a client could write.

**These routes never modify an engineering artefact.** They read the
semantic set to resolve a statement and to compare identity; the only
table they write is `engineering_reviews`. An architecture test asserts
it.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.domain.human_review.review_exceptions import (
    InvalidReviewCommentError,
    InvalidReviewTargetError,
    ReviewPolicyViolationError,
    ReviewTargetNotFoundError,
)
from app.domain.human_review.review_policy import (
    DECISIONS_REQUIRING_COMMENT,
)
from app.domain.human_review.review_vocabulary import (
    REASONS_FOR_DECISION,
    ReviewDecision,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageRequest,
)
from app.domain.shared_kernel.pagination_exceptions import PaginationError
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.infrastructure.engineering_semantics.sqlalchemy_engineering_semantic_repository import (  # noqa: E501
    SqlAlchemyEngineeringSemanticRepository,
)
from app.infrastructure.human_review.sqlalchemy_review_repository import (
    SqlAlchemyReviewRepository,
)
from app.routers.security import require_capability
from app.schemas.human_review import (
    CurrentReviewRead,
    DocumentReviewSummaryResponse,
    RecordReviewRequest,
    ReviewHistoryEntryRead,
    ReviewHistoryResponse,
    ReviewRead,
    ReviewVocabularyResponse,
)
from app.schemas.pagination import PageMetadata
from app.services import audit_service, human_review_service

router = APIRouter(tags=["Human Review"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _reviews(db: Session) -> SqlAlchemyReviewRepository:
    return SqlAlchemyReviewRepository(db)


def _semantics(db: Session) -> SqlAlchemyEngineeringSemanticRepository:
    """
    The engineering repository, held **read-only**.

    Used to resolve a statement key and to compare identity. Nothing in
    this router calls a method on it that writes.
    """

    return SqlAlchemyEngineeringSemanticRepository(db)


@router.get(
    "/engineering-reviews/vocabulary",
    response_model=ReviewVocabularyResponse,
    summary="The decisions a review may carry, and the reasons each admits",
)
def read_vocabulary() -> ReviewVocabularyResponse:
    """
    Served rather than duplicated in each client.

    A frontend that hard-coded which reasons go with which decision would
    eventually offer a pairing the backend refuses, and the reviewer would
    find out on submit.
    """

    return ReviewVocabularyResponse(
        decisions=tuple(ReviewDecision),
        reasons_by_decision={
            decision: tuple(sorted(reasons, key=lambda item: item.value))
            for decision, reasons in REASONS_FOR_DECISION.items()
        },
        decisions_requiring_comment=tuple(
            sorted(DECISIONS_REQUIRING_COMMENT, key=lambda item: item.value)
        ),
    )


@router.get(
    "/documents/{document_id}/engineering-semantics/reviews",
    response_model=DocumentReviewSummaryResponse,
    summary="The current decision for every reviewed statement in a document",
)
def read_document_reviews(
    document_id: int,
    db: Session = Depends(get_db),
    _: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
) -> DocumentReviewSummaryResponse:
    """
    One request for a whole document's review state.

    Statements nobody has reviewed are **absent**, not present with a
    null decision: "never reviewed" is the absence of a judgement, and a
    row asserting it would be a judgement.
    """

    summary = human_review_service.document_review_summary(
        _reviews(db), _semantics(db), document_id=document_id
    )

    return DocumentReviewSummaryResponse(
        document_id=summary.document_id,
        items=tuple(
            CurrentReviewRead.of(projection)
            for projection in summary.projections
        ),
    )


@router.get(
    "/documents/{document_id}/engineering-semantics/{statement_key}"
    "/current-review",
    response_model=CurrentReviewRead,
    summary="The effective decision for one statement, computed from history",
)
def read_current_review(
    document_id: int,
    statement_key: str,
    db: Session = Depends(get_db),
    _: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
) -> CurrentReviewRead:
    """
    Answers for a statement that no longer exists, too.

    That is the case the snapshot exists for: the projection reports
    `requires_revalidation` or `orphaned` rather than a `404`, because a
    judgement about something the pipeline has since re-derived is still
    a judgement somebody made and must still be readable.
    """

    try:
        projection = human_review_service.current_review(
            _reviews(db),
            _semantics(db),
            document_id=document_id,
            statement_key=statement_key,
        )
    except InvalidReviewTargetError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return CurrentReviewRead.of(projection)


@router.get(
    "/documents/{document_id}/engineering-semantics/{statement_key}/reviews",
    response_model=ReviewHistoryResponse,
    summary="One statement's review history, newest first",
)
def read_review_history(
    document_id: int,
    statement_key: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE
    ),
    db: Session = Depends(get_db),
    _: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
) -> ReviewHistoryResponse:
    """
    The authoritative record. Every judgement ever passed, in order.

    Paged because it only grows: a statement an engineering team argues
    over for a year is one whose history no single response should try to
    carry.
    """

    try:
        found, annotated = human_review_service.review_history(
            _reviews(db),
            _semantics(db),
            document_id=document_id,
            statement_key=statement_key,
            page=PageRequest(page=page, page_size=page_size),
        )
    except InvalidReviewTargetError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except PaginationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ReviewHistoryResponse(
        items=tuple(
            ReviewHistoryEntryRead.of(entry) for entry in annotated
        ),
        pagination=PageMetadata.of(found),
    )


@router.post(
    "/documents/{document_id}/engineering-semantics/{statement_key}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {
            "description": "The caller may not record engineering reviews."
        },
        404: {
            "description": (
                "The statement is not in this document's current "
                "interpretation."
            )
        },
        422: {"description": "The review does not satisfy the policy."},
    },
    summary="Record an engineering judgement about one statement",
)
def record_review(
    document_id: int,
    statement_key: str,
    payload: RecordReviewRequest,
    identity: AuditIdentity = Depends(
        require_capability(Capability.RECORD_ENGINEERING_REVIEW)
    ),
    db: Session = Depends(get_db),
) -> ReviewRead:
    """
    Appends a judgement. Nothing is updated, here or downstream.

    `201` always, even when an earlier review exists: a second judgement
    **creates** a second record rather than replacing the first, and a
    `200` would suggest otherwise. The superseded review is untouched and
    stays readable in the history.

    The reviewer is the authenticated identity. There is no field in the
    request body through which a caller could name somebody else.
    """

    now = datetime.utcnow()

    try:
        recorded = human_review_service.record_review(
            _reviews(db),
            _semantics(db),
            document_id=document_id,
            statement_key=statement_key,
            decision=payload.decision,
            reason=payload.reason,
            comment=payload.comment,
            identity=identity,
            now=now,
        )
    except ReviewPolicyViolationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=" ".join(error.violations),
        ) from error
    except (InvalidReviewCommentError, InvalidReviewTargetError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ReviewTargetNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    _record_audit(db, identity, recorded, now)

    return ReviewRead.of(recorded.review)


def _record_audit(
    db: Session,
    identity: AuditIdentity,
    recorded: human_review_service.RecordedReview,
    now: datetime,
) -> None:
    """
    The judgement, in the audit trail.

    A review is already an attributable, immutable record - so this is not
    the trail's only account of it. It is here because the audit trail is
    where "what did this person do on Tuesday?" is answered, and a
    governed engineering decision is exactly the kind of action that
    question is asked about.
    """

    audit = SqlAlchemyAuditRepository(db)
    review = recorded.review

    audit_service.record_for_identity(
        audit,
        identity=identity,
        action=AuditAction.ENGINEERING_REVIEW_RECORDED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource(
            review.target.target_type.value, review.target.target_key
        ),
        now=now,
        detail=review.describe(),
    )

    if recorded.superseded is not None:
        audit_service.record_for_identity(
            audit,
            identity=identity,
            action=AuditAction.ENGINEERING_REVIEW_SUPERSEDED,
            outcome=AuditOutcome.SUCCEEDED,
            resource=AuditResource(
                review.target.target_type.value, review.target.target_key
            ),
            now=now,
            detail=(
                f"review {recorded.superseded.review_id} superseded by "
                f"{review.review_id}"
            ),
        )
