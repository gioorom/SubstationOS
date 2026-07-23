from __future__ import annotations

import io

import httpx
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


def _upload_file(
    api_client: TestClient,
    *,
    data: dict,
) -> httpx.Response:
    return api_client.post(
        "/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        data=data,
    )


def test_project_scoped_upload_requires_a_project_id(
    api_client: TestClient,
) -> None:
    response = _upload_file(api_client, data={"scope": "project"})

    assert response.status_code == 422


def test_canonical_library_upload_rejects_a_project_id(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = _upload_file(
        api_client,
        data={
            "scope": "canonical_library",
            "project_id": str(project["id"]),
        },
    )

    assert response.status_code == 422


def test_canonical_library_upload_without_a_project_succeeds(
    api_client: TestClient,
) -> None:
    response = _upload_file(
        api_client,
        data={"scope": "canonical_library"},
    )

    assert response.status_code == 200
    assert response.json()["scope"] == "canonical_library"


def test_project_scoped_upload_to_a_draft_project_succeeds(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)

    response = _upload_file(
        api_client,
        data={
            "scope": "project",
            "project_id": str(project["id"]),
        },
    )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"


def test_upload_to_an_archived_project_is_rejected(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = _upload_file(
        api_client,
        data={
            "scope": "project",
            "project_id": str(project["id"]),
        },
    )

    assert response.status_code == 409
