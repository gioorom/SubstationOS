from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.domain.engineering_session.engineering_session_builder import (
    build_initial_session,
)
from app.schemas.engineering_session import EngineeringSessionRead

NOW = datetime(2026, 1, 1, 20, 0, 0)


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


def _session_json(project_id: int, session_id: str) -> dict:
    session = build_initial_session(
        project_id=project_id, session_id=session_id, now=NOW
    ).session
    return json.loads(EngineeringSessionRead.from_domain(session).model_dump_json())


def test_build_returns_an_empty_working_memory_for_a_fresh_conversation(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "WM-001")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    session_json = _session_json(project["id"], "sess-1")

    response = api_client.post(
        f"/projects/{project['id']}/working-memory/build",
        json={"conversation": conversation, "engineering_session": session_json},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["working_memory"]["entries"] == []
    assert body["validation"]["valid"] is True


def test_build_surfaces_an_open_question(api_client: TestClient) -> None:
    project = _create_project(api_client, "WM-002")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    ).json()["conversation"]
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/add-message",
        json={"conversation": conversation, "role": "user", "text": "Which breaker?"},
    ).json()["conversation"]
    session_json = _session_json(project["id"], "sess-1")

    response = api_client.post(
        f"/projects/{project['id']}/working-memory/build",
        json={"conversation": conversation, "engineering_session": session_json},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["working_memory"]["entries"][0]["entry_type"] == "open_question"
    assert body["working_memory"]["entries"][0]["content"] == "Which breaker?"


def test_rebuild_matches_build(api_client: TestClient) -> None:
    project = _create_project(api_client, "WM-003")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    session_json = _session_json(project["id"], "sess-1")

    body = {"conversation": conversation, "engineering_session": session_json}
    build_response = api_client.post(
        f"/projects/{project['id']}/working-memory/build", json=body
    ).json()
    rebuild_response = api_client.post(
        f"/projects/{project['id']}/working-memory/rebuild", json=body
    ).json()

    assert (
        build_response["working_memory"]["entries"]
        == rebuild_response["working_memory"]["entries"]
    )
    assert (
        build_response["working_memory"]["working_memory_id"]
        == rebuild_response["working_memory"]["working_memory_id"]
    )


def test_project_id_mismatch_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "WM-004")
    other_project = _create_project(api_client, "WM-005")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    session_json = _session_json(project["id"], "sess-1")

    response = api_client.post(
        f"/projects/{other_project['id']}/working-memory/build",
        json={"conversation": conversation, "engineering_session": session_json},
    )

    assert response.status_code == 422


def test_session_mismatch_returns_422(api_client: TestClient) -> None:
    project = _create_project(api_client, "WM-006")
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation", json={"session_id": "sess-1"}
    ).json()["conversation"]
    other_session_json = _session_json(project["id"], "sess-other")

    response = api_client.post(
        f"/projects/{project['id']}/working-memory/build",
        json={"conversation": conversation, "engineering_session": other_session_json},
    )

    assert response.status_code == 422
