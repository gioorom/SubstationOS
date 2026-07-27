from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.engineering_intent.engineering_intent_exceptions import (
    EngineeringIntentError,
)
from app.schemas.engineering_intent import (
    EngineeringIntentClassificationResultRead,
    EngineeringIntentClassifyRequestBody,
)
from app.services import engineering_intent_service

router = APIRouter(
    tags=["Engineering Intent"],
)


@router.post(
    "/projects/{project_id}/engineering-intents/classify",
    response_model=EngineeringIntentClassificationResultRead,
    summary="Deterministically classify an explicit engineering request "
    "into a structured EngineeringIntent",
)
def classify_engineering_request(
    project_id: int,
    body: EngineeringIntentClassifyRequestBody,
) -> EngineeringIntentClassificationResultRead:
    try:
        result = engineering_intent_service.classify(
            project_id=project_id,
            engineering_session_id=body.engineering_session_id,
            conversation_id=body.conversation_id,
            turn_id=body.turn_id,
            request_text=body.request_text,
            classified_at=datetime.utcnow(),
            working_memory_has_open_question=(
                body.working_memory_has_open_question
            ),
            working_memory_active_response_count=(
                body.working_memory_active_response_count
            ),
        )
    except EngineeringIntentError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return EngineeringIntentClassificationResultRead.from_domain(result)
