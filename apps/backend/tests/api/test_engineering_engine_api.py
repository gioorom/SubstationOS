"""
API tests for the Engineering Engine (Milestone 23A).

The real provider is never called: every test monkeypatches the
router's own ``build_anthropic_client`` with an in-memory fake SDK
client, the same technique ``tests/api/test_llm_invocation_api.py`` and
the full-pipeline integration test already use.
"""

from __future__ import annotations

import io
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


# --- DOCUMENT_LOOKUP (Milestone 23B.1) ------------------------------------
#
# The second registered workflow, over the *same* endpoint and the *same*
# request body: a caller selects it only by supplying a different
# classified intent type, never by naming a workflow.


def _upload_document(
    api_client: TestClient, project_id: int, filename: str
) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (filename, io.BytesIO(b"%PDF-1.4"), "application/pdf")
        },
        data={"scope": "project", "project_id": str(project_id)},
    )
    assert response.status_code == 200

    return response.json()


def _register_mention(
    api_client: TestClient,
    *,
    document_id: int,
    identifier: str,
    page: int,
    kind: str = "equipment",
) -> None:
    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document_id,
            "kind": kind,
            "identifier": identifier,
            "page": page,
        },
    )
    assert response.status_code == 201


def _lookup_body(**overrides) -> dict:
    defaults = dict(
        request_text="Trova il documento del montante T2",
        intent_type="document_lookup",
        retrieval_entity_type=None,
        retrieval_lexical_terms=["T2"],
    )
    defaults.update(overrides)

    return _body(**defaults)


def test_a_document_lookup_returns_structured_document_references(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-DL-001")
    document = _upload_document(
        api_client, project["id"], "montante-T2-schema.pdf"
    )
    _register_mention(
        api_client, document_id=document["id"], identifier="T2", page=4
    )

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_lookup_body(),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["selection"]["workflow_type"] == "document_lookup"
    assert body["validation"]["valid"] is True

    references = body["engineering_response"]["document_references"]
    assert len(references) == 1
    assert references[0]["document_id"] == document["id"]
    assert references[0]["title"] == "montante-T2-schema.pdf"
    # Reported exactly as the document repository stores it - never
    # re-derived, and never guessed from the filename.
    assert references[0]["document_format"] == document["file_format"]
    assert references[0]["revision"] == document["revision"]
    assert references[0]["page_references"] == [4]
    assert references[0]["relevance"]["total"] > 0


def test_a_document_lookup_response_names_no_provider_or_model(
    api_client: TestClient, monkeypatch
) -> None:
    """The API-visible form of this milestone's honesty guarantee: a
    caller can tell from the payload alone that no model was involved."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-DL-002")
    document = _upload_document(api_client, project["id"], "schema.pdf")
    _register_mention(
        api_client, document_id=document["id"], identifier="T2", page=1
    )

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_lookup_body(),
    )

    engineering_response = response.json()["engineering_response"]

    assert engineering_response["origin"] == "deterministic_retrieval"
    assert engineering_response["metadata"]["provider_id"] is None
    assert (
        engineering_response["metadata"]["configured_model_identifier"]
        is None
    )
    assert engineering_response["version"]["runtime_version"] is None


def test_a_document_lookup_with_no_match_completes_as_empty(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-DL-003")
    document = _upload_document(api_client, project["id"], "schema.pdf")
    _register_mention(
        api_client, document_id=document["id"], identifier="T2", page=1
    )

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_lookup_body(retrieval_lexical_terms=["99Z"]),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["failure"] is None
    assert body["engineering_response"]["status"] == "empty"
    assert body["engineering_response"]["document_references"] == []


def test_a_document_lookup_naming_no_identifier_fails_as_invalid(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-DL-004")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_lookup_body(retrieval_lexical_terms=[]),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "failed"
    assert body["failure"]["code"] == "invalid_execution_request"
    assert body["failure"]["step_type"] == "build_document_retrieval_request"


def test_a_document_lookup_never_reaches_the_provider(
    api_client: TestClient, monkeypatch
) -> None:
    """The runtime is deliberately left *disabled* and no credential is
    present. A knowledge query would fail here; a document lookup does not
    care, because it never invokes the runtime."""

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "false")

    project = _create_project(api_client, "ENGINE-DL-005")
    document = _upload_document(api_client, project["id"], "schema.pdf")
    _register_mention(
        api_client, document_id=document["id"], identifier="87T", page=2,
        kind="protection",
    )

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_lookup_body(
            request_text="Quali documenti parlano della protezione 87T?",
            retrieval_lexical_terms=["87T"],
        ),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert len(body["engineering_response"]["document_references"]) == 1


# --- ENGINEERING_EXPLANATION (Milestone 23B.2) ----------------------------
#
# The third registered workflow, over the *same* endpoint and the *same*
# request body - selected, as always, only by the classified intent type.


def _explanation_body(**overrides) -> dict:
    defaults = dict(
        request_text="Spiegami il funzionamento della protezione 87T",
        intent_type="engineering_explanation",
        retrieval_entity_type="PROTECTION",
    )
    defaults.update(overrides)

    return _body(**defaults)


def test_an_explanation_runs_the_workflow_to_completion(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-EX-001")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_explanation_body(),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["validation"]["valid"] is True
    assert body["selection"]["workflow_type"] == "engineering_explanation"
    assert body["engineering_response"] is not None


def test_an_explanation_returns_an_ordinary_llm_response(
    api_client: TestClient, monkeypatch
) -> None:
    """No new response type and no new metadata: an explanation is a
    normal EngineeringResponse with normal, populated provider fields."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-EX-002")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_explanation_body(),
    )

    engineering_response = response.json()["engineering_response"]

    assert engineering_response["origin"] == "llm_invocation"
    assert engineering_response["metadata"]["provider_id"]
    assert engineering_response["metadata"]["configured_model_identifier"]
    assert engineering_response["document_references"] == []


