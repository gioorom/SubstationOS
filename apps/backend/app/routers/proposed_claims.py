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
from app.domain.proposed_claims.proposed_claim_exceptions import (
    ClaimObjectRequiredError,
    ClaimPredicateRequiredError,
    CrossDocumentEvidenceNotAllowedError,
    CrossProjectEvidenceError,
    DocumentNotClaimableError,
    DuplicateEvidenceError,
    DuplicateProposedClaimError,
    EmptyEvidenceError,
    EvidenceEntryNotFoundError,
    InvalidClaimObjectError,
    InvalidClaimPredicateError,
    InvalidClaimSubjectError,
    ProjectNotClaimableError,
    ProposedClaimNotFoundError,
)
from app.infrastructure.engineering_index.sqlalchemy_document_lookup import (
    SqlAlchemyDocumentLookup,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.proposed_claims.sqlalchemy_proposed_claim_repository import (
    SqlAlchemyProposedClaimRepository,
)
from app.schemas.proposed_claims import (
    EvidenceReplace,
    ProposedClaimCreate,
    ProposedClaimRead,
)
from app.services import proposed_claim_service


router = APIRouter(
    tags=["Proposed Claims"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


_NOT_FOUND_ERRORS = (
    EvidenceEntryNotFoundError,
    ProposedClaimNotFoundError,
)

_INVALID_INPUT_ERRORS = (
    InvalidClaimSubjectError,
    InvalidClaimPredicateError,
    InvalidClaimObjectError,
    ClaimPredicateRequiredError,
    ClaimObjectRequiredError,
    EmptyEvidenceError,
    DocumentNotClaimableError,
    CrossDocumentEvidenceNotAllowedError,
    CrossProjectEvidenceError,
)

_CONFLICT_ERRORS = (
    DuplicateProposedClaimError,
    DuplicateEvidenceError,
    ProjectNotClaimableError,
)


@router.post(
    "/proposed-claims",
    response_model=ProposedClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def create_proposed_claim(
    payload: ProposedClaimCreate,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)
    engineering_index_repository = SqlAlchemyEngineeringIndexRepository(
        db
    )
    document_lookup = SqlAlchemyDocumentLookup(db)

    try:
        return proposed_claim_service.create_proposed_claim(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_type=payload.claim_type,
            subject=payload.subject,
            predicate=payload.predicate,
            object_=payload.object,
            engineering_index_entry_ids=(
                payload.engineering_index_entry_ids
            ),
            now=datetime.utcnow(),
            allow_cross_document_evidence=(
                payload.allow_cross_document_evidence
            ),
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
    "/proposed-claims/{claim_id}",
    response_model=ProposedClaimRead,
)
def get_proposed_claim(
    claim_id: int,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)

    try:
        return proposed_claim_service.get_proposed_claim(
            claim_repository,
            claim_id,
        )
    except ProposedClaimNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.put(
    "/proposed-claims/{claim_id}/evidence",
    response_model=ProposedClaimRead,
)
def replace_claim_evidence(
    claim_id: int,
    payload: EvidenceReplace,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)
    engineering_index_repository = SqlAlchemyEngineeringIndexRepository(
        db
    )
    document_lookup = SqlAlchemyDocumentLookup(db)

    try:
        return proposed_claim_service.replace_claim_evidence(
            claim_repository,
            engineering_index_repository,
            document_lookup,
            claim_id=claim_id,
            engineering_index_entry_ids=(
                payload.engineering_index_entry_ids
            ),
            now=datetime.utcnow(),
            allow_cross_document_evidence=(
                payload.allow_cross_document_evidence
            ),
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


@router.delete(
    "/proposed-claims/{claim_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_proposed_claim(
    claim_id: int,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)

    try:
        proposed_claim_service.delete_proposed_claim(
            claim_repository,
            claim_id,
        )
    except ProposedClaimNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return None


@router.get(
    "/projects/{project_id}/proposed-claims",
    response_model=list[ProposedClaimRead],
)
def list_proposed_claims_for_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)

    return proposed_claim_service.list_proposed_claims_for_project(
        claim_repository,
        project_id,
    )


@router.get(
    "/documents/{document_id}/proposed-claims",
    response_model=list[ProposedClaimRead],
)
def list_proposed_claims_for_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    claim_repository = SqlAlchemyProposedClaimRepository(db)

    return proposed_claim_service.list_proposed_claims_for_document(
        claim_repository,
        document_id,
    )
