from __future__ import annotations

import json
from datetime import datetime

import io

from fastapi.testclient import TestClient

from app.schemas.context_builder import ContextPackageRead
from app.services import context_builder_service

from tests._governed_context import asset_item, results_for

NOW = datetime(2026, 1, 1, 12, 0, 0)


def _create_project(api_client: TestClient, code: str = "PB-001") -> dict:
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

    return response.json()["document"]


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


#: EPIC 31.4 removed ``_build_and_execute_graph``.
#:
#: It created a project, uploaded a document, approved a claim,
#: canonicalised it, built a Canonical Facts graph batch and executed it -
#: so that legacy Structured Retrieval had something to find. None of that
#: reaches these tests any more: since EPIC 31.3 the governed
#: ``ContextPackage`` they need is assembled in process, and EPIC 31.4
#: withdrew the four route groups the fixture drove. A project is all that
#: is left to create, and ``_create_project`` already does it.


def _context_package_json(project_id: int, *, count: int = 1) -> dict:
    """
    A governed ``ContextPackage``, serialized.

    Built in-process rather than through an endpoint: the
    ``/context-builder/build`` route was withdrawn by EPIC 31.3, because
    a governed context cannot honestly be assembled from a request body
    (provenance a caller asserts is not provenance). These two routes
    still accept a package because they persist nothing and write no
    graph - see ``app/schemas/context_builder.py``.
    """

    package = context_builder_service.build_context_package(
        project_id=project_id,
        results=results_for(
            tuple(
                asset_item(
                    f"node-tr{index}",
                    f"TR{index}",
                    statement_key=f"statement-{index}",
                    project_id=project_id,
                )
                for index in range(count)
            ),
            project_id=project_id,
        ),
        now=NOW,
    ).package

    return json.loads(
        ContextPackageRead.from_domain(package).model_dump_json()
    )


def test_build_endpoint_assembles_a_prompt_package(api_client: TestClient) -> None:
    project = _create_project(api_client, code="PB-BUILD-001")
    package = _context_package_json(project["id"])

    response = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build",
        json={"context_package": package},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    prompt = body["package"]
    assert prompt["project_id"] == project["id"]
    assert len(prompt["sections"]) == 11
    assert prompt["retrieved_knowledge"]["enabled"] is True
    assert len(prompt["constraints"]) == 5
    assert len(prompt["instructions"]) == 3
    assert body["validation"]["valid"] is True


def test_build_endpoint_on_an_empty_context_package_is_a_valid_empty_prompt(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="PB-EMPTY-001")
    package = _context_package_json(project["id"], count=0)

    response = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build",
        json={"context_package": package},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package"]["statistics"]["knowledge_item_count"] == 0
    disabled = [s for s in body["package"]["sections"] if not s["enabled"]]
    assert any(s["section_type"] == "selected_knowledge" for s in disabled)
    assert body["validation"]["valid"] is True


def test_build_endpoint_rejects_a_mismatched_project_id(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="PB-MISMATCH-001")
    other_project = _create_project(api_client, code="PB-MISMATCH-002")
    package = _context_package_json(project["id"])

    response = api_client.post(
        f"/projects/{other_project['id']}/prompt-builder/build",
        json={"context_package": package},
    )

    assert response.status_code == 422


def test_build_endpoint_rejects_an_invalid_project_id(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="PB-INVALID-001")
    package = _context_package_json(project["id"])

    response = api_client.post(
        "/projects/0/prompt-builder/build",
        json={"context_package": {**package, "project_id": 0}},
    )

    assert response.status_code == 422


def test_build_endpoint_preserves_evidence_references(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="PB-EVIDENCE-001")
    package = _context_package_json(project["id"])

    response = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build",
        json={"context_package": package},
    )

    assert response.status_code == 200
    references = response.json()["package"]["references"]
    assert len(references) == 1
    assert references[0]["item_id"] == package["selected_items"][0]["item_id"]


def test_build_endpoint_response_is_deterministic(api_client: TestClient) -> None:
    project = _create_project(api_client, code="PB-DETERM-001")
    package = _context_package_json(project["id"])
    payload = {"context_package": package}

    first = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build", json=payload
    ).json()["package"]
    second = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build", json=payload
    ).json()["package"]

    # Everything is deterministic except metadata.assembled_at, which
    # legitimately varies between two real, separately timed API calls
    # (the router stamps `now` from the wall clock at the boundary -
    # assembly itself is deterministic given the same `now`, per
    # ADR-0012).
    assert first["sections"] == second["sections"]
    assert first["statistics"] == second["statistics"]
    assert first["references"] == second["references"]
    assert first["version"] == second["version"]
