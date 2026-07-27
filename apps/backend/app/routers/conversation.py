from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.conversation.conversation_exceptions import ConversationError
from app.schemas.conversation import (
    ConversationAddMessageRequestBody,
    ConversationAttachResponseRequestBody,
    ConversationBuilderResultRead,
    ConversationChangeStatusRequestBody,
    ConversationCompleteTurnRequestBody,
    ConversationCreateRequestBody,
    ConversationStartTurnRequestBody,
    conversation_from_schema,
)
from app.schemas.engineering_response import engineering_response_from_schema
from app.services import conversation_service

router = APIRouter(
    tags=["Conversation"],
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
    "/projects/{project_id}/conversation",
    response_model=ConversationBuilderResultRead,
    summary="Create a new Conversation for a project's EngineeringSession",
)
def create_conversation_endpoint(
    project_id: int,
    body: ConversationCreateRequestBody,
) -> ConversationBuilderResultRead:
    try:
        result = conversation_service.create(
            project_id=project_id,
            session_id=body.session_id,
            conversation_id=str(uuid.uuid4()),
            now=datetime.utcnow(),
            created_by=body.created_by,
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/conversation/start-turn",
    response_model=ConversationBuilderResultRead,
    summary="Start a new ConversationTurn (only one may be open at a time)",
)
def start_turn(
    project_id: int,
    body: ConversationStartTurnRequestBody,
) -> ConversationBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = conversation_service.start_new_turn(
            conversation=conversation,
            turn_id=str(uuid.uuid4()),
            now=datetime.utcnow(),
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/conversation/add-message",
    response_model=ConversationBuilderResultRead,
    summary="Append a message to the currently open ConversationTurn",
)
def add_message(
    project_id: int,
    body: ConversationAddMessageRequestBody,
) -> ConversationBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = conversation_service.add_message(
            conversation=conversation,
            role=body.role,
            text=body.text,
            now=datetime.utcnow(),
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/conversation/attach-response",
    response_model=ConversationBuilderResultRead,
    summary="Attach an EngineeringResponse to the currently open ConversationTurn",
)
def attach_response(
    project_id: int,
    body: ConversationAttachResponseRequestBody,
) -> ConversationBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    response = engineering_response_from_schema(body.response)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = conversation_service.attach_response(
            conversation=conversation,
            response=response,
            now=datetime.utcnow(),
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/conversation/complete-turn",
    response_model=ConversationBuilderResultRead,
    summary="Complete the currently open ConversationTurn",
)
def complete_turn(
    project_id: int,
    body: ConversationCompleteTurnRequestBody,
) -> ConversationBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = conversation_service.finish_turn(
            conversation=conversation, now=datetime.utcnow()
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)


@router.post(
    "/projects/{project_id}/conversation/change-status",
    response_model=ConversationBuilderResultRead,
    summary="Transition a Conversation's status",
)
def change_status(
    project_id: int,
    body: ConversationChangeStatusRequestBody,
) -> ConversationBuilderResultRead:
    conversation = conversation_from_schema(body.conversation)
    _require_matching_project(project_id, conversation.project_id)

    try:
        result = conversation_service.change_status(
            conversation=conversation,
            target_status=body.target_status,
            now=datetime.utcnow(),
        )
    except ConversationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return ConversationBuilderResultRead.from_domain(result)
