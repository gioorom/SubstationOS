from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, code: str = "LLM-001") -> dict:
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


def test_prepare_request_endpoint_succeeds_with_explicit_provider_and_model(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="LLM-BUILD-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={
            "prompt_package": prompt_package,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request"]["project_id"] == project["id"]
    assert body["request"]["model_selection"]["model_identifier"] == "model-under-test"
    assert body["prepared_request"]["model"] == "model-under-test"
    assert body["prepared_request"]["provider_id"] == "anthropic"
    assert body["capability_validation"]["valid"] is True


def test_prepare_request_endpoint_uses_configuration_when_selection_is_omitted(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "configured-model")

    project = _build_and_execute_graph(api_client, code="LLM-CONFIG-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={"prompt_package": prompt_package},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request"]["provider_selection"]["provider_id"] == "anthropic"
    assert body["request"]["model_selection"]["model_identifier"] == "configured-model"


def test_prepare_request_endpoint_rejects_an_unknown_provider(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="LLM-UNKNOWN-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={
            "prompt_package": prompt_package,
            "provider_id": "openai",
            "model_identifier": "gpt-whatever",
        },
    )

    assert response.status_code == 422


def test_prepare_request_endpoint_rejects_a_missing_model(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)

    project = _build_and_execute_graph(api_client, code="LLM-MISSING-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={"prompt_package": prompt_package, "provider_id": "anthropic"},
    )

    assert response.status_code == 422


def test_prepare_request_endpoint_response_contains_no_secret_fields(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="LLM-SECRET-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={
            "prompt_package": prompt_package,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )

    assert response.status_code == 200
    raw_text = response.text
    assert "ANTHROPIC_API_KEY" not in raw_text
    assert "api_key" not in raw_text.lower()


def test_prepare_request_endpoint_never_invokes_a_provider(
    api_client: TestClient,
) -> None:
    # No network call is possible: the response is available
    # immediately and carries a prepared, never-sent request
    # representation, with no field describing an HTTP call or
    # response from Anthropic itself.
    project = _build_and_execute_graph(api_client, code="LLM-NOINVOKE-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={
            "prompt_package": prompt_package,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "content" not in body["prepared_request"]
    assert "finish_reason" not in body


def test_prepare_request_endpoint_response_is_deterministic(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="LLM-DETERM-001")
    prompt_package = _prompt_package(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )
    payload = {
        "prompt_package": prompt_package,
        "provider_id": "anthropic",
        "model_identifier": "model-under-test",
    }

    first = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request", json=payload
    ).json()
    second = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request", json=payload
    ).json()

    # Everything is deterministic except metadata.prepared_at and the
    # per-request correlation id - both legitimately vary between two
    # real, separately timed API calls (the router stamps `now` from
    # the wall clock and mints a fresh correlation id per call).
    assert first["request"]["messages"] == second["request"]["messages"]
    assert first["prepared_request"]["system"] == second["prepared_request"]["system"]
    assert first["prepared_request"]["messages"] == second["prepared_request"]["messages"]
