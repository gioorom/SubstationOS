"""
API tests for the Engineering Engine (Milestone 23A).

The real provider is never called: every test monkeypatches the
router's own ``build_anthropic_client`` with an in-memory fake SDK
client, the same technique ``tests/api/test_llm_invocation_api.py`` and
the full-pipeline integration test already use.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from tests.infrastructure._anthropic_test_support import make_message


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


def _enable_fake_runtime(monkeypatch) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-engine-test-key")
    monkeypatch.setenv("LLM_MODEL", "model-under-test")

    class _FakeMessages:
        def __init__(self) -> None:
            self.create = AsyncMock(
                side_effect=lambda **kwargs: make_message(
                    text="The engine's deterministic answer.",
                    model="model-under-test",
                )
            )

    class _FakeClient:
        def __init__(self) -> None:
            self.messages = _FakeMessages()

    import app.routers.engineering_engine as engine_router_module

    monkeypatch.setattr(
        engine_router_module,
        "build_anthropic_client",
        lambda **_kwargs: _FakeClient(),
    )


def _body(**overrides) -> dict:
    body = {
        "engineering_session_id": "sess-1",
        "conversation_id": "conv-1",
        "turn_id": "turn-1",
        "request_text": "Quale TA è installato sul montante T2?",
        "engineering_intent_id": "conv-1:turn-1:1.0",
        "intent_type": "knowledge_query",
        "retrieval_entity_type": "CABLE",
    }
    body.update(overrides)
    return body


def test_execute_runs_the_knowledge_query_workflow_to_completion(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-001")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_body(),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["validation"]["valid"] is True
    assert body["selection"]["workflow_id"] == "knowledge-query"
    assert len(body["plan"]["steps"]) == 10
    assert all(
        result["status"] == "completed"
        for result in body["execution"]["step_results"]
    )
    assert body["engineering_response"] is not None
    assert body["engineering_response"]["direct_answer"]["body"] == [
        "The engine's deterministic answer."
    ]
    assert body["failure"] is None


def test_execute_returns_prepared_not_applied_aggregate_updates(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-002")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()

    updates = body["prepared_updates"]
    assert updates["conversation_update"]["disposition"] == "prepared"
    assert updates["session_update"]["disposition"] == "prepared"
    assert updates["conversation_update"]["conversation_id"] == "conv-1"
    assert updates["session_update"]["engineering_session_id"] == "sess-1"


def test_execute_returns_an_auditable_timeline(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-003")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()

    events = body["execution"]["timeline"]["events"]
    event_types = [event["event_type"] for event in events]

    assert event_types[0] == "execution_created"
    assert "workflow_selected" in event_types
    assert "plan_built" in event_types
    assert "plan_validated" in event_types
    assert event_types[-1] == "execution_completed"
    assert [event["sequence"] for event in events] == list(
        range(len(events))
    )


def test_an_unsupported_intent_returns_200_with_status_unsupported(
    api_client: TestClient, monkeypatch
) -> None:
    """A well-formed request for an unimplemented workflow is answered
    correctly, not rejected - so it is a 200 carrying
    ``status="unsupported"``, keeping 422 meaning exactly one thing
    (a structurally invalid request) across this codebase."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-004")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_body(intent_type="drawing_request"),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "unsupported"
    assert body["failure"]["code"] == "unsupported_intent"
    assert body["plan"] is None
    assert body["execution"] is None
    assert body["engineering_response"] is None
    assert body["prepared_updates"] is None


def test_a_blank_turn_id_fails_with_an_invalid_request(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-005")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_body(turn_id="   "),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure"]["code"] == "invalid_execution_request"


def test_a_non_positive_path_project_id_returns_422(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)

    response = api_client.post(
        "/projects/0/engineering-engine/execute", json=_body()
    )

    assert response.status_code == 422


def test_the_path_project_id_is_authoritative(
    api_client: TestClient, monkeypatch
) -> None:
    """The body carries no ``project_id`` at all - the path's is used
    everywhere, so a mismatch is structurally impossible."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-006")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()

    assert body["project_id"] == project["id"]
    assert body["metadata"]["project_id"] == project["id"]
    assert body["plan"]["metadata"]["project_id"] == project["id"]


def test_a_runtime_failure_is_reported_as_a_typed_engine_failure(
    api_client: TestClient, monkeypatch
) -> None:
    """No credential configured: the runtime refuses before any network
    access, and the engine reports a provider-neutral failure rather
    than raw provider detail."""

    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    project = _create_project(api_client, "ENGINE-007")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["failure"]["code"] == "runtime_failure"
    assert body["failure"]["step_type"] == "invoke_llm_runtime"
    assert body["engineering_response"] is None

    statuses = {
        result["step_type"]: result["status"]
        for result in body["execution"]["step_results"]
    }
    assert statuses["build_prompt"] == "completed"
    assert statuses["build_engineering_response"] == "skipped"


def test_planning_identity_is_deterministic_across_calls(
    api_client: TestClient, monkeypatch
) -> None:
    """Planning is deterministic even though runtime output need not
    be: the same request always yields the same plan and step ids."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-008")

    first = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()
    second = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()

    assert first["plan"]["plan_id"] == second["plan"]["plan_id"]
    assert first["execution_id"] == second["execution_id"]
    assert [step["step_id"] for step in first["plan"]["steps"]] == [
        step["step_id"] for step in second["plan"]["steps"]
    ]


def test_the_response_never_exposes_raw_provider_output(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-009")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute", json=_body()
    ).json()

    # The engine's own result is the primary payload; there is no raw
    # envelope, no provider SDK object, and no API key anywhere.
    assert "llm_response_envelope" not in body
    assert "api_key" not in str(body).lower()
