from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.working_memory.working_memory_exceptions import WorkingMemoryError
from app.schemas.conversation import conversation_from_schema
from app.schemas.engineering_session import engineering_session_from_schema
from app.schemas.working_memory import (
    WorkingMemoryBuildRequestBody,
    WorkingMemoryBuilderResultRead,
)
from app.services import working_memory_service

router = APIRouter(
    tags=["Working Memory"],
)


def _require_matching_project(project_id: int, conversation_project_id: int) -> None:
    """The path's ``project_id`` is authoritative; a supplied
    conversation naming a different project is a real inconsistency,
    never silently ignored - the same convention every governed router
    in this pipeline follows."""

    if project_id != conversation_project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Project id mismatch: path project id {project_id} does "
                "not match the supplied conversation's project id "
                f"{conversation_project_id}."
            ),
        )


@router.post(
    "/projects/{project_id}/working-memory/build",
    response_model=WorkingMemoryBuilderResultRead,
    summary="Deterministically build WorkingMemory from a Conversation "
    "and its EngineeringSession",
)
def build_working_memory(
    project_id: int,
    body: WorkingMemoryBuildRequestBody,
) -> WorkingMemoryBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    engineering_session = engineering_session_from_schema(body.engineering_session)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = working_memory_service.build(
            conversation=conversation,
            engineering_session=engineering_session,
            now=datetime.utcnow(),
        )
    except WorkingMemoryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return WorkingMemoryBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/working-memory/rebuild",
    response_model=WorkingMemoryBuilderResultRead,
    summary="Rebuild WorkingMemory from scratch - identical computation "
    "to /build, since nothing is ever persisted",
)
def rebuild_working_memory(
    project_id: int,
    body: WorkingMemoryBuildRequestBody,
) -> WorkingMemoryBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    engineering_session = engineering_session_from_schema(body.engineering_session)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = working_memory_service.rebuild(
            conversation=conversation,
            engineering_session=engineering_session,
            now=datetime.utcnow(),
        )
    except WorkingMemoryError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return WorkingMemoryBuilderResultRead.from_domain(result)
