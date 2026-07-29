"""
The Engineering Semantic Interpretation API (Milestone 30.1).

```
POST /documents/{document_id}/engineering-semantics                  interpret or re-use
GET  /documents/{document_id}/engineering-semantics                  the current set
GET  /documents/{document_id}/engineering-semantics/{statement_key}  one statement
GET  /documents/{document_id}/engineering-semantics/{statement_key}/facts
```

The composition root builds the fact repository and the semantic
repository, and nothing else. There is no canonical text repository, no
evidence repository and no parser here, because interpretation reads
facts and has no way to reach a document.

`201` when a set was interpreted, `200` when the same facts had already
been interpreted under the same rules, `404` when the document has no
facts - interpretation is the step after construction. Everything else
returns `200` with a `succeeded: false` result carrying the typed cause,
so `422` keeps meaning exactly one thing across this codebase.

Interpreting nothing is **not** a failure, and neither is declining an
ambiguous subject.

No ORM model is exposed, and nothing here writes a graph node or edge.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.engineering_semantics.semantic_failures import (
    SemanticInterpretationFailureCode,
)
from app.infrastructure.engineering_facts.sqlalchemy_engineering_fact_repository import (  # noqa: E501
    SqlAlchemyEngineeringFactRepository,
)
from app.infrastructure.engineering_semantics.sqlalchemy_engineering_semantic_repository import (  # noqa: E501
    SqlAlchemyEngineeringSemanticRepository,
)
from app.schemas.engineering_facts import EngineeringFactRead
from app.schemas.engineering_semantics import (
    SemanticInterpretationResultRead,
    SemanticSetRead,
    SemanticStatementRead,
)
from app.services import engineering_semantic_service

router = APIRouter(
    tags=["Engineering Semantics"],
)

_STATUS_FOR_FAILURE: dict[SemanticInterpretationFailureCode, int] = {
    SemanticInterpretationFailureCode.FACT_SET_MISSING: (
        status.HTTP_404_NOT_FOUND
    ),
    SemanticInterpretationFailureCode.SEMANTIC_PERSISTENCE_FAILURE: (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ),
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _require_semantic_set(db: Session, document_id: int):
    semantic_set = engineering_semantic_service.get_semantic_set(
        SqlAlchemyEngineeringSemanticRepository(db), document_id
    )

    if semantic_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no engineering "
            "semantics; no interpretation has run against it.",
        )

    return semantic_set


def _require_statement(db: Session, document_id: int, statement_key: str):
    statement = _require_semantic_set(db, document_id).statement(
        statement_key
    )

    if statement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No statement '{statement_key}' in the current "
            f"semantic set of document '{document_id}'.",
        )

    return statement


@router.post(
    "/documents/{document_id}/engineering-semantics",
    response_model=SemanticInterpretationResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign engineering meaning to a document's facts, or "
    "re-use the interpretation it already has",
)
def interpret_engineering_semantics(
    document_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> SemanticInterpretationResultRead:
    result = engineering_semantic_service.interpret_document_facts(
        SqlAlchemyEngineeringFactRepository(db),
        SqlAlchemyEngineeringSemanticRepository(db),
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
        # Nothing was created; the interpretation these facts already had
        # is returned unchanged.
        response.status_code = status.HTTP_200_OK

    return SemanticInterpretationResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/engineering-semantics",
    response_model=SemanticSetRead,
    summary="Read a document's interpreted engineering meaning, each "
    "statement with the facts supporting it",
)
def read_engineering_semantics(
    document_id: int,
    db: Session = Depends(get_db),
) -> SemanticSetRead:
    return SemanticSetRead.model_validate(
        _require_semantic_set(db, document_id)
    )


@router.get(
    "/documents/{document_id}/engineering-semantics/{statement_key}",
    response_model=SemanticStatementRead,
    summary="Read one semantic statement",
)
def read_semantic_statement(
    document_id: int,
    statement_key: str,
    db: Session = Depends(get_db),
) -> SemanticStatementRead:
    return SemanticStatementRead.model_validate(
        _require_statement(db, document_id, statement_key)
    )


@router.get(
    "/documents/{document_id}/engineering-semantics/{statement_key}/facts",
    response_model=list[EngineeringFactRead],
    summary="The facts supporting one statement - the next link in the "
    "chain from meaning back to the characters on the page",
)
def read_statement_facts(
    document_id: int,
    statement_key: str,
    db: Session = Depends(get_db),
) -> list[EngineeringFactRead]:
    statement = _require_statement(db, document_id, statement_key)
    fact_set = SqlAlchemyEngineeringFactRepository(
        db
    ).find_latest_for_document(document_id)

    if fact_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The facts supporting statement '{statement_key}' "
            "are no longer available.",
        )

    return [
        EngineeringFactRead.model_validate(fact)
        for fact_key in statement.supporting_fact_keys
        if (fact := fact_set.fact(fact_key)) is not None
    ]
