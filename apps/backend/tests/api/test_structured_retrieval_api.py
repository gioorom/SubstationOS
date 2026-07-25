from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, code: str = "ALPHA-001") -> dict:
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


def _build_and_execute_graph(api_client: TestClient, code: str = "ALPHA-001") -> dict:
    """
    Full pipeline: Project -> Document -> Engineering Index entries ->
    a RELATIONSHIP claim (Cable 295 FEEDS TR2), an ATTRIBUTE claim
    (TR2 rated voltage 132kV), and an EXISTENCE claim (a lone Breaker,
    left unconnected so it shows up as an orphan) -> approval ->
    CanonicalFact -> GraphOperationBatch -> GraphExecution -> persisted
    graph state. Returns the project dict.
    """

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
    breaker_entry = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "CB1",
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
    _approve_claim(
        api_client,
        claim_type="attribute",
        subject="TR2",
        predicate="Rated Voltage",
        object_="132kV",
        entry_ids=[cable_entry["id"]],
    )
    _approve_claim(
        api_client,
        claim_type="existence",
        subject="Breaker 1",
        predicate=None,
        object_=None,
        entry_ids=[breaker_entry["id"]],
    )

    batch = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()
    executed = api_client.post(f"/graph-executions/batches/{batch['id']}")
    assert executed.status_code == 200
    assert executed.json()["execution"]["status"] == "succeeded"

    return project


def test_plan_endpoint_returns_a_plan_without_touching_the_graph(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/plan",
        json={"mode": "entity_type_search", "entity_type": "CABLE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["required_operations"] == ["entities_by_type"]


def test_search_endpoint_returns_matching_entities(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "entity_type_search", "entity_type": "CABLE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 1
    candidate = body["candidates"]["candidates"][0]
    assert candidate["candidate_kind"] == "entity"
    assert candidate["primary_reference"]["canonical_id"] == "C-295"
    assert candidate["score"]["total"] == 50.0
    assert candidate["score"]["components"][0]["category"] == "entity_type_match"


def test_search_endpoint_exact_entity_lookup(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="LOOKUP-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_lookup",
            "canonical_entity_id": "CABLE:C-295",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 1
    assert body["candidates"]["candidates"][0]["score"]["total"] == 100.0


def test_search_endpoint_attribute_search(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="ATTR-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "attribute_search", "attribute_name": "rated_voltage"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 1
    assert body["candidates"]["candidates"][0]["matched_attributes"] == [
        {"name": "rated_voltage", "value": "132kV"}
    ]


def test_search_endpoint_relationship_search(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="REL-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "relationship_search", "relationship_type": "FEEDS"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 1
    assert body["candidates"]["candidates"][0]["candidate_kind"] == "relationship"


def test_search_endpoint_lexical_search(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="LEX-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "lexical_search", "lexical_terms": ["feeds"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 1


def test_search_endpoint_combined_search(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="COMBO-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "combined",
            "entity_type": "CABLE",
            "lexical_terms": ["cable"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] >= 1


def test_search_endpoint_neighborhood_enrichment(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="NEIGH-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_lookup",
            "canonical_entity_id": "CABLE:C-295",
            "include_neighborhood": True,
            "neighborhood_depth": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["neighborhood_enrichment_applied"] is True
    related = body["candidates"]["candidates"][0]["related_entities"]
    assert any(r["canonical_id"] == "TR-02" for r in related)


def test_search_endpoint_rejects_a_missing_criterion(api_client: TestClient) -> None:
    project = _create_project(api_client, code="INVALID-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "entity_lookup"},
    )

    assert response.status_code == 422


def test_search_endpoint_rejects_an_unsupported_criterion_combination(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="INVALID-002")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_lookup",
            "canonical_entity_id": "CABLE:C-295",
            "entity_type": "CABLE",
        },
    )

    assert response.status_code == 422


def test_search_endpoint_rejects_an_out_of_range_limit(api_client: TestClient) -> None:
    project = _create_project(api_client, code="INVALID-003")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_type_search",
            "entity_type": "CABLE",
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_search_endpoint_rejects_an_unsupported_neighborhood_depth(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="INVALID-004")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_type_search",
            "entity_type": "CABLE",
            "include_neighborhood": True,
            "neighborhood_depth": 2,
        },
    )

    assert response.status_code == 422


def test_search_endpoint_on_an_empty_project_is_a_successful_empty_result(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="EMPTY-001")

    response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={"mode": "entity_type_search", "entity_type": "CABLE"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"]["returned_count"] == 0
    assert body["candidates"]["total_before_limit"] == 0


def test_search_endpoint_is_scoped_per_project(api_client: TestClient) -> None:
    project_a = _build_and_execute_graph(api_client, code="SCOPE-A")
    project_b = _create_project(api_client, code="SCOPE-B")

    response = api_client.post(
        f"/projects/{project_b['id']}/structured-retrieval/search",
        json={"mode": "entity_type_search", "entity_type": "CABLE"},
    )

    assert response.status_code == 200
    assert response.json()["candidates"]["returned_count"] == 0
    assert project_a["id"] != project_b["id"]


def test_search_endpoint_response_is_deterministic(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="DETERM-001")

    payload = {"mode": "entity_type_search", "entity_type": "CABLE"}
    first = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search", json=payload
    )
    second = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search", json=payload
    )

    first_ids = [c["candidate_id"] for c in first.json()["candidates"]["candidates"]]
    second_ids = [c["candidate_id"] for c in second.json()["candidates"]["candidates"]]
    assert first_ids == second_ids
