from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.engineering_session.engineering_session_exceptions import (
    EngineeringSessionError,
)
from app.schemas.engineering_response import engineering_response_from_schema
from app.schemas.engineering_session import (
    EngineeringSessionAppendResponseRequestBody,
    EngineeringSessionBuilderResultRead,
    EngineeringSessionChangeStateRequestBody,
    EngineeringSessionCreateRequestBody,
    EngineeringSessionUpdateConfigurationRequestBody,
    engineering_session_from_schema,
)
from app.services import engineering_session_service

router = APIRouter(
    tags=["Engineering Session"],
)


def _require_matching_project(project_id: int, session_project_id: int) -> None:
    """The path's ``project_id`` is authoritative; a supplied session
    naming a different project is a real inconsistency, never silently
    ignored - the same convention every governed router in this
    pipeline follows."""

    if project_id != session_project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Project id mismatch: path project id {project_id} does "
                "not match the supplied session's project id "
                f"{session_project_id}."
            ),
        )


@router.post(
    "/projects/{project_id}/engineering-session",
    response_model=EngineeringSessionBuilderResultRead,
    summary="Create a new EngineeringSession for a project",
)
def create_session(
    project_id: int,
    body: EngineeringSessionCreateRequestBody,
) -> EngineeringSessionBuilderResultRead:
    try:
        result = engineering_session_service.create_session(
            project_id=project_id,
            session_id=str(uuid.uuid4()),
            now=datetime.utcnow(),
            created_by=body.created_by,
            title=body.title,
            notes=body.notes,
        )
    except EngineeringSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return EngineeringSessionBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/engineering-session/append-response",
    response_model=EngineeringSessionBuilderResultRead,
    summary="Append an EngineeringResponse to an EngineeringSession",
)
def append_response(
    project_id: int,
    body: EngineeringSessionAppendResponseRequestBody,
) -> EngineeringSessionBuilderResultRead:
    session = engineering_session_from_schema(body.session)
    response = engineering_response_from_schema(body.response)
    _require_matching_project(project_id, session.project_id)

    try:
        result = engineering_session_service.append_response(
            session=session, response=response, now=datetime.utcnow()
        )
    except EngineeringSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return EngineeringSessionBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/engineering-session/change-state",
    response_model=EngineeringSessionBuilderResultRead,
    summary="Transition an EngineeringSession's state",
)
def change_state(
    project_id: int,
    body: EngineeringSessionChangeStateRequestBody,
) -> EngineeringSessionBuilderResultRead:
    session = engineering_session_from_schema(body.session)
    _require_matching_project(project_id, session.project_id)

    try:
        result = engineering_session_service.change_state(
            session=session,
            target_status=body.target_status,
            now=datetime.utcnow(),
        )
    except EngineeringSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return EngineeringSessionBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/engineering-session/update-configuration",
    response_model=EngineeringSessionBuilderResultRead,
    summary="Update an EngineeringSession's configuration (title/notes)",
)
def update_configuration(
    project_id: int,
    body: EngineeringSessionUpdateConfigurationRequestBody,
) -> EngineeringSessionBuilderResultRead:
    session = engineering_session_from_schema(body.session)
    _require_matching_project(project_id, session.project_id)

    try:
        result = engineering_session_service.update_configuration(
            session=session,
            now=datetime.utcnow(),
            title=body.title,
            notes=body.notes,
        )
    except EngineeringSessionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return EngineeringSessionBuilderResultRead.from_domain(result)
