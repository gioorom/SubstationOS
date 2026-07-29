from __future__ import annotations

from fastapi.testclient import TestClient


def _create_project(
    api_client: TestClient,
    *,
    code: str = "ALPHA-001",
    name: str = "Alpha Substation",
) -> dict:
    response = api_client.post(
        "/projects/",
        json={
            "name": name,
            "code": code,
            "customer": "Acme Utilities",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_create_project_returns_a_draft_project(
    api_client: TestClient,
) -> None:
    body = _create_project(api_client)

    assert body["lifecycle_state"] == "draft"
    assert body["canonical_domain_version"] == "unversioned"
    assert body["name"] == "Alpha Substation"


def test_create_project_rejects_a_duplicate_code(
    api_client: TestClient,
) -> None:
    _create_project(api_client, code="ALPHA-001")

    response = api_client.post(
        "/projects/",
        json={
            "name": "Alpha Substation Two",
            "code": "ALPHA-001",
            "customer": "Acme Utilities",
        },
    )

    assert response.status_code == 409


def test_create_project_rejects_a_blank_name(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/projects/",
        json={
            "name": "",
            "code": "ALPHA-001",
            "customer": "Acme Utilities",
        },
    )

    assert response.status_code == 422


def test_get_project_returns_404_for_an_unknown_id(
    api_client: TestClient,
) -> None:
    response = api_client.get("/projects/999")

    assert response.status_code == 404


def test_get_project_returns_the_created_project(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)

    response = api_client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json()["code"] == "ALPHA-001"


def test_list_projects_excludes_deleted_by_default(
    api_client: TestClient,
) -> None:
    kept = _create_project(api_client, code="ALPHA-001")
    removed = _create_project(api_client, code="BETA-001")

    api_client.post(f"/projects/{removed['id']}/activate")
    api_client.post(f"/projects/{removed['id']}/archive")
    api_client.delete(f"/projects/{removed['id']}")

    response = api_client.get("/projects/")

    codes = {project["code"] for project in response.json()["items"]}

    assert kept["code"] in codes
    assert removed["code"] not in codes


def test_list_projects_includes_deleted_when_requested(
    api_client: TestClient,
) -> None:
    removed = _create_project(api_client, code="BETA-001")

    api_client.post(f"/projects/{removed['id']}/activate")
    api_client.post(f"/projects/{removed['id']}/archive")
    api_client.delete(f"/projects/{removed['id']}")

    response = api_client.get("/projects/?include_deleted=true")

    codes = {project["code"] for project in response.json()["items"]}

    assert removed["code"] in codes


def test_activate_moves_project_from_draft_to_active(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)

    response = api_client.post(f"/projects/{created['id']}/activate")

    assert response.status_code == 200
    assert response.json()["lifecycle_state"] == "active"


def test_archiving_a_draft_project_is_rejected(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)

    response = api_client.post(f"/projects/{created['id']}/archive")

    assert response.status_code == 409


def test_full_lifecycle_round_trip(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)
    project_id = created["id"]

    activate_response = api_client.post(
        f"/projects/{project_id}/activate"
    )
    assert activate_response.json()["lifecycle_state"] == "active"

    archive_response = api_client.post(f"/projects/{project_id}/archive")
    assert archive_response.json()["lifecycle_state"] == "archived"

    delete_response = api_client.delete(f"/projects/{project_id}")
    assert delete_response.json()["lifecycle_state"] == "deleted"

    restore_response = api_client.post(
        f"/projects/{project_id}/restore"
    )
    assert restore_response.json()["lifecycle_state"] == "archived"

    restore_again_response = api_client.post(
        f"/projects/{project_id}/restore"
    )
    assert restore_again_response.json()["lifecycle_state"] == "active"


def test_update_metadata_on_a_draft_project(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)

    response = api_client.patch(
        f"/projects/{created['id']}",
        json={"location": "Turin"},
    )

    assert response.status_code == 200
    assert response.json()["location"] == "Turin"


def test_update_metadata_on_an_archived_project_is_rejected(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)
    project_id = created["id"]

    api_client.post(f"/projects/{project_id}/activate")
    api_client.post(f"/projects/{project_id}/archive")

    response = api_client.patch(
        f"/projects/{project_id}",
        json={"location": "Turin"},
    )

    assert response.status_code == 409


def test_update_metadata_does_not_accept_a_code_field(
    api_client: TestClient,
) -> None:
    created = _create_project(api_client)

    response = api_client.patch(
        f"/projects/{created['id']}",
        json={"code": "SHOULD-BE-IGNORED"},
    )

    assert response.status_code == 200
    assert response.json()["code"] == created["code"]
