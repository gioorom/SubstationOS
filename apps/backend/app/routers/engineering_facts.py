"""
The Engineering Fact Construction API (Milestone 29.2).

```
POST /documents/{document_id}/engineering-facts            construct or re-use
GET  /documents/{document_id}/engineering-facts            the current set
GET  /documents/{document_id}/engineering-facts/{fact_key} one fact
GET  /documents/{document_id}/engineering-facts/{fact_key}/support
```

The composition root builds the entity, evidence and fact repositories,
and nothing else. There is no canonical text repository and no parser
here, because construction reads entities and has no way to reach a
document.

`201` when a set was constructed, `200` when the same entity source had
already been associated under the same rules, `404` when the document has
no entities - construction is the step after resolution. Everything else
returns `200` with a `succeeded: false` result carrying the typed cause,
so `422` keeps meaning exactly one thing across this codebase.

Constructing nothing is **not** a failure, and neither is declining an
ambiguous line: `found_facts` and `has_ambiguities` distinguish those
outcomes from each other and from a failure.

No ORM model is exposed, and nothing here writes a graph node or edge.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.engineering_facts.fact_failures import (
    FactConstructionFailureCode,
)
from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.infrastructure.engineering_facts.sqlalchemy_engineering_fact_repository import (  # noqa: E501
    SqlAlchemyEngineeringFactRepository,
)
from app.schemas.engineering_facts import (
    EngineeringFactRead,
    FactConstructionResultRead,
    FactSetRead,
    FactSupportRead,
)
from app.services import engineering_fact_service

router = APIRouter(
    tags=["Engineering Facts"],
)

_STATUS_FOR_FAILURE: dict[FactConstructionFailureCode, int] = {
    FactConstructionFailureCode.ENTITY_SET_MISSING: (
        status.HTTP_404_NOT_FOUND
    ),
    FactConstructionFailureCode.FACT_PERSISTENCE_FAILURE: (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ),
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _require_fact_set(db: Session, document_id: int):
    fact_set = engineering_fact_service.get_fact_set(
        SqlAlchemyEngineeringFactRepository(db), document_id
    )

    if fact_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no engineering facts; "
            "no construction has run against it.",
        )

    return fact_set


def _require_fact(db: Session, document_id: int, fact_key: str):
    fact = _require_fact_set(db, document_id).fact(fact_key)

    if fact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fact '{fact_key}' in the current fact set of "
            f"document '{document_id}'.",
        )

    return fact


@router.post(
    "/documents/{document_id}/engineering-facts",
    response_model=FactConstructionResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Construct associations between a document's resolved "
    "entities, or re-use the set it already has",
)
def construct_engineering_facts(
    document_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> FactConstructionResultRead:
    result = engineering_fact_service.construct_document_facts(
        SqlAlchemyEngineeringEntityRepository(db),
        SqlAlchemyEngineeringEvidenceRepository(db),
        SqlAlchemyEngineeringFactRepository(db),
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
        # Nothing was created; the set this entity source already had is
        # returned unchanged.
        response.status_code = status.HTTP_200_OK

    return FactConstructionResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/engineering-facts",
    response_model=FactSetRead,
    summary="Read a document's engineering facts, each with the "
    "observations supporting it, plus any declined ambiguities",
)
def read_engineering_facts(
    document_id: int,
    db: Session = Depends(get_db),
) -> FactSetRead:
    return FactSetRead.model_validate(_require_fact_set(db, document_id))


@router.get(
    "/documents/{document_id}/engineering-facts/{fact_key}",
    response_model=EngineeringFactRead,
    summary="Read one engineering fact",
)
def read_engineering_fact(
    document_id: int,
    fact_key: str,
    db: Session = Depends(get_db),
) -> EngineeringFactRead:
    return EngineeringFactRead.model_validate(
        _require_fact(db, document_id, fact_key)
    )


@router.get(
    "/documents/{document_id}/engineering-facts/{fact_key}/support",
    response_model=list[FactSupportRead],
    summary="The observations supporting one fact - every fact must be "
    "explainable through its entity and evidence support",
)
def read_fact_support(
    document_id: int,
    fact_key: str,
    db: Session = Depends(get_db),
) -> list[FactSupportRead]:
    fact = _require_fact(db, document_id, fact_key)

    return [
        FactSupportRead.model_validate(reference)
        for reference in fact.support
    ]
