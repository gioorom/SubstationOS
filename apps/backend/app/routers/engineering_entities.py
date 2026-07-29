"""
The Engineering Entity Resolution API (Milestone 29.1).

```
POST /documents/{document_id}/engineering-entities              resolve or re-use
GET  /documents/{document_id}/engineering-entities              the current set
GET  /documents/{document_id}/engineering-entities/{entity_key} one entity
GET  /documents/{document_id}/engineering-entities/{entity_key}/evidence
```

The composition root builds the evidence repository and the entity
repository, and nothing else. There is no canonical text repository and
no parser here, because resolution reads evidence and has no way to reach
a document.

`201` when a set was resolved, `200` when the same evidence had already
been resolved under the same rules, `404` when the document has no
evidence - resolution is the step after extraction, and asking for it
first is a state conflict rather than a malformed request. Everything
else returns `200` with a `succeeded: false` result carrying the typed
cause, so `422` keeps meaning exactly one thing across this codebase.

Resolving nothing is **not** a failure: a document may contain no
observations these rules group into anything.

No ORM model is exposed, and nothing here writes a graph node.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.engineering_entities.entity_failures import (
    EntityResolutionFailureCode,
)
from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.schemas.engineering_entities import (
    EngineeringEntityRead,
    EntityResolutionResultRead,
    EntitySetRead,
    EvidenceReferenceRead,
)
from app.services import engineering_entity_service

router = APIRouter(
    tags=["Engineering Entities"],
)

_STATUS_FOR_FAILURE: dict[EntityResolutionFailureCode, int] = {
    EntityResolutionFailureCode.EVIDENCE_SET_MISSING: (
        status.HTTP_404_NOT_FOUND
    ),
    EntityResolutionFailureCode.ENTITY_PERSISTENCE_FAILURE: (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ),
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _require_entity_set(db: Session, document_id: int):
    entity_set = engineering_entity_service.get_entity_set(
        SqlAlchemyEngineeringEntityRepository(db), document_id
    )

    if entity_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no engineering "
            "entities; no resolution has run against it.",
        )

    return entity_set


def _require_entity(db: Session, document_id: int, entity_key: str):
    entity = _require_entity_set(db, document_id).entity(entity_key)

    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No entity '{entity_key}' in the current entity set "
            f"of document '{document_id}'.",
        )

    return entity


@router.post(
    "/documents/{document_id}/engineering-entities",
    response_model=EntityResolutionResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Resolve a document's engineering evidence into entities, "
    "or re-use the set it already has",
)
def resolve_engineering_entities(
    document_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> EntityResolutionResultRead:
    result = engineering_entity_service.resolve_document_entities(
        SqlAlchemyEngineeringEvidenceRepository(db),
        SqlAlchemyEngineeringEntityRepository(db),
        document_id=document_id,
    )

    if not result.succeeded:
        error_status = _STATUS_FOR_FAILURE.get(result.failure.code)

        if error_status is not None:
            raise HTTPException(
                status_code=error_status, detail=result.failure.message
            )

        response.status_code = status.HTTP_200_OK
    elif result.reused:
        # Nothing was created; the set this evidence already had is
        # returned unchanged.
        response.status_code = status.HTTP_200_OK

    return EntityResolutionResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/engineering-entities",
    response_model=EntitySetRead,
    summary="Read a document's engineering entities, each with the "
    "evidence that created it",
)
def read_engineering_entities(
    document_id: int,
    db: Session = Depends(get_db),
) -> EntitySetRead:
    return EntitySetRead.model_validate(
        _require_entity_set(db, document_id)
    )


@router.get(
    "/documents/{document_id}/engineering-entities/{entity_key}",
    response_model=EngineeringEntityRead,
    summary="Read one engineering entity",
)
def read_engineering_entity(
    document_id: int,
    entity_key: str,
    db: Session = Depends(get_db),
) -> EngineeringEntityRead:
    return EngineeringEntityRead.model_validate(
        _require_entity(db, document_id, entity_key)
    )


@router.get(
    "/documents/{document_id}/engineering-entities/{entity_key}/evidence",
    response_model=list[EvidenceReferenceRead],
    summary="The observations that created one entity - every entity "
    "can enumerate its own evidence",
)
def read_entity_evidence(
    document_id: int,
    entity_key: str,
    db: Session = Depends(get_db),
) -> list[EvidenceReferenceRead]:
    entity = _require_entity(db, document_id, entity_key)

    return [
        EvidenceReferenceRead.model_validate(reference)
        for reference in entity.evidence
    ]
