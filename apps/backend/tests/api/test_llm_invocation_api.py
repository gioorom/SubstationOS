from __future__ import annotations

import io
from unittest.mock import AsyncMock

import anthropic
from fastapi.testclient import TestClient

from tests.infrastructure._anthropic_test_support import make_httpx_response, make_message


def _create_project(api_client: TestClient, code: str = "INV-001") -> dict:
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


def _upload_document(api_client: TestClient, project_id: int) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "functional-schematic.pdf",
                io.BytesIO(b"%PDF-1.4"),
                "application/pdf",
            )
        },
        data={"scope": "project", "project_id": str(project_id)},
    )
    assert response.status_code == 200

    return response.json()


def _approve_claim(
    api_client: TestClient,
    *,
    claim_type: str,
    subject: str,
    predicate: str | None,
    object_: str | None,
    entry_ids: list[int],
) -> dict:
    payload = {
        "claim_type": claim_type,
        "subject": subject,
        "engineering_index_entry_ids": entry_ids,
    }
    if predicate is not None:
        payload["predicate"] = predicate
    if object_ is not None:
        payload["object"] = object_

    claim = api_client.post("/proposed-claims", json=payload).json()
    candidate = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    ).json()
    approved = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer.smith"},
    ).json()
    fact_response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": approved["id"]},
    )
    assert fact_response.status_code == 200

    return fact_response.json()


def _build_and_execute_graph(api_client: TestClient, code: str) -> dict:
    project = _create_project(api_client, code=code)
    document = _upload_document(api_client, project["id"])

    cable_entry = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "C-295",
        },
    ).json()

    _approve_claim(
        api_client,
        claim_type="relationship",
        subject="Cable 295",
        predicate="feeds",
        object_="TR2",
        entry_ids=[cable_entry["id"]],
    )

    batch = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()
    executed = api_client.post(f"/graph-executions/batches/{batch['id']}")
    assert executed.status_code == 200
    assert executed.json()["execution"]["status"] == "succeeded"

    return project


def _prompt_package(api_client: TestClient, project_id: int, **retrieval_body) -> dict:
    retrieval_response = api_client.post(
        f"/projects/{project_id}/structured-retrieval/search", json=retrieval_body
    )
    assert retrieval_response.status_code == 200
    candidates = retrieval_response.json()["candidates"]

    context_response = api_client.post(
        f"/projects/{project_id}/context-builder/build",
        json={"candidates": candidates},
    )
    assert context_response.status_code == 200
    context_package = context_response.json()["package"]

    prompt_response = api_client.post(
        f"/projects/{project_id}/prompt-builder/build",
        json={"context_package": context_package},
    )
    assert prompt_response.status_code == 200

    return prompt_response.json()["package"]


class _FakeMessagesResource:
    def __init__(self, side_effect) -> None:
        self.create = AsyncMock(side_effect=side_effect)


class _FakeAnthropicClient:
    def __init__(self, side_effect) -> None:
        self.messages = _FakeMessagesResource(side_effect)


def test_invoke_endpoint_is_disabled_by_default(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="INV-DISABLED-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package},
    )

    assert response.status_code == 422
    assert "disabled" in response.json()["detail"].lower()


def test_invoke_endpoint_rejects_missing_credential(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    project = _build_and_execute_graph(api_client, code="INV-NOCRED-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 422
    assert "credential" in response.json()["detail"].lower()


def test_invoke_endpoint_project_mismatch_is_rejected(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")

    project = _build_and_execute_graph(api_client, code="INV-MISMATCH-001")
    other_project = _create_project(api_client, code="INV-MISMATCH-002")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{other_project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 422


def test_invoke_endpoint_successful_mocked_invocation(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY_SECONDS", "0.001")

    def _fake_build_client(**_kwargs):
        return _FakeAnthropicClient(
            side_effect=lambda **kwargs: make_message(text="Deterministic mocked answer.")
        )

    import app.routers.llm_provider as llm_provider_router_module

    monkeypatch.setattr(
        llm_provider_router_module, "build_anthropic_client", _fake_build_client
    )

    project = _build_and_execute_graph(api_client, code="INV-SUCCESS-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["envelope"]["content"][0]["text"] == "Deterministic mocked answer."
    assert body["envelope"]["provider_id"] == "anthropic"
    assert body["terminal_error"] is None
    assert len(body["attempts"]) == 1


def test_invoke_endpoint_normalized_provider_failure(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "1")

    response_obj = make_httpx_response(401)
    sdk_error = anthropic.AuthenticationError(
        "invalid api key",
        response=response_obj,
        body={"error": {"type": "authentication_error"}},
    )

    def _fake_build_client(**_kwargs):
        return _FakeAnthropicClient(side_effect=sdk_error)

    import app.routers.llm_provider as llm_provider_router_module

    monkeypatch.setattr(
        llm_provider_router_module, "build_anthropic_client", _fake_build_client
    )

    project = _build_and_execute_graph(api_client, code="INV-FAIL-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["envelope"] is None
    assert body["terminal_error"]["category"] == "authentication_failure"
    assert len(body["attempts"]) == 1


def test_invoke_endpoint_no_api_key_accepted_in_request_body(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="INV-NOKEYFIELD-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={
            "prompt_package": prompt_package,
            "api_key": "sk-ant-should-be-ignored",
        },
    )

    # An unknown "api_key" field is simply ignored by pydantic (extra
    # fields are dropped, never accepted as a credential) - the
    # request still fails on "runtime disabled", never on anything
    # related to the bogus field.
    assert response.status_code == 422
    assert "disabled" in response.json()["detail"].lower()


def test_invoke_endpoint_response_contains_no_secret_fields(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key-should-not-leak")

    def _fake_build_client(**_kwargs):
        return _FakeAnthropicClient(
            side_effect=lambda **kwargs: make_message(text="ok")
        )

    import app.routers.llm_provider as llm_provider_router_module

    monkeypatch.setattr(
        llm_provider_router_module, "build_anthropic_client", _fake_build_client
    )

    project = _build_and_execute_graph(api_client, code="INV-SECRET-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 200
    assert "fake-test-key-should-not-leak" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_prepare_request_endpoint_still_performs_zero_invocation(
    api_client: TestClient, monkeypatch
) -> None:
    # Even with the runtime enabled and a credential configured, the
    # Milestone 16 preparation-only endpoint must never invoke
    # anything - proven here by NOT patching build_anthropic_client at
    # all; if /prepare-request tried to call a real client, this test
    # would attempt real network I/O and fail/hang.
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")

    project = _build_and_execute_graph(api_client, code="INV-PREPONLY-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 200
    assert response.json()["prepared_request"]["provider_id"] == "anthropic"


def test_invoke_endpoint_first_attempt_success_invokes_exactly_once(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-test-key")

    call_counter = {"count": 0}

    def _counting_side_effect(**kwargs):
        call_counter["count"] += 1
        return make_message(text="single call")

    def _fake_build_client(**_kwargs):
        return _FakeAnthropicClient(side_effect=_counting_side_effect)

    import app.routers.llm_provider as llm_provider_router_module

    monkeypatch.setattr(
        llm_provider_router_module, "build_anthropic_client", _fake_build_client
    )

    project = _build_and_execute_graph(api_client, code="INV-ONECALL-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={"prompt_package": prompt_package, "model_identifier": "claude-test-model"},
    )

    assert response.status_code == 200
    assert call_counter["count"] == 1
