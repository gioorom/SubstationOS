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
from app.domain.canonicalization.canonicalization_exceptions import (
    CanonicalFactNotFoundError,
    CanonicalizationClaimNotFoundError,
    CanonicalizationProjectNotFoundError,
    CanonicalizationReviewCandidateNotFoundError,
    CrossProjectCanonicalizationError,
    ProjectNotCanonicalizableError,
    ReviewCandidateNotApprovedError,
    UnknownCanonicalEntityTypeError,
    UnknownCanonicalPredicateError,
    UnrecognizedEntityReferenceError,
    UnsupportedClaimTypeError,
)
from app.infrastructure.canonicalization.sqlalchemy_canonical_fact_repository import (
    SqlAlchemyCanonicalFactRepository,
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
from app.schemas.canonicalization import (
    CanonicalFactRead,
    CanonicalizationResultRead,
    CanonicalizeReviewCandidateRequest,
)
from app.services import canonicalization_service


router = APIRouter(
    tags=["Canonicalization"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


_NOT_FOUND_ERRORS = (
    CanonicalizationReviewCandidateNotFoundError,
    CanonicalizationClaimNotFoundError,
    CanonicalizationProjectNotFoundError,
    CanonicalFactNotFoundError,
)

_INVALID_INPUT_ERRORS = (
    CrossProjectCanonicalizationError,
    UnsupportedClaimTypeError,
    UnrecognizedEntityReferenceError,
    UnknownCanonicalEntityTypeError,
    UnknownCanonicalPredicateError,
)

_CONFLICT_ERRORS = (
    ReviewCandidateNotApprovedError,
    ProjectNotCanonicalizableError,
)


@router.post(
    "/canonical-facts",
    response_model=CanonicalizationResultRead,
)
def canonicalize_review_candidate(
    payload: CanonicalizeReviewCandidateRequest,
    db: Session = Depends(get_db),
):
    fact_repository = SqlAlchemyCanonicalFactRepository(db)
    candidate_repository = SqlAlchemyReviewCandidateRepository(db)
    claim_repository = SqlAlchemyProposedClaimRepository(db)
    project_repository = SqlAlchemyProjectRepository(db)

    try:
        return canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=payload.review_candidate_id,
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
    except _CONFLICT_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.get(
    "/canonical-facts/{fact_id}",
    response_model=CanonicalFactRead,
)
def get_canonical_fact(
    fact_id: int,
    db: Session = Depends(get_db),
):
    fact_repository = SqlAlchemyCanonicalFactRepository(db)

    try:
        return canonicalization_service.get_canonical_fact(
            fact_repository,
            fact_id,
        )
    except CanonicalFactNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/projects/{project_id}/canonical-facts",
    response_model=list[CanonicalFactRead],
)
def list_canonical_facts_for_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    fact_repository = SqlAlchemyCanonicalFactRepository(db)

    return canonicalization_service.list_canonical_facts_for_project(
        fact_repository,
        project_id,
    )


@router.get(
    "/documents/{document_id}/canonical-facts",
    response_model=list[CanonicalFactRead],
)
def list_canonical_facts_for_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    fact_repository = SqlAlchemyCanonicalFactRepository(db)

    return canonicalization_service.list_canonical_facts_for_document(
        fact_repository,
        document_id,
    )
