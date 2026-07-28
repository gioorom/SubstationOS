"""
API tests for Engineering Request Preparation (Milestone 23B.3),
including the full HTTP path this milestone creates:

    POST /engineering-requests/prepare   (raw sentence in)
    POST /engineering-engine/execute     (its output posted on unchanged)

The real provider is never called: the engine test's own fake SDK client
technique is reused.
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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-bridge-test-key")
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


def _prepare_body(request_text: str, **overrides) -> dict:
    body = {
        "engineering_session_id": "sess-1",
        "conversation_id": "conv-1",
        "turn_id": "turn-1",
        "request_text": request_text,
    }
    body.update(overrides)

    return body


def _prepare(api_client: TestClient, project_id: int, text: str, **overrides):
    return api_client.post(
        f"/projects/{project_id}/engineering-requests/prepare",
        json=_prepare_body(text, **overrides),
    )


# --- Preparation ------------------------------------------------------------


def test_prepare_derives_an_executable_request_from_a_raw_sentence(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-001")

    response = _prepare(
        api_client, project["id"], "Quale TA è installato sul cavo C-295?"
    )

    assert response.status_code == 200
    body = response.json()

    assert body["prepared"] is True
    assert body["intent"]["intent_type"] == "knowledge_query"
    assert body["bridge"]["resolved"] is True
    assert body["bridge"]["configuration"]["mode"] == "entity_lookup"

    request = body["execution_request"]
    assert request["retrieval_canonical_entity_id"] == "CABLE:C-295"
    assert request["intent_type"] == "knowledge_query"
    assert request["engineering_intent_id"]


def test_prepare_reports_the_designations_it_found(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-002")

    body = _prepare(
        api_client,
        project["id"],
        "Spiegami il funzionamento della protezione 87T",
    ).json()

    designations = body["bridge"]["designations"]
    assert len(designations) == 1
    assert designations[0]["text"] == "87T"
    assert designations[0]["resolution"] == "lexical_term"
    assert designations[0]["canonical_id"] is None


def test_prepare_applies_the_explanation_neighborhood_policy(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-003")

    body = _prepare(
        api_client,
        project["id"],
        "Spiegami il funzionamento della protezione 87T",
    ).json()

    request = body["execution_request"]
    assert request["intent_type"] == "engineering_explanation"
    assert request["retrieval_lexical_terms"] == ["87T"]
    assert request["retrieval_include_neighborhood"] is True
    assert request["retrieval_neighborhood_depth"] == 1


def test_the_request_body_accepts_no_retrieval_criteria(
    api_client: TestClient,
) -> None:
    """Deriving them is this endpoint's entire purpose; accepting an
    override would reopen the gap it exists to close."""

    from app.schemas.engineering_request_preparation import (
        EngineeringRequestPrepareRequestBody,
    )

    fields = set(EngineeringRequestPrepareRequestBody.model_fields)

    assert not any("retrieval" in field for field in fields)
    assert "intent_type" not in fields
    assert "engineering_intent_id" not in fields


# --- Honest refusals --------------------------------------------------------


def test_an_under_specified_request_is_answered_not_rejected(
    api_client: TestClient,
) -> None:
    """A well-formed request the bridge cannot resolve is a 200 carrying
    ``prepared=false`` - 422 keeps meaning exactly one thing."""

    project = _create_project(api_client, "BRIDGE-004")

    response = _prepare(
        api_client, project["id"], "Spiegami il funzionamento del trasformatore"
    )

    assert response.status_code == 200
    body = response.json()

    assert body["prepared"] is False
    assert body["execution_request"] is None
    assert body["bridge"]["failure"]["code"] == "insufficient_evidence"
    # The classification is still reported, so the refusal is inspectable.
    assert body["intent"]["intent_type"] == "engineering_explanation"


def test_an_unmapped_intent_is_reported_as_unsupported_mapping(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-005")

    body = _prepare(
        api_client, project["id"], "Disegna lo schema del cavo C-295"
    ).json()

    assert body["prepared"] is False
    assert body["bridge"]["failure"]["code"] == "unsupported_intent_mapping"


def test_conflicting_evidence_is_reported_rather_than_resolved_arbitrarily(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-006")

    body = _prepare(
        api_client, project["id"], "Spiegami il cavo C-295 e il cavo C-300"
    ).json()

    assert body["prepared"] is False
    assert body["bridge"]["failure"]["code"] == "conflicting_evidence"
    assert len(body["bridge"]["designations"]) == 2


def test_a_non_positive_path_project_id_returns_422(
    api_client: TestClient,
) -> None:
    response = _prepare(api_client, 0, "Trova il documento del montante T2")

    assert response.status_code == 422


# --- The full path: raw sentence -> prepare -> execute ----------------------


def test_a_raw_sentence_travels_all_the_way_to_a_completed_workflow(
    api_client: TestClient, monkeypatch
) -> None:
    """The gap this milestone closes, over HTTP: the caller supplies a
    sentence and posts the prepared request on unchanged. No retrieval
    criteria are written by hand at any point."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "BRIDGE-007")

    prepared = _prepare(
        api_client, project["id"], "Quale TA è installato sul cavo C-295?"
    ).json()
    assert prepared["prepared"] is True

    executed = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=prepared["execution_request"],
    )

    assert executed.status_code == 200
    body = executed.json()

    assert body["status"] == "completed"
    assert body["selection"]["workflow_id"] == "knowledge-query"
    assert body["engineering_response"] is not None


