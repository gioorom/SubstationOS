from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.engineering_response.engineering_response_exceptions import (
    EngineeringResponseError,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseBuilderResult,
)
from app.schemas.context_builder import context_package_from_schema
from app.schemas.engineering_response import (
    EngineeringResponseBuildRequestBody,
    EngineeringResponseBuilderResultRead,
)
from app.schemas.llm_provider import llm_response_envelope_from_schema
from app.schemas.prompt_builder import prompt_package_from_schema
from app.services import engineering_response_service

router = APIRouter(
    tags=["Engineering Response"],
)


@router.post(
    "/projects/{project_id}/engineering-response/build",
    response_model=EngineeringResponseBuilderResultRead,
    summary="Build a structured, traceable EngineeringResponse from an "
    "LLMResponseEnvelope",
)
def build_engineering_response(
    project_id: int,
    body: EngineeringResponseBuildRequestBody,
) -> EngineeringResponseBuilderResult:
    context_package = context_package_from_schema(body.context_package)
    prompt_package = prompt_package_from_schema(body.prompt_package)
    llm_response_envelope = llm_response_envelope_from_schema(
        body.llm_response_envelope
    )

    try:
        return engineering_response_service.build_engineering_response(
            project_id=project_id,
            context_package=context_package,
            prompt_package=prompt_package,
            llm_response_envelope=llm_response_envelope,
            now=datetime.utcnow(),
        )
    except EngineeringResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
