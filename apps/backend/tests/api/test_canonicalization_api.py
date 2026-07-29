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

    return response.json()["document"]


def _create_index_entry(
    api_client: TestClient,
    document_id: int,
    identifier: str = "C-295",
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


def _create_approved_candidate(
    api_client: TestClient,
    *,
    subject: str = "Cable 295",
) -> tuple[dict, dict, dict]:
    project = _create_project(api_client)
    document = _upload_document(api_client, project["id"])
    entry = _create_index_entry(api_client, document["id"])

    claim_response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": subject,
            "engineering_index_entry_ids": [entry["id"]],
        },
    )
    assert claim_response.status_code == 201
    claim = claim_response.json()

    candidate_response = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    )
    assert candidate_response.status_code == 201
    candidate = candidate_response.json()

    approve_response = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer.smith"},
    )
    assert approve_response.status_code == 200

    return project, document, approve_response.json()


def test_canonicalize_review_candidate_creates_a_fact(
    api_client: TestClient,
) -> None:
    project, document, candidate = _create_approved_candidate(api_client)

    response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["fact"]["subject"]["value"] == "CABLE:C-295"
    assert body["fact"]["project_id"] == project["id"]


def test_canonicalize_review_candidate_is_idempotent_over_the_api(
    api_client: TestClient,
) -> None:
    _, _, candidate = _create_approved_candidate(api_client)

    first = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )
    second = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )

    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert first.json()["fact"]["id"] == second.json()["fact"]["id"]


def test_canonicalize_rejects_a_non_approved_candidate(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project["id"])
    entry = _create_index_entry(api_client, document["id"])

    claim_response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": "Cable 295",
            "engineering_index_entry_ids": [entry["id"]],
        },
    )
    claim = claim_response.json()

    candidate_response = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    )
    candidate = candidate_response.json()

    response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )

    assert response.status_code == 409


def test_canonicalize_returns_404_for_an_unknown_candidate(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": 999},
    )

    assert response.status_code == 404


def test_get_canonical_fact_returns_404_for_an_unknown_fact(
    api_client: TestClient,
) -> None:
    response = api_client.get("/canonical-facts/999")

    assert response.status_code == 404


def test_get_canonical_fact_returns_the_created_fact(
    api_client: TestClient,
) -> None:
    _, _, candidate = _create_approved_candidate(api_client)
    created = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    ).json()

    response = api_client.get(
        f"/canonical-facts/{created['fact']['id']}"
    )

    assert response.status_code == 200
    assert response.json()["subject"]["value"] == "CABLE:C-295"


def test_list_canonical_facts_for_project(
    api_client: TestClient,
) -> None:
    project, _, candidate = _create_approved_candidate(api_client)
    api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )

    response = api_client.get(
        f"/projects/{project['id']}/canonical-facts"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_canonical_facts_for_document(
    api_client: TestClient,
) -> None:
    _, document, candidate = _create_approved_candidate(api_client)
    api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": candidate["id"]},
    )

    response = api_client.get(
        f"/documents/{document['id']}/canonical-facts"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_relationship_claim_canonicalizes_both_entity_references(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project["id"])
    subject_entry = _create_index_entry(api_client, document["id"], "C-295")

    claim_response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable 295",
            "predicate": "feeds",
            "object": "TR2",
            "engineering_index_entry_ids": [subject_entry["id"]],
        },
    )
    assert claim_response.status_code == 201
    claim = claim_response.json()

    candidate = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    ).json()
    approved = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer.smith"},
    ).json()

    response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": approved["id"]},
    )

    assert response.status_code == 200
    fact = response.json()["fact"]
    assert fact["subject"]["value"] == "CABLE:C-295"
    assert fact["predicate_value"] == "FEEDS"
    assert fact["object_entity"]["value"] == "TRANSFORMER:TR-02"
    assert fact["object_value"] is None