def test_a_raw_explanation_travels_all_the_way_to_a_completed_workflow(
    api_client: TestClient, monkeypatch
) -> None:
    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "BRIDGE-008")

    prepared = _prepare(
        api_client,
        project["id"],
        "Spiegami il funzionamento della protezione 87T",
    ).json()

    executed = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=prepared["execution_request"],
    )

    body = executed.json()
    assert body["status"] == "completed"
    assert body["selection"]["workflow_id"] == "engineering-explanation"


def test_preparation_is_reproducible_over_http(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-009")

    first = _prepare(
        api_client, project["id"], "Trova il documento del montante T2"
    ).json()
    second = _prepare(
        api_client, project["id"], "Trova il documento del montante T2"
    ).json()

    assert first["execution_request"] == second["execution_request"]
    assert first["bridge"]["configuration"] == (
        second["bridge"]["configuration"]
    )


# --- Comparison preparation (Milestone 24.2) --------------------------------


def test_a_comparison_prepares_two_operands_in_order(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-CMP-001")

    body = _prepare(
        api_client, project["id"], "Confronta il trasformatore T1 con T2"
    ).json()

    assert body["prepared"] is True
    assert body["intent"]["intent_type"] == "engineering_comparison"
    assert body["bridge"] is None

    comparison = body["comparison_bridge"]
    assert comparison["resolved"] is True
    assert comparison["configuration"]["left"]["designation"]["text"] == "T1"
    assert comparison["configuration"]["right"]["designation"]["text"] == "T2"

    request = body["execution_request"]
    assert request["comparison_left"]["designation"] == "T1"
    assert request["comparison_right"]["designation"] == "T2"
    # A comparison has no single retrieval configuration.
    assert request["retrieval_lexical_terms"] == []


def test_reversing_a_comparison_reverses_the_operands(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "BRIDGE-CMP-002")

    forward = _prepare(
        api_client, project["id"], "Confronta il trasformatore T1 con T2"
    ).json()["execution_request"]
    reverse = _prepare(
        api_client, project["id"], "Confronta il trasformatore T2 con T1"
    ).json()["execution_request"]

    assert forward["comparison_left"]["designation"] == "T1"
    assert reverse["comparison_left"]["designation"] == "T2"


def test_a_one_sided_comparison_is_refused(api_client: TestClient) -> None:
    project = _create_project(api_client, "BRIDGE-CMP-003")

    body = _prepare(
        api_client, project["id"], "Confronta il trasformatore T1"
    ).json()

    assert body["prepared"] is False
    assert body["execution_request"] is None
    assert body["comparison_bridge"]["failure"]["code"] == (
        "insufficient_evidence"
    )


def test_a_three_sided_comparison_is_refused(api_client: TestClient) -> None:
    project = _create_project(api_client, "BRIDGE-CMP-004")

    body = _prepare(api_client, project["id"], "Confronta T1 con T2 e T3").json()

    assert body["prepared"] is False
    assert body["comparison_bridge"]["failure"]["code"] == (
        "conflicting_evidence"
    )
    assert len(body["comparison_bridge"]["designations"]) == 3


def test_a_raw_comparison_travels_all_the_way_to_a_workflow(
    api_client: TestClient, monkeypatch
) -> None:
    """The full path over HTTP: a sentence naming two subjects becomes a
    completed comparison, with no retrieval criteria written by hand."""

    _enable_fake_runtime(monkeypatch)
    project = _create_project(api_client, "BRIDGE-CMP-005")

    prepared = _prepare(
        api_client, project["id"], "Confronta il trasformatore T1 con T2"
    ).json()
    assert prepared["prepared"] is True

    executed = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json=prepared["execution_request"],
    )

    assert executed.status_code == 200
    body = executed.json()

    assert body["status"] == "completed"
    assert body["selection"]["workflow_id"] == "engineering-comparison"

    # An empty project, so the structural bound applies: neither side has
    # evidence, and no difference can be asserted.
    comparison = body["engineering_response"]["comparison"]
    assert comparison["outcome"] == "insufficient_evidence"
    assert comparison["evidence_bounded"] is True
    assert comparison["left_evidence_count"] == 0
    assert comparison["right_evidence_count"] == 0
