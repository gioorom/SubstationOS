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


def _run_full_pipeline_to_batch(api_client: TestClient) -> dict:
    """
    ProposedClaim -> approval -> CanonicalFact -> GraphOperationBatch,
    for one RELATIONSHIP claim ("Cable 295" FEEDS "TR2"). Returns the
    created project dict.
    """

    project = _create_project(api_client)
    document = _upload_document(api_client, project["id"])

    entry = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "C-295",
        },
    ).json()

    claim = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable 295",
            "predicate": "feeds",
            "object": "TR2",
            "engineering_index_entry_ids": [entry["id"]],
        },
    ).json()

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

    return project


def _build_batch(api_client: TestClient, project_id: int) -> dict:
    response = api_client.post(f"/graph-builder/build/project/{project_id}")
    assert response.status_code == 201

    return response.json()


def test_full_pipeline_from_claim_to_persisted_graph_state(
    api_client: TestClient,
) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])

    execute_response = api_client.post(
        f"/graph-executions/batches/{batch['id']}"
    )

    assert execute_response.status_code == 200
    body = execute_response.json()
    assert body["created"] is True
    assert body["execution"]["status"] == "succeeded"
    assert body["execution"]["operation_count"] == 3

    nodes_response = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes"
    )
    assert nodes_response.status_code == 200
    nodes = nodes_response.json()
    assert len(nodes) == 2
    values = {node["graph_entity_id"]["value"] for node in nodes}
    assert values == {
        f"{project['id']}:CABLE:C-295",
        f"{project['id']}:TRANSFORMER:TR-02",
    }

    relationships_response = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/relationships"
    )
    assert relationships_response.status_code == 200
    relationships = relationships_response.json()
    assert len(relationships) == 1
    assert relationships[0]["relationship_type"]["value"] == "FEEDS"


def test_execute_batch_retry_returns_the_same_execution(
    api_client: TestClient,
) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])

    first = api_client.post(f"/graph-executions/batches/{batch['id']}")
    second = api_client.post(f"/graph-executions/batches/{batch['id']}")

    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["execution"]["id"] == second.json()["execution"]["id"]


def test_execute_batch_returns_404_for_an_unknown_batch(
    api_client: TestClient,
) -> None:
    response = api_client.post("/graph-executions/batches/999")

    assert response.status_code == 404


def test_execute_batch_returns_409_for_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    api_client.post(f"/projects/{project['id']}/activate")
    batch = _build_batch(api_client, project["id"])
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.post(f"/graph-executions/batches/{batch['id']}")

    assert response.status_code == 409


def test_get_execution_returns_404_for_an_unknown_execution(
    api_client: TestClient,
) -> None:
    response = api_client.get("/graph-executions/999")

    assert response.status_code == 404


def test_get_execution_returns_the_recorded_execution(
    api_client: TestClient,
) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])
    executed = api_client.post(
        f"/graph-executions/batches/{batch['id']}"
    ).json()

    response = api_client.get(
        f"/graph-executions/{executed['execution']['id']}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


def test_list_executions_for_batch(api_client: TestClient) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])
    api_client.post(f"/graph-executions/batches/{batch['id']}")
    api_client.post(f"/graph-executions/batches/{batch['id']}")

    response = api_client.get(
        f"/graph-operation-batches/{batch['id']}/executions"
    )

    assert response.status_code == 200
    # Retried, not re-executed: still exactly one recorded attempt.
    assert len(response.json()) == 1


def test_get_graph_node_by_entity_id(api_client: TestClient) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])
    api_client.post(f"/graph-executions/batches/{batch['id']}")

    response = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes/CABLE:C-295"
    )

    assert response.status_code == 200
    assert response.json()["canonical_id"] == "C-295"


def test_get_graph_node_returns_404_for_an_unknown_node(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes/CABLE:UNKNOWN"
    )

    assert response.status_code == 404


def test_get_graph_node_returns_422_for_a_malformed_entity_id(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes/malformed"
    )

    assert response.status_code == 422


def test_outgoing_and_incoming_relationship_reads(
    api_client: TestClient,
) -> None:
    project = _run_full_pipeline_to_batch(api_client)
    batch = _build_batch(api_client, project["id"])
    api_client.post(f"/graph-executions/batches/{batch['id']}")

    outgoing = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes/CABLE:C-295/outgoing"
    )
    incoming = api_client.get(
        f"/projects/{project['id']}/knowledge-graph/nodes/TRANSFORMER:TR-02/incoming"
    )

    assert outgoing.status_code == 200
    assert len(outgoing.json()) == 1
    assert incoming.status_code == 200
    assert len(incoming.json()) == 1
    assert (
        outgoing.json()[0]["target_entity_id"]["value"]
        == incoming.json()[0]["target_entity_id"]["value"]
    )
