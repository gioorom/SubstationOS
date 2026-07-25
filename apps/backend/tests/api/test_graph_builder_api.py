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


def _create_approved_relationship_fact(
    api_client: TestClient,
) -> tuple[dict, dict]:
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

    return project, document


def test_build_batch_for_project_returns_graph_operations(
    api_client: TestClient,
) -> None:
    project, _document = _create_approved_relationship_fact(api_client)

    response = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["source"] == {"scope": "project", "scope_id": project["id"]}
    assert len(body["operations"]) == 3

    categories = [op["operation_category"] for op in body["operations"]]
    assert categories.count("node") == 2
    assert categories.count("relationship") == 1

    relationship = next(
        op for op in body["operations"] if op["operation_category"] == "relationship"
    )
    assert relationship["relationship_type"]["value"] == "FEEDS"
    assert relationship["subject_id"]["value"] == f"{project['id']}:CABLE:C-295"
    assert (
        relationship["object_id"]["value"]
        == f"{project['id']}:TRANSFORMER:TR-02"
    )


def test_build_batch_for_project_returns_404_for_an_unknown_project(
    api_client: TestClient,
) -> None:
    response = api_client.post("/graph-builder/build/project/999")

    assert response.status_code == 404


def test_build_batch_for_project_returns_409_for_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    )

    assert response.status_code == 409


def test_build_batch_for_document_returns_graph_operations(
    api_client: TestClient,
) -> None:
    _project, document = _create_approved_relationship_fact(api_client)

    response = api_client.post(
        f"/graph-builder/build/document/{document['id']}"
    )

    assert response.status_code == 200
    assert len(response.json()["operations"]) == 3


def test_build_batch_for_document_with_no_facts_returns_an_empty_batch(
    api_client: TestClient,
) -> None:
    response = api_client.post("/graph-builder/build/document/999")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] is None
    assert body["project_id"] is None
    assert body["operations"] == []


def test_get_graph_operation_batch_returns_404_for_an_unknown_batch(
    api_client: TestClient,
) -> None:
    response = api_client.get("/graph-builder/batch/999")

    assert response.status_code == 404


def test_get_graph_operation_batch_returns_the_built_batch(
    api_client: TestClient,
) -> None:
    project, _document = _create_approved_relationship_fact(api_client)
    built = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()

    response = api_client.get(f"/graph-builder/batch/{built['id']}")

    assert response.status_code == 200
    assert response.json()["operations"] == built["operations"]


def test_build_batch_twice_creates_two_independent_batches(
    api_client: TestClient,
) -> None:
    project, _document = _create_approved_relationship_fact(api_client)

    first = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()
    second = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()

    assert first["id"] != second["id"]
    assert first["operations"] == second["operations"]
