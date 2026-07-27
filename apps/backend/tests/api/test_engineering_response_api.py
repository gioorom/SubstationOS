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
from app.schemas.context_builder import ContextPackageRead
from app.schemas.llm_provider import LLMResponseEnvelopeRead
from app.schemas.prompt_builder import PromptPackageRead
from app.services import context_builder_service, prompt_builder_service

NOW = datetime(2026, 1, 1, 14, 0, 0)


def _create_project(api_client: TestClient, code: str = "ENGRESP-001") -> dict:
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


def _packages_json(project_id: int) -> tuple[dict, dict, object]:
    collection = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_result = context_builder_service.build_context_package(
        project_id=project_id, candidates=collection, now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )

    context_json = json.loads(
        ContextPackageRead.model_validate(context_result.package).model_dump_json()
    )
    prompt_json = json.loads(
        PromptPackageRead.model_validate(prompt_result.package).model_dump_json()
    )
    return context_json, prompt_json, prompt_result.package


def _envelope_json(prompt_package, **overrides) -> dict:
    defaults = dict(
        provider_id="anthropic",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="This cable feeds transformer TR2.",
                provider_block_type=None,
                annotations=(),
            ),
        ),
        finish_reason=LLMFinishReason.COMPLETED,
        usage=LLMUsage(
            input_tokens=42,
            output_tokens=7,
            total_tokens=49,
            cached_input_tokens=None,
            cache_creation_tokens=None,
        ),
        status=LLMInvocationStatus.SUCCEEDED,
        request_correlation_id="corr-api-1",
        provider_request_id="prov-req-1",
        started_at=NOW,
        completed_at=NOW,
        latency_seconds=0.25,
        attempt_count=1,
        attempts=(),
        warnings=(),
        metadata=LLMResponseMetadata(
            runtime_version="1.0",
            adapter_version="1.0",
            request_preparation_policy_version="1.0",
            prompt_package_version=prompt_package.version.package_version,
            context_builder_version=prompt_package.metadata.context_builder_version,
            prompt_builder_version=prompt_package.version.prompt_builder_version,
        ),
    )
    defaults.update(overrides)
    envelope = LLMResponseEnvelope(**defaults)
    return json.loads(LLMResponseEnvelopeRead.model_validate(envelope).model_dump_json())


def test_build_endpoint_returns_a_structured_engineering_response(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    context_json, prompt_json, prompt_package = _packages_json(project["id"])
    envelope_json = _envelope_json(prompt_package)

    response = api_client.post(
        f"/projects/{project['id']}/engineering-response/build",
        json={
            "context_package": context_json,
            "prompt_package": prompt_json,
            "llm_response_envelope": envelope_json,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["project_id"] == project["id"]
    result = body["response"]
    assert result["status"] == "complete"
    assert len(result["sections"]) == 9
    assert result["direct_answer"]["body"] == [
        "This cable feeds transformer TR2."
    ]
    assert result["direct_answer"]["enabled"] is True
    assert body["validation"]["valid"] is True


def test_build_endpoint_never_invokes_a_provider(
    api_client: TestClient, monkeypatch
) -> None:
    """No environment variable this endpoint reads should ever trigger a
    network call - Engineering Response performs no AI invocation."""

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_RUNTIME_ENABLED", raising=False)

    project = _create_project(api_client, code="ENGRESP-002")
    context_json, prompt_json, prompt_package = _packages_json(project["id"])
    envelope_json = _envelope_json(prompt_package)

    response = api_client.post(
        f"/projects/{project['id']}/engineering-response/build",
        json={
            "context_package": context_json,
            "prompt_package": prompt_json,
            "llm_response_envelope": envelope_json,
        },
    )

    assert response.status_code == 200


def test_project_id_mismatch_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, code="ENGRESP-003")
    other_project = _create_project(api_client, code="ENGRESP-004")

    context_json, prompt_json, prompt_package = _packages_json(project["id"])
    envelope_json = _envelope_json(prompt_package)

    response = api_client.post(
        f"/projects/{other_project['id']}/engineering-response/build",
        json={
            "context_package": context_json,
            "prompt_package": prompt_json,
            "llm_response_envelope": envelope_json,
        },
    )

    assert response.status_code == 422


def test_determinism_across_repeated_calls(api_client: TestClient) -> None:
    project = _create_project(api_client, code="ENGRESP-005")
    context_json, prompt_json, prompt_package = _packages_json(project["id"])
    envelope_json = _envelope_json(prompt_package)

    body = {
        "context_package": context_json,
        "prompt_package": prompt_json,
        "llm_response_envelope": envelope_json,
    }

    first = api_client.post(
        f"/projects/{project['id']}/engineering-response/build", json=body
    ).json()
    second = api_client.post(
        f"/projects/{project['id']}/engineering-response/build", json=body
    ).json()

    assert first["response"]["sections"] == second["response"]["sections"]
    assert first["response"]["statistics"] == second["response"]["statistics"]


def test_unsupported_content_is_reported_as_partial(api_client: TestClient) -> None:
    project = _create_project(api_client, code="ENGRESP-006")
    context_json, prompt_json, prompt_package = _packages_json(project["id"])
    envelope_json = _envelope_json(
        prompt_package,
        content=(
            LLMResponseContent(
                sequence_index=0,
                content_type=LLMResponseContentType.TEXT,
                text="Partial text.",
                provider_block_type=None,
                annotations=(),
            ),
            LLMResponseContent(
                sequence_index=1,
                content_type=LLMResponseContentType.UNSUPPORTED,
                text="",
                provider_block_type="tool_use",
                annotations=(),
            ),
        ),
    )

    response = api_client.post(
        f"/projects/{project['id']}/engineering-response/build",
        json={
            "context_package": context_json,
            "prompt_package": prompt_json,
            "llm_response_envelope": envelope_json,
        },
    )

    assert response.status_code == 200
    result = response.json()["response"]
    assert result["status"] == "partial"
    assert any(w["category"] == "unknown_content" for w in result["warnings"])
