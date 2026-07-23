from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_exceptions import (
    DuplicateOpenReviewCandidateError,
    InvalidReviewCommentError,
    InvalidReviewerError,
    InvalidReviewStatusTransitionError,
    ProjectNotReviewableError,
    ReviewCandidateNotFoundError,
    ReviewCommentRequiredError,
    ReviewedProjectNotFoundError,
    ReviewedProposedClaimNotFoundError,
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
from app.schemas.review_workflow import (
    ReviewCandidateCreate,
    ReviewCandidateRead,
    ReviewDecisionCreate,
    ReviewHistoryEventRead,
)
from app.services import review_workflow_service


router = APIRouter(
    tags=["Review Workflow"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Grouped only for reuse across the several endpoints that can raise
# them - each tuple still maps to one explicit HTTP status, never a
# catch-all.
_NOT_FOUND_ERRORS = (
    ReviewedProposedClaimNotFoundError,
    ReviewCandidateNotFoundError,
    ReviewedProjectNotFoundError,
)

_INVALID_INPUT_ERRORS = (
    InvalidReviewerError,
    InvalidReviewCommentError,
    ReviewCommentRequiredError,
)


@router.post(
    "/review-candidates",
    response_model=ReviewCandidateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review_candidate(
    payload: ReviewCandidateCreate,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    claim_repository = SqlAlchemyProposedClaimRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return review_workflow_service.create_review_candidate(
            candidate_repository,
            claim_repository,
            project_repository,
            proposed_claim_id=payload.proposed_claim_id,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        DuplicateOpenReviewCandidateError,
        ProjectNotReviewableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/review-candidates/pending",
    response_model=list[ReviewCandidateRead],
)
def list_pending_review_candidates(
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)

    return review_workflow_service.list_pending_review_candidates(
        candidate_repository
    )


@router.get(
    "/review-candidates/{candidate_id}",
    response_model=ReviewCandidateRead,
)
def get_review_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)

    try:
        return review_workflow_service.get_review_candidate(
            candidate_repository,
            candidate_id,
        )
    except ReviewCandidateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/review-candidates/{candidate_id}/history",
    response_model=list[ReviewHistoryEventRead],
)
def get_review_history(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    history_repository = SqlAlchemyReviewHistoryRepository(db)

    try:
        return review_workflow_service.get_review_history(
            candidate_repository,
            history_repository,
            candidate_id,
        )
    except ReviewCandidateNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/review-candidates/{candidate_id}/approve",
    response_model=ReviewCandidateRead,
)
def approve_review_candidate(
    candidate_id: int,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    history_repository = SqlAlchemyReviewHistoryRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return review_workflow_service.approve_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate_id,
            reviewed_by=payload.reviewed_by,
            comment=payload.comment,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        InvalidReviewStatusTransitionError,
        ProjectNotReviewableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/review-candidates/{candidate_id}/reject",
    response_model=ReviewCandidateRead,
)
def reject_review_candidate(
    candidate_id: int,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    history_repository = SqlAlchemyReviewHistoryRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return review_workflow_service.reject_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate_id,
            reviewed_by=payload.reviewed_by,
            comment=payload.comment,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        InvalidReviewStatusTransitionError,
        ProjectNotReviewableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/review-candidates/{candidate_id}/request-changes",
    response_model=ReviewCandidateRead,
)
def request_review_changes(
    candidate_id: int,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    history_repository = SqlAlchemyReviewHistoryRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return review_workflow_service.request_review_changes(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate_id,
            reviewed_by=payload.reviewed_by,
            comment=payload.comment,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        InvalidReviewStatusTransitionError,
        ProjectNotReviewableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.post(
    "/review-candidates/{candidate_id}/resubmit",
    response_model=ReviewCandidateRead,
)
def resubmit_review_candidate(
    candidate_id: int,
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    history_repository = SqlAlchemyReviewHistoryRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return review_workflow_service.resubmit_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate_id,
            reviewed_by=payload.reviewed_by,
            comment=payload.comment,
            now=datetime.utcnow(),
        )
    except _NOT_FOUND_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except _INVALID_INPUT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except (
        InvalidReviewStatusTransitionError,
        ProjectNotReviewableError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/projects/{project_id}/review-candidates",
    response_model=list[ReviewCandidateRead],
)
def list_review_candidates_for_project(
    project_id: int,
    review_status: ReviewStatus | None = None,
    db: Session = Depends(get_db),
):
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)

    return review_workflow_service.list_review_candidates_for_project(
        candidate_repository,
        project_id,
        status=review_status,
    )
