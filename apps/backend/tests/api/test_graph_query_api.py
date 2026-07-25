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


def _build_and_execute_graph(api_client: TestClient) -> dict:
    """
    Full pipeline: Project -> Document -> Engineering Index entries ->
    a RELATIONSHIP claim (Cable 295 FEEDS TR2) and an EXISTENCE claim
    (a lone Breaker CB1, left unconnected on purpose so it shows up as
    an orphan) -> approval -> CanonicalFact -> GraphOperationBatch ->
    GraphExecution -> persisted graph state. Returns the project dict.
    """

    project = _create_project(api_client)
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


def test_list_entities_returns_every_node(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entities"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    values = [node["graph_entity_id"]["value"] for node in body]
    assert values == sorted(values)


def test_list_entities_filters_by_attribute(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entities",
        params={"has_attribute": "rated_voltage"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["canonical_id"] == "TR-02"
    assert body[0]["properties"] == {"rated_voltage": "132kV"}


def test_get_entity_by_id(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entities/CABLE:C-295"
    )

    assert response.status_code == 200
    assert response.json()["canonical_id"] == "C-295"


def test_get_entity_returns_404_for_an_unknown_entity(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entities/CABLE:UNKNOWN"
    )

    assert response.status_code == 404


def test_get_entity_returns_422_for_a_malformed_entity_id(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entities/malformed"
    )

    assert response.status_code == 422


def test_list_entities_by_type(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/entity-types/TRANSFORMER"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["entity_type"] == "TRANSFORMER"


def test_get_neighborhood_returns_center_and_directional_relationships(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/neighborhood/CABLE:C-295"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["center"]["canonical_id"] == "C-295"
    assert len(body["outgoing"]) == 1
    assert len(body["incoming"]) == 0
    assert [n["canonical_id"] for n in body["neighbors"]] == ["TR-02"]


def test_get_neighborhood_rejects_an_unsupported_depth(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/neighborhood/CABLE:C-295",
        params={"depth": 2},
    )

    assert response.status_code == 422


def test_get_neighborhood_returns_404_for_an_unknown_entity(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/neighborhood/CABLE:UNKNOWN"
    )

    assert response.status_code == 404


def test_get_statistics(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/statistics"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_entities"] == 3
    assert body["total_relationships"] == 1
    assert body["orphan_count"] == 1
    assert body["entities_by_type"]["CABLE"] == 1
    assert body["relationships_by_type"]["FEEDS"] == 1


def test_list_orphans(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(f"/projects/{project['id']}/graph/orphans")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["entity_type"] == "BREAKER"


def test_list_relationships(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/graph/relationships"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["relationship_type"]["value"] == "FEEDS"


def test_graph_query_is_scoped_per_project(api_client: TestClient) -> None:
    project_a = _build_and_execute_graph(api_client)
    project_b = _create_project(api_client, code="BETA-001")

    response = api_client.get(
        f"/projects/{project_b['id']}/graph/entities"
    )

    assert response.status_code == 200
    assert response.json() == []
    assert project_a["id"] != project_b["id"]
