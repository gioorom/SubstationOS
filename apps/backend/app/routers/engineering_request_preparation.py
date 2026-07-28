"""
The Engineering Request Preparation API (Milestone 23B.3) - the stage
that closes the gap between a raw request and an executable engine
request.

```
POST /projects/{id}/engineering-requests/prepare   <- this router
POST /projects/{id}/engineering-engine/execute     <- unchanged
```

Deliberately a **separate endpoint** rather than a new mode of the engine
endpoint. Two reasons, both this codebase's established discipline:

1. The engine must keep receiving an explicit execution request and must
   never parse natural language. Preparation is a stage before it, not a
   behaviour inside it.
2. Every stage in this pipeline exposes its own endpoint and returns an
   inspectable artifact that is the next stage's request shape. A caller
   can read exactly which designations were found and which criteria were
   derived *before* anything executes - which is what makes a
   deterministic bridge reviewable in practice rather than only in
   principle.

**An unresolvable request returns HTTP 200 with ``prepared=false``**, not
a client error: the request was well-formed and the bridge answered it
correctly ("this request names no equipment designation"). This matches
how the engine already reports unsupported intents, and keeps `422`
meaning exactly one thing across this codebase - a structurally invalid
request.

This router performs no retrieval, invokes no provider, and touches no
database.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.engineering_intent.engineering_intent_exceptions import (
    EngineeringIntentError,
)
from app.schemas.engineering_request_preparation import (
    EngineeringRequestPrepareRequestBody,
    PreparedEngineeringRequestRead,
)
from app.services import engineering_request_preparation_service

router = APIRouter(
    tags=["Engineering Request Preparation"],
)


@router.post(
    "/projects/{project_id}/engineering-requests/prepare",
    response_model=PreparedEngineeringRequestRead,
    summary="Classify a raw engineering request and derive the retrieval "
    "configuration the Engineering Engine needs, with no "
    "caller-supplied retrieval criteria",
)
def prepare_engineering_request(
    project_id: int,
    body: EngineeringRequestPrepareRequestBody,
) -> PreparedEngineeringRequestRead:
    if project_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid project id: '{project_id}'.",
        )

    try:
        prepared = (
            engineering_request_preparation_service.prepare_engineering_request(
                project_id=project_id,
                engineering_session_id=body.engineering_session_id,
                conversation_id=body.conversation_id,
                turn_id=body.turn_id,
                request_text=body.request_text,
                now=datetime.utcnow(),
                provider_id=body.provider_id,
                model_identifier=body.model_identifier,
                request_correlation_id=body.request_correlation_id,
                working_memory_has_open_question=(
                    body.working_memory_has_open_question
                ),
                working_memory_active_response_count=(
                    body.working_memory_active_response_count
                ),
            )
        )
    except EngineeringIntentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return PreparedEngineeringRequestRead.from_domain(prepared)
