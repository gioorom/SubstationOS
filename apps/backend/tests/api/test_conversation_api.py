from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.application.models.llm_invocation import (
    LLMFinishReason,
    LLMInvocationStatus,
    LLMResponseContent,
    LLMResponseContentType,
    LLMResponseEnvelope,
    LLMResponseMetadata,
    LLMUsage,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.schemas.engineering_response import EngineeringResponseRead
from app.services import context_builder_service, engineering_response_service, prompt_builder_service

NOW = datetime(2026, 1, 1, 18, 0, 0)


def _create_project(api_client: TestClient, code: str) -> dict:
    response = api_client.post(
        "/projects/",
        json={
            "name": "Alpha Substation",
            "code": code,
            "customer": "Acme Utilities",
        },
    )
    assert response.status_code == 201
    return response.json()


def _engineering_response_json(project_id: int) -> dict:
    collection = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_result = context_builder_service.build_context_package(
        project_id=project_id, candidates=collection, now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    envelope = LLMResponseEnvelope(
        provider_id="anthropic",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="It feeds TR2.",
                provider_block_type=None,
                annotations=(),
            ),
        ),
        finish_reason=LLMFinishReason.COMPLETED,
        usage=LLMUsage(
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        ),
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id="corr-api-1",
        provider_request_id=None,
        started_at=NOW,
        completed_at=NOW,
        latency_seconds=0.1,
        attempt_count=1,
        attempts=(),
        warnings=(),
        metadata=LLMResponseMetadata(
            runtime_version="1.0",
            adapter_version="1.0",
            request_preparation_policy_version="1.0",
            prompt_package_version=prompt_result.package.version.package_version,
            context_builder_version=prompt_result.package.metadata.context_builder_version,
            prompt_builder_version=prompt_result.package.version.prompt_builder_version,
        ),
    )
    response = engineering_response_service.build_engineering_response(
        project_id=project_id,
        context_package=context_result.package,
        prompt_package=prompt_result.package,
        llm_response_envelope=envelope,
        now=NOW,
    ).response
    return json.loads(EngineeringResponseRead.model_validate(response).model_dump_json())


def test_create_conversation_returns_an_active_conversation(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "CONV-001")

    response = api_client.post(
        f"/projects/{project['id']}/conversation",
        json={"session_id": "sess-api-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["conversation"]["status"] == "active"
    assert body["conversation"]["session_id"] == "sess-api-1"
    assert body["validation"]["valid"] is True


def test_full_turn_lifecycle_through_the_api(api_client: TestClient) -> None:
    project = _create_project(api_client, "CONV-002")

    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]

    start_body = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    ).json()
    assert start_body["validation"]["valid"] is True
    conversation = start_body["conversation"]
    assert len(conversation["turns"]) == 1

    msg_body = api_client.post(
        f"/projects/{project['id']}/conversation/add-message",
        json={
            "conversation": conversation,
            "role": "user",
            "text": "What does C-295 feed?",
        },
    ).json()
    assert msg_body["validation"]["valid"] is True
    conversation = msg_body["conversation"]

    response_json = _engineering_response_json(project["id"])
    attach_body = api_client.post(
        f"/projects/{project['id']}/conversation/attach-response",
        json={"conversation": conversation, "response": response_json},
    ).json()
    assert attach_body["validation"]["valid"] is True
    conversation = attach_body["conversation"]

    msg2_body = api_client.post(
        f"/projects/{project['id']}/conversation/add-message",
        json={
            "conversation": conversation,
            "role": "assistant",
            "text": "It feeds TR2.",
        },
    ).json()
    conversation = msg2_body["conversation"]

    complete_body = api_client.post(
        f"/projects/{project['id']}/conversation/complete-turn",
        json={"conversation": conversation},
    ).json()
    assert complete_body["validation"]["valid"] is True
    conversation = complete_body["conversation"]

    assert conversation["statistics"]["message_count"] == 2
    assert conversation["statistics"]["engineering_response_count"] == 1
    assert conversation["turns"][0]["status"] == "completed"

    status_body = api_client.post(
        f"/projects/{project['id']}/conversation/change-status",
        json={"conversation": conversation, "target_status": "completed"},
    ).json()
    assert status_body["conversation"]["status"] == "completed"


def test_starting_a_second_turn_while_one_is_open_returns_422(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "CONV-003")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    ).json()["conversation"]

    response = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    )

    assert response.status_code == 422


def test_project_id_mismatch_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "CONV-004")
    other_project = _create_project(api_client, "CONV-005")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]

    response = api_client.post(
        f"/projects/{other_project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    )

    assert response.status_code == 422


def test_determinism_across_repeated_calls(api_client: TestClient) -> None:
    """
    The router itself is impure (``now=datetime.utcnow()`` per call) -
    so what stays identical across two calls is the *structure* the
    pure domain layer produced (event types/sequences), never exact
    timestamps. Domain-level, same-``now`` determinism is proven
    exactly by
    ``tests/domain/test_conversation_builder.py::test_identical_inputs_produce_an_identical_conversation``.
    """

    project = _create_project(api_client, "CONV-006")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]

    body = {"conversation": conversation}
    first = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn", json=body
    ).json()
    second = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn", json=body
    ).json()

    first_shape = [
        (event["event_type"], event["sequence"])
        for event in first["conversation"]["timeline"]["events"]
    ]
    second_shape = [
        (event["event_type"], event["sequence"])
        for event in second["conversation"]["timeline"]["events"]
    ]
    assert first_shape == second_shape
    assert first["validation"]["valid"] is True
    assert second["validation"]["valid"] is True
