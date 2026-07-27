from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.prompt_builder.prompt_builder_exceptions import (
    PromptBuilderError,
)
from app.domain.prompt_builder.prompt_builder_models import PromptBuildResult
from app.schemas.prompt_builder import (
    PromptBuildRequestBody,
    PromptBuildResultRead,
    context_package_from_schema,
)
from app.services import prompt_builder_service

router = APIRouter(
    tags=["Prompt Builder"],
)


@router.post(
    "/projects/{project_id}/prompt-builder/build",
    response_model=PromptBuildResultRead,
    summary="Assemble a deterministic, provider-independent PromptPackage "
    "from a ContextPackage",
)
def build_prompt_package(
    project_id: int,
    body: PromptBuildRequestBody,
) -> PromptBuildResult:
    context_package = context_package_from_schema(body.context_package)

    try:
        return prompt_builder_service.build_prompt_package(
            project_id=project_id,
            context_package=context_package,
            now=datetime.utcnow(),
        )
    except PromptBuilderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
