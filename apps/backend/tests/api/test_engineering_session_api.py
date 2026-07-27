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

NOW = datetime(2026, 1, 1, 16, 0, 0)


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
                text="Answer text.",
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


def test_create_session_returns_a_created_session(api_client: TestClient) -> None:
    project = _create_project(api_client, "ENGSESS-001")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-session",
        json={"title": "Initial review"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["session"]["state"]["status"] == "created"
    assert body["session"]["configuration"]["title"] == "Initial review"
    assert body["validation"]["valid"] is True


def test_full_session_lifecycle_through_the_api(api_client: TestClient) -> None:
    project = _create_project(api_client, "ENGSESS-002")

    create_body = api_client.post(
        f"/projects/{project['id']}/engineering-session", json={}
    ).json()
    session = create_body["session"]

    activate_body = api_client.post(
        f"/projects/{project['id']}/engineering-session/change-state",
        json={"session": session, "target_status": "active"},
    ).json()
    assert activate_body["session"]["state"]["status"] == "active"
    session = activate_body["session"]

    response_json = _engineering_response_json(project["id"])
    append_body = api_client.post(
        f"/projects/{project['id']}/engineering-session/append-response",
        json={"session": session, "response": response_json},
    ).json()
    assert append_body["validation"]["valid"] is True
    assert append_body["session"]["statistics"]["response_count"] == 1
    session = append_body["session"]

    config_body = api_client.post(
        f"/projects/{project['id']}/engineering-session/update-configuration",
        json={"session": session, "notes": "Reviewed by engineer.smith"},
    ).json()
    assert config_body["session"]["configuration"]["notes"] == (
        "Reviewed by engineer.smith"
    )


def test_invalid_transition_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "ENGSESS-003")
    session = api_client.post(
        f"/projects/{project['id']}/engineering-session", json={}
    ).json()["session"]

    response = api_client.post(
        f"/projects/{project['id']}/engineering-session/change-state",
        json={"session": session, "target_status": "completed"},
    )

    assert response.status_code == 422


def test_project_id_mismatch_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "ENGSESS-004")
    other_project = _create_project(api_client, "ENGSESS-005")
    session = api_client.post(
        f"/projects/{project['id']}/engineering-session", json={}
    ).json()["session"]

    response = api_client.post(
        f"/projects/{other_project['id']}/engineering-session/change-state",
        json={"session": session, "target_status": "active"},
    )

    assert response.status_code == 422


def test_determinism_across_repeated_state_changes(api_client: TestClient) -> None:
    """
    The router itself is impure (``now=datetime.utcnow()`` per call, the
    same "impure at the edge, pure underneath" discipline every other
    governed router in this pipeline uses) - so two real HTTP calls
    never share an identical timestamp. What must stay identical is the
    *structure* the pure domain layer produced: event types, sequence
    numbers, and event count. Domain-level, same-``now`` determinism is
    already proven exactly by
    ``tests/domain/test_engineering_session_builder.py::test_identical_inputs_produce_an_identical_initial_session``.
    """

    project = _create_project(api_client, "ENGSESS-006")
    session = api_client.post(
        f"/projects/{project['id']}/engineering-session", json={}
    ).json()["session"]

    body = {"session": session, "target_status": "active"}
    first = api_client.post(
        f"/projects/{project['id']}/engineering-session/change-state", json=body
    ).json()
    second = api_client.post(
        f"/projects/{project['id']}/engineering-session/change-state", json=body
    ).json()

    first_shape = [
        (event["event_type"], event["sequence"])
        for event in first["session"]["timeline"]["events"]
    ]
    second_shape = [
        (event["event_type"], event["sequence"])
        for event in second["session"]["timeline"]["events"]
    ]
    assert first_shape == second_shape
    assert first["validation"]["valid"] is True
    assert second["validation"]["valid"] is True