def test_an_explanation_runs_the_explanation_prompt_step(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-EX-003")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_explanation_body(),
    )

    step_types = [
        step["step_type"] for step in response.json()["execution"]["step_results"]
    ]

    assert "build_explanation_prompt" in step_types
    assert "build_prompt" not in step_types


def test_the_same_endpoint_still_runs_a_knowledge_query(
    api_client: TestClient, monkeypatch
) -> None:
    """A caller selects a workflow only by supplying a classified intent
    type - never by naming a workflow."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-EX-004")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_body(),
    )

    body = response.json()

    assert body["status"] == "completed"
    assert body["selection"]["workflow_type"] == "knowledge_query"


# --- ENGINEERING_VERIFICATION (Milestone 24.1) ----------------------------
#
# The fourth registered workflow, over the same endpoint, and the first
# whose response carries a machine-readable verdict.


def _enable_fake_runtime_answering(monkeypatch, text: str) -> None:
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-engine-test-key")
    monkeypatch.setenv("LLM_MODEL", "model-under-test")

    class _FakeMessages:
        def __init__(self) -> None:
            self.create = AsyncMock(
                side_effect=lambda **kwargs: make_message(
                    text=text, model="model-under-test"
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


def _verification_body(**overrides) -> dict:
    defaults = dict(
        request_text="Verify that protection 87T is present.",
        intent_type="verification_request",
        retrieval_entity_type=None,
        retrieval_lexical_terms=["87T"],
        retrieval_include_neighborhood=True,
        retrieval_neighborhood_depth=1,
    )
    defaults.update(overrides)

    return _body(**defaults)


def test_a_verification_runs_the_workflow_to_completion(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime_answering(monkeypatch, "SUPPORTED\nCandidate c1.")
    project = _create_project(api_client, "ENGINE-VF-001")

    response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_verification_body(),
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "completed"
    assert body["validation"]["valid"] is True
    assert body["selection"]["workflow_type"] == "engineering_verification"


def test_a_verification_exposes_its_verdict_over_the_api(
    api_client: TestClient, monkeypatch
) -> None:
    """An empty project here, so the structural bound applies: the model
    claims SUPPORTED and is overruled, which is exactly what a caller must
    be able to see."""

    _enable_fake_runtime_answering(monkeypatch, "SUPPORTED\nCandidate c1.")
    project = _create_project(api_client, "ENGINE-VF-002")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_verification_body(),
    ).json()

    verification = body["engineering_response"]["verification"]
    assert verification is not None
    assert verification["outcome"] == "insufficient_evidence"
    assert verification["stated_by_model"] is True
    assert verification["evidence_bounded"] is True
    assert verification["evidence_reference_count"] == 0


def test_a_verification_runs_the_verification_prompt_step(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime_answering(monkeypatch, "SUPPORTED\nCandidate c1.")
    project = _create_project(api_client, "ENGINE-VF-003")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_verification_body(),
    ).json()

    step_types = [
        step["step_type"] for step in body["execution"]["step_results"]
    ]

    assert "build_verification_prompt" in step_types
    assert "build_prompt" not in step_types


def test_other_workflows_expose_no_verdict(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "ENGINE-VF-004")

    body = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=_body(),
    ).json()

    assert body["engineering_response"]["verification"] is None
