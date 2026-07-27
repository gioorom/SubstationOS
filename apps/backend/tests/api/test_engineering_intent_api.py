from __future__ import annotations

from fastapi.testclient import TestClient


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


def _classify(api_client: TestClient, project_id: int, request_text: str, **overrides):
    body = {
        "engineering_session_id": "sess-1",
        "conversation_id": "conv-1",
        "turn_id": "turn-1",
        "request_text": request_text,
    }
    body.update(overrides)
    return api_client.post(
        f"/projects/{project_id}/engineering-intents/classify", json=body
    )


def test_classify_returns_a_structured_classification(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INTENT-001")

    response = _classify(
        api_client, project["id"], "Confronta le revisioni 01 e 02 dello schema"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    intent = body["intent"]
    assert intent["intent_type"] == "engineering_comparison"
    assert intent["confidence"] == "high"
    assert intent["engineering_intent_id"] == "conv-1:turn-1:1.0"
    assert body["validation"]["valid"] is True


def test_classify_exposes_evidence_secondary_matches_and_statistics(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INTENT-002")

    response = _classify(api_client, project["id"], "Confronta i due documenti")

    assert response.status_code == 200
    intent = response.json()["intent"]

    matched_rule_ids = [item["matched_rule_id"] for item in intent["evidence"]]
    assert "comparison.verb" in matched_rule_ids
    assert "document_lookup" in intent["secondary_intent_types"]
    assert intent["statistics"]["matched_rule_count"] == len(intent["evidence"])


def test_classify_reports_ambiguity_as_a_first_class_result(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INTENT-003")

    response = _classify(api_client, project["id"], "Confronta e modifica lo schema")

    assert response.status_code == 200
    intent = response.json()["intent"]
    assert intent["intent_type"] == "ambiguous_request"
    assert intent["confidence"] == "unresolved"
    assert set(intent["secondary_intent_types"]) >= {
        "drawing_request",
        "engineering_comparison",
    }


def test_classify_reports_an_unsupported_request(api_client: TestClient) -> None:
    project = _create_project(api_client, "INTENT-004")

    response = _classify(api_client, project["id"], "Raccontami una barzelletta")

    assert response.status_code == 200
    intent = response.json()["intent"]
    assert intent["intent_type"] == "unsupported_request"
    assert intent["evidence"] == []


def test_classify_preserves_the_project_id_from_the_path(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INTENT-005")

    response = _classify(api_client, project["id"], "Verifica lo schema")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["intent"]["project_id"] == project["id"]
    assert body["intent"]["metadata"]["project_id"] == project["id"]


def test_blank_request_text_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "INTENT-006")

    response = _classify(api_client, project["id"], "   ")

    assert response.status_code == 422


def test_blank_provenance_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "INTENT-007")

    response = _classify(
        api_client, project["id"], "Verifica lo schema", conversation_id="  "
    )

    assert response.status_code == 422


def test_the_body_never_accepts_a_caller_supplied_classification(
    api_client: TestClient,
) -> None:
    """A caller cannot dictate the result: unknown fields like
    ``intent_type`` are ignored by the request schema, and the
    classifier's own deterministic decision always wins."""

    project = _create_project(api_client, "INTENT-008")

    response = _classify(
        api_client,
        project["id"],
        "Verifica lo schema",
        intent_type="drawing_request",
        confidence="high",
    )

    assert response.status_code == 200
    assert response.json()["intent"]["intent_type"] == "verification_request"


def test_classification_is_deterministic_across_repeated_calls(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INTENT-009")

    first = _classify(api_client, project["id"], "Apri la pagina").json()
    second = _classify(api_client, project["id"], "Apri la pagina").json()

    assert first["intent"]["engineering_intent_id"] == (
        second["intent"]["engineering_intent_id"]
    )
    assert first["intent"]["intent_type"] == second["intent"]["intent_type"]
    assert first["intent"]["evidence"] == second["intent"]["evidence"]
    assert first["intent"]["statistics"] == second["intent"]["statistics"]
