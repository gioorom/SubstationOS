"""
The Governed Structured Retrieval API (EPIC 31.2).

```
GET /projects/{project_id}/governed-retrieval/assets?designation=TR1
```

**One endpoint, and it is the one the Engineering Engine uses.** The
milestone's instruction was not to create a public API unless a product
requirement justifies one; the requirement here is inspection: an
engineer reading an engine answer must be able to ask *what the engine
retrieved and why*, and get exactly what the engine got - the same
query, the same matching, the same ordering, the same provenance.

Everything else a caller might want is already a resource:
``/knowledge-graph/nodes``, ``/knowledge-graph/edges`` and
``/documents/{id}/engineering-semantics/{key}/promotion`` answer the
browse-shaped questions, and duplicating them here would be a second way
to ask the same thing.

**No query language, and no room for one.** The only inputs are a
designation, a scope and a limit. There is no filter object, no
expression, no property map, no Cypher, no GraphQL and no SPARQL - the
same refusal the governed graph API already makes, for the same reason:
a governed graph whose value is that every answer is explainable must
not first ship a way to ask questions nobody planned.

**This route never writes.** It reaches the graph through
``GovernedKnowledgeReader``, a port with no write method at all.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.governed_retrieval.governed_retrieval_exceptions import (
    GovernedRetrievalError,
)
from app.domain.governed_retrieval.governed_retrieval_factory import (
    GovernedRetrievalQueryFactory,
)
from app.domain.governed_retrieval.governed_retrieval_validator import (
    DEFAULT_RESULT_LIMIT,
    MAX_RESULT_LIMIT,
    MIN_RESULT_LIMIT,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    RetrievalScope,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.infrastructure.governed_retrieval.sqlalchemy_governed_knowledge_reader import (  # noqa: E501
    SqlAlchemyGovernedKnowledgeReader,
)
from app.routers.security import require_capability
from app.schemas.governed_retrieval import (
    GovernedAssetRetrievalResponse,
    GovernedRetrievalResultRead,
)
from app.services import governed_retrieval_service

router = APIRouter(tags=["Governed Structured Retrieval"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


#: Reading governed knowledge needs no more than using the platform -
#: the same capability ``/knowledge-graph/nodes`` requires, because this
#: endpoint reads exactly the same rows.
_READ = Depends(require_capability(Capability.USE_ENGINEERING_PLATFORM))


@router.get(
    "/projects/{project_id}/governed-retrieval/assets",
    response_model=GovernedAssetRetrievalResponse,
    summary="Resolve a designation against governed knowledge, with the "
    "reason each governed object matched and the review that "
    "authorised it",
)
def retrieve_governed_assets(
    project_id: int,
    designation: str = Query(
        description=(
            "The designation to resolve, exactly as an engineer would "
            "write it. Matched against the governed label and the "
            "pipeline's own normalized value, by exact, "
            "case-and-whitespace-folded and alphanumeric-only equality - "
            "never by substring and never by similarity."
        ),
    ),
    include_quantities: bool = Query(
        default=False,
        description=(
            "Also follow the governed relationships from each resolved "
            "asset, returning what is asserted about it."
        ),
    ),
    include_historical: bool = Query(
        default=False,
        description=(
            "By default only current governed knowledge answers. Set to "
            "read what the graph used to assert - which is never mixed "
            "into a current answer implicitly."
        ),
    ),
    limit: int = Query(
        default=DEFAULT_RESULT_LIMIT,
        ge=MIN_RESULT_LIMIT,
        le=MAX_RESULT_LIMIT,
    ),
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> GovernedAssetRetrievalResponse:
    if project_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid project id: '{project_id}'.",
        )

    scope = (
        RetrievalScope.CURRENT_AND_HISTORICAL
        if include_historical
        else RetrievalScope.CURRENT_ONLY
    )
    reader = SqlAlchemyGovernedKnowledgeReader(db)
    now = datetime.utcnow()

    try:
        assets = governed_retrieval_service.retrieve(
            reader,
            GovernedRetrievalQueryFactory.asset_by_designation(
                designation=designation,
                scope=scope,
                limit=limit,
                project_id=project_id,
            ),
            now=now,
        )

        quantities = (
            governed_retrieval_service.retrieve(
                reader,
                GovernedRetrievalQueryFactory.quantity_for_asset(
                    designation=designation,
                    scope=scope,
                    limit=limit,
                    project_id=project_id,
                ),
                now=now,
            )
            if include_quantities
            else None
        )
    except GovernedRetrievalError as error:
        # Every failure this context raises is about the query, so 422
        # is the only status it can produce. A designation that matches
        # nothing is **not** a failure: it is a successful result whose
        # outcome is `no_match`, and an engineer needs to be able to
        # read that rather than catch it.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return GovernedAssetRetrievalResponse(
        designation=designation,
        assets=GovernedRetrievalResultRead.model_validate(assets),
        quantities=(
            None
            if quantities is None
            else GovernedRetrievalResultRead.model_validate(quantities)
        ),
    )
