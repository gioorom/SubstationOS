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


def test_create_index_entry_succeeds_for_a_project_scoped_document(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
            "page": 3,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["document_id"] == document["id"]
    assert body["kind"] == "equipment"
    assert body["identifier"] == "T1"
    assert body["page"] == 3


def test_create_index_entry_rejects_a_blank_identifier(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "",
        },
    )

    assert response.status_code == 422


def test_create_index_entry_returns_404_for_an_unknown_document(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": 999,
            "kind": "equipment",
            "identifier": "T1",
        },
    )

    assert response.status_code == 404


def test_create_index_entry_rejects_a_canonical_library_document(
    api_client: TestClient,
) -> None:
    document = _upload_document(
        api_client,
        project_id=None,
        scope="canonical_library",
    )

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )

    assert response.status_code == 422


def test_create_index_entry_rejects_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )

    assert response.status_code == 409


def test_create_index_entries_bulk_registers_every_mention(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    response = api_client.post(
        "/engineering-index/entries/bulk",
        json={
            "document_id": document["id"],
            "mentions": [
                {"kind": "equipment", "identifier": "T1", "page": 1},
                {"kind": "cable", "identifier": "W-152", "page": 2},
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert [entry["identifier"] for entry in body] == ["T1", "W-152"]


def test_get_index_entry_returns_404_for_an_unknown_entry(
    api_client: TestClient,
) -> None:
    response = api_client.get("/engineering-index/entries/999")

    assert response.status_code == 404


def test_list_index_entries_for_document(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )

    response = api_client.get(
        f"/documents/{document['id']}/engineering-index"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_index_entries_for_project_filters_by_kind(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )
    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "cable",
            "identifier": "W-152",
        },
    )

    response = api_client.get(
        f"/projects/{project['id']}/engineering-index",
        params={"kind": "cable"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["identifier"] == "W-152"


def test_search_index_entries_by_identifier(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "protection",
            "identifier": "52-T1",
        },
    )

    response = api_client.get(
        f"/projects/{project['id']}/engineering-index/search",
        params={"identifier": "t1"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_replace_document_index_is_idempotent_for_identical_input(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    body = {
        "mentions": [
            {"kind": "equipment", "identifier": "T1", "page": 1},
            {"kind": "cable", "identifier": "W-152", "page": 2},
        ]
    }

    first = api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json=body,
    )
    second = api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json=body,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    listing = api_client.get(
        f"/documents/{document['id']}/engineering-index"
    )

    assert sorted(
        entry["identifier"] for entry in listing.json()
    ) == ["T1", "W-152"]


def test_replace_document_index_swaps_in_changed_data(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json={
            "mentions": [
                {"kind": "equipment", "identifier": "T1"},
            ]
        },
    )
    response = api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json={
            "mentions": [
                {"kind": "equipment", "identifier": "T2"},
            ]
        },
    )

    assert response.status_code == 200
    assert [entry["identifier"] for entry in response.json()] == ["T2"]

    listing = api_client.get(
        f"/documents/{document['id']}/engineering-index"
    )

    assert [entry["identifier"] for entry in listing.json()] == ["T2"]


def test_replace_document_index_rejects_a_canonical_library_document(
    api_client: TestClient,
) -> None:
    document = _upload_document(
        api_client,
        project_id=None,
        scope="canonical_library",
    )

    response = api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json={"mentions": [{"kind": "equipment", "identifier": "T1"}]},
    )

    assert response.status_code == 422


def test_replace_document_index_rejects_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.put(
        f"/documents/{document['id']}/engineering-index",
        json={"mentions": [{"kind": "equipment", "identifier": "T1"}]},
    )

    assert response.status_code == 409


def test_replace_document_index_returns_404_for_an_unknown_document(
    api_client: TestClient,
) -> None:
    response = api_client.put(
        "/documents/999/engineering-index",
        json={"mentions": [{"kind": "equipment", "identifier": "T1"}]},
    )

    assert response.status_code == 404


def test_clear_document_index_removes_entries_but_keeps_the_document(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )

    response = api_client.delete(
        f"/documents/{document['id']}/engineering-index"
    )

    assert response.status_code == 204

    listing = api_client.get(
        f"/documents/{document['id']}/engineering-index"
    )

    assert listing.json() == []

    documents = api_client.get(
        "/documents/",
        params={"project_id": project["id"]},
    )

    assert [d["id"] for d in documents.json()] == [document["id"]]


def test_clear_document_index_does_not_affect_a_different_project(
    api_client: TestClient,
) -> None:
    project_a = _create_project(api_client, code="ALPHA-002")
    project_b = _create_project(api_client, code="ALPHA-003")
    document_a = _upload_document(api_client, project_id=project_a["id"])
    document_b = _upload_document(api_client, project_id=project_b["id"])

    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document_a["id"],
            "kind": "equipment",
            "identifier": "T1",
        },
    )
    api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document_b["id"],
            "kind": "equipment",
            "identifier": "T2",
        },
    )

    api_client.delete(f"/documents/{document_a['id']}/engineering-index")

    response = api_client.get(
        f"/projects/{project_b['id']}/engineering-index"
    )

    assert [entry["identifier"] for entry in response.json()] == ["T2"]


def test_clear_document_index_rejects_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.delete(
        f"/documents/{document['id']}/engineering-index"
    )

    assert response.status_code == 409


def test_create_index_entry_accepts_a_non_page_locator(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "cable",
            "identifier": "W-152",
            "locator_kind": "cell_range",
            "locator_value": "B12:C15",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["locator_kind"] == "cell_range"
    assert body["locator_value"] == "B12:C15"
    assert body["page"] is None


def test_create_index_entry_rejects_a_page_combined_with_another_locator_kind(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])

    response = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "T1",
            "page": 3,
            "locator_kind": "sheet",
            "locator_value": "Sheet1",
        },
    )

    assert response.status_code == 422
