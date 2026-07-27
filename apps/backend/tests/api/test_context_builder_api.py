from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, code: str = "CTX-001") -> dict:
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


def _build_and_execute_graph(api_client: TestClient, code: str) -> dict:
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

    batch = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()
    executed = api_client.post(f"/graph-executions/batches/{batch['id']}")
    assert executed.status_code == 200
    assert executed.json()["execution"]["status"] == "succeeded"

    return project


def _retrieve_candidates(api_client: TestClient, project_id: int, **body) -> dict:
    response = api_client.post(
        f"/projects/{project_id}/structured-retrieval/search", json=body
    )
    assert response.status_code == 200

    return response.json()["candidates"]


def test_build_endpoint_assembles_a_package_from_retrieved_candidates(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="CTX-BUILD-001")
    candidates = _retrieve_candidates(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )

    response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={"candidates": candidates},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    package = body["package"]
    assert package["project_id"] == project["id"]
    assert len(package["selected_candidates"]) == 1
    assert package["selected_candidates"][0]["primary_reference"]["canonical_id"] == "C-295"
    assert package["budget"]["exceeded"] is False
    assert package["metadata"]["context_builder_version"] == "1.0"


def test_build_endpoint_enforces_a_caller_supplied_budget(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="CTX-BUDGET-001")
    candidates = _retrieve_candidates(
        api_client, project["id"], mode="combined", entity_type="CABLE",
        attribute_name="rated_voltage",
    )

    response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={
            "candidates": candidates,
            "max_candidates": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package"]["budget"]["policy"]["max_candidates"] == 1
    assert len(body["package"]["selected_candidates"]) <= 1


def test_build_endpoint_on_an_empty_collection_is_a_successful_empty_package(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="CTX-EMPTY-001")

    response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={
            "candidates": {
                "candidates": [],
                "total_before_limit": 0,
                "returned_count": 0,
                "applied_limit": 20,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["package"]["selected_candidates"] == []
    assert body["package"]["warnings"] == []


def test_build_endpoint_rejects_an_invalid_project_id(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/projects/0/context-builder/build",
        json={
            "candidates": {
                "candidates": [],
                "total_before_limit": 0,
                "returned_count": 0,
                "applied_limit": 20,
            }
        },
    )

    assert response.status_code == 422


def test_build_endpoint_rejects_an_out_of_range_budget_value(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, code="CTX-INVALID-001")

    response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={
            "candidates": {
                "candidates": [],
                "total_before_limit": 0,
                "returned_count": 0,
                "applied_limit": 20,
            },
            "max_candidates": 0,
        },
    )

    assert response.status_code == 422


def test_build_endpoint_preserves_score_and_provenance_through_the_wire(
    api_client: TestClient,
) -> None:
    project = _build_and_execute_graph(api_client, code="CTX-PROV-001")
    candidates = _retrieve_candidates(
        api_client, project["id"], mode="entity_lookup",
        canonical_entity_id="CABLE:C-295",
    )

    response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={"candidates": candidates},
    )

    assert response.status_code == 200
    selected = response.json()["package"]["selected_candidates"][0]
    assert selected["score"]["total"] == candidates["candidates"][0]["score"]["total"]
    assert selected["graph_execution_ids"] == candidates["candidates"][0]["graph_execution_ids"]


def test_build_endpoint_response_is_deterministic(api_client: TestClient) -> None:
    project = _build_and_execute_graph(api_client, code="CTX-DETERM-001")
    candidates = _retrieve_candidates(
        api_client, project["id"], mode="entity_type_search", entity_type="CABLE"
    )
    payload = {"candidates": candidates}

    first = api_client.post(
        f"/projects/{project['id']}/context-builder/build", json=payload
    )
    second = api_client.post(
        f"/projects/{project['id']}/context-builder/build", json=payload
    )

    first_ids = [
        c["candidate_id"] for c in first.json()["package"]["selected_candidates"]
    ]
    second_ids = [
        c["candidate_id"] for c in second.json()["package"]["selected_candidates"]
    ]
    assert first_ids == second_ids
