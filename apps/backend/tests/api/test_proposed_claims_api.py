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


def _upload_document(
    api_client: TestClient,
    *,
    project_id: int | None,
    scope: str = "project",
) -> dict:
    data: dict[str, str] = {"scope": scope}

    if project_id is not None:
        data["project_id"] = str(project_id)

    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "functional-schematic.pdf",
                io.BytesIO(b"%PDF-1.4"),
                "application/pdf",
            )
        },
        data=data,
    )

    assert response.status_code == 200

    return response.json()


def _create_index_entry(
    api_client: TestClient,
    *,
    document_id: int,
    identifier: str,
) -> dict:
    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document_id,
            "kind": "equipment",
            "identifier": identifier,
        },
    )

    assert response.status_code == 201

    return response.json()


def test_create_proposed_claim_from_two_evidence_entries_in_one_document(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="TR-02",
    )

    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable C-295",
            "predicate": "FEEDS",
            "object": "Transformer TR-02",
            "engineering_index_entry_ids": [entry_a["id"], entry_b["id"]],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["claim_type"] == "relationship"
    assert body["subject"] == "Cable C-295"
    assert body["predicate"] == "FEEDS"
    assert body["object"] == "Transformer TR-02"
    assert {
        reference["engineering_index_entry_id"]
        for reference in body["evidence"]
    } == {entry_a["id"], entry_b["id"]}


def test_create_proposed_claim_returns_404_for_an_unknown_entry(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable C-295",
            "engineering_index_entry_ids": [999],
        },
    )

    assert response.status_code == 404


def test_create_proposed_claim_rejects_a_relationship_with_no_predicate(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )

    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable C-295",
            "object": "Transformer TR-02",
            "engineering_index_entry_ids": [entry["id"]],
        },
    )

    assert response.status_code == 422


def test_create_proposed_claim_rejects_evidence_spanning_documents_by_default(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document_a = _upload_document(api_client, project_id=project["id"])
    document_b = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document_a["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document_b["id"],
        identifier="TR-02",
    )

    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable C-295",
            "predicate": "FEEDS",
            "object": "Transformer TR-02",
            "engineering_index_entry_ids": [entry_a["id"], entry_b["id"]],
        },
    )

    assert response.status_code == 422


def test_create_proposed_claim_accepts_evidence_spanning_documents_when_allowed(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document_a = _upload_document(api_client, project_id=project["id"])
    document_b = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document_a["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document_b["id"],
        identifier="TR-02",
    )

    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable C-295",
            "predicate": "FEEDS",
            "object": "Transformer TR-02",
            "engineering_index_entry_ids": [entry_a["id"], entry_b["id"]],
            "allow_cross_document_evidence": True,
        },
    )

    assert response.status_code == 201


def test_create_proposed_claim_rejects_evidence_spanning_projects(
    api_client: TestClient,
) -> None:
    project_a = _create_project(api_client, code="ALPHA-002")
    project_b = _create_project(api_client, code="ALPHA-003")
    document_a = _upload_document(api_client, project_id=project_a["id"])
    document_b = _upload_document(api_client, project_id=project_b["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document_a["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document_b["id"],
        identifier="TR-02",
    )

    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable C-295",
            "predicate": "FEEDS",
            "object": "Transformer TR-02",
            "engineering_index_entry_ids": [entry_a["id"], entry_b["id"]],
            "allow_cross_document_evidence": True,
        },
    )

    assert response.status_code == 422


def test_create_proposed_claim_rejects_a_duplicate_claim(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295-B",
    )

    body = {
        "claim_type": "existence",
        "subject": "Cable C-295",
        "engineering_index_entry_ids": [entry_a["id"]],
    }
    first = api_client.post("/proposed-claims", json=body)
    assert first.status_code == 201

    second = api_client.post(
        "/proposed-claims",
        json={**body, "engineering_index_entry_ids": [entry_b["id"]]},
    )

    assert second.status_code == 409


def test_get_proposed_claim_returns_404_for_an_unknown_claim(
    api_client: TestClient,
) -> None:
    response = api_client.get("/proposed-claims/999")

    assert response.status_code == 404


def test_replace_claim_evidence(api_client: TestClient) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295-B",
    )
    created = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable C-295",
            "engineering_index_entry_ids": [entry_a["id"]],
        },
    )
    claim = created.json()

    response = api_client.put(
        f"/proposed-claims/{claim['id']}/evidence",
        json={"engineering_index_entry_ids": [entry_b["id"]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [
        reference["engineering_index_entry_id"]
        for reference in body["evidence"]
    ] == [entry_b["id"]]


def test_delete_proposed_claim(api_client: TestClient) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )
    created = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable C-295",
            "engineering_index_entry_ids": [entry["id"]],
        },
    )
    claim = created.json()

    response = api_client.delete(f"/proposed-claims/{claim['id']}")

    assert response.status_code == 204
    assert api_client.get(f"/proposed-claims/{claim['id']}").status_code == 404


def test_delete_proposed_claim_returns_404_for_an_unknown_claim(
    api_client: TestClient,
) -> None:
    response = api_client.delete("/proposed-claims/999")

    assert response.status_code == 404


def test_list_proposed_claims_for_project_does_not_leak_across_projects(
    api_client: TestClient,
) -> None:
    project_a = _create_project(api_client, code="ALPHA-004")
    project_b = _create_project(api_client, code="ALPHA-005")
    document_a = _upload_document(api_client, project_id=project_a["id"])
    document_b = _upload_document(api_client, project_id=project_b["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document_a["id"],
        identifier="C-295",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document_b["id"],
        identifier="TR-02",
    )
    api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable C-295",
            "engineering_index_entry_ids": [entry_a["id"]],
        },
    )
    api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Transformer TR-02",
            "engineering_index_entry_ids": [entry_b["id"]],
        },
    )

    response = api_client.get(
        f"/projects/{project_a['id']}/proposed-claims"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["subject"] == "Cable C-295"


def test_list_proposed_claims_for_document(api_client: TestClient) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="C-295",
    )
    api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable C-295",
            "engineering_index_entry_ids": [entry["id"]],
        },
    )

    response = api_client.get(f"/documents/{document['id']}/proposed-claims")

    assert response.status_code == 200
    assert len(response.json()) == 1
