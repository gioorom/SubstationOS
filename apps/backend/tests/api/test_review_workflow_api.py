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

    return response.json()["document"]


def _create_index_entry(
    api_client: TestClient,
    *,
    document_id: int,
    identifier: str = "T1",
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


def _create_claim(
    api_client: TestClient,
    *,
    engineering_index_entry_ids: list[int],
    subject: str = "T1",
) -> dict:
    response = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "existence",
            "subject": subject,
            "engineering_index_entry_ids": engineering_index_entry_ids,
        },
    )

    assert response.status_code == 201

    return response.json()


def _create_candidate(
    api_client: TestClient,
    *,
    proposed_claim_id: int,
) -> dict:
    response = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": proposed_claim_id},
    )

    assert response.status_code == 201

    return response.json()


def _propose_claim_for_a_fresh_document(
    api_client: TestClient,
    *,
    project_id: int,
    identifier: str = "T1",
) -> dict:
    document = _upload_document(api_client, project_id=project_id)
    entry = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier=identifier,
    )

    return _create_claim(
        api_client,
        engineering_index_entry_ids=[entry["id"]],
        subject=identifier,
    )


def test_create_review_candidate_for_a_proposed_claim(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )

    body = _create_candidate(api_client, proposed_claim_id=claim["id"])

    assert body["project_id"] == project["id"]
    assert body["proposed_claim_id"] == claim["id"]
    assert body["status"] == "pending"
    assert body["reviewed_by"] is None


def test_create_review_candidate_returns_404_for_an_unknown_claim(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": 999},
    )

    assert response.status_code == 404


def test_create_review_candidate_rejects_a_duplicate_open_candidate(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )

    _create_candidate(api_client, proposed_claim_id=claim["id"])

    response = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    )

    assert response.status_code == 409


def test_approve_review_candidate(api_client: TestClient) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    response = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["reviewed_by"] == "engineer@acme.com"
    assert body["reviewed_at"] is not None


def test_reject_review_candidate_requires_a_comment(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    response = api_client.post(
        f"/review-candidates/{candidate['id']}/reject",
        json={"reviewed_by": "engineer@acme.com"},
    )

    assert response.status_code == 422


def test_reject_review_candidate_with_a_comment(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    response = api_client.post(
        f"/review-candidates/{candidate['id']}/reject",
        json={
            "reviewed_by": "engineer@acme.com",
            "comment": "Identifier does not match the drawing.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["review_comment"] == (
        "Identifier does not match the drawing."
    )


def test_approved_candidate_cannot_be_resubmitted_to_pending(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])
    api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )

    response = api_client.post(
        f"/review-candidates/{candidate['id']}/resubmit",
        json={"reviewed_by": "author@acme.com"},
    )

    assert response.status_code == 409


def test_needs_changes_loops_back_to_pending_and_can_then_be_approved(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    needs_changes = api_client.post(
        f"/review-candidates/{candidate['id']}/request-changes",
        json={
            "reviewed_by": "engineer@acme.com",
            "comment": "Please confirm the rated voltage.",
        },
    )
    assert needs_changes.status_code == 200
    assert needs_changes.json()["status"] == "needs_changes"

    resubmitted = api_client.post(
        f"/review-candidates/{candidate['id']}/resubmit",
        json={"reviewed_by": "author@acme.com"},
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending"

    approved = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_get_review_candidate_returns_404_for_an_unknown_candidate(
    api_client: TestClient,
) -> None:
    response = api_client.get("/review-candidates/999")

    assert response.status_code == 404


def test_list_pending_review_candidates(api_client: TestClient) -> None:
    project = _create_project(api_client)
    document = _upload_document(api_client, project_id=project["id"])
    entry_a = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="T1",
    )
    entry_b = _create_index_entry(
        api_client,
        document_id=document["id"],
        identifier="T2",
    )
    claim_a = _create_claim(
        api_client,
        engineering_index_entry_ids=[entry_a["id"]],
        subject="T1",
    )
    claim_b = _create_claim(
        api_client,
        engineering_index_entry_ids=[entry_b["id"]],
        subject="T2",
    )
    _create_candidate(api_client, proposed_claim_id=claim_a["id"])
    approved = _create_candidate(
        api_client,
        proposed_claim_id=claim_b["id"],
    )
    api_client.post(
        f"/review-candidates/{approved['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )

    response = api_client.get("/review-candidates/pending")

    assert response.status_code == 200
    body = response.json()
    assert [candidate["proposed_claim_id"] for candidate in body] == [
        claim_a["id"]
    ]


def test_list_review_candidates_for_project_does_not_leak_across_projects(
    api_client: TestClient,
) -> None:
    project_a = _create_project(api_client, code="ALPHA-002")
    project_b = _create_project(api_client, code="ALPHA-003")
    claim_a = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project_a["id"],
    )
    claim_b = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project_b["id"],
    )
    _create_candidate(api_client, proposed_claim_id=claim_a["id"])
    _create_candidate(api_client, proposed_claim_id=claim_b["id"])

    response = api_client.get(
        f"/projects/{project_a['id']}/review-candidates"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["proposed_claim_id"] == claim_a["id"]


def test_review_history_records_every_decision(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    api_client.post(
        f"/review-candidates/{candidate['id']}/request-changes",
        json={
            "reviewed_by": "engineer@acme.com",
            "comment": "Please confirm the rated voltage.",
        },
    )
    api_client.post(
        f"/review-candidates/{candidate['id']}/resubmit",
        json={"reviewed_by": "author@acme.com"},
    )
    api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )

    response = api_client.get(
        f"/review-candidates/{candidate['id']}/history"
    )

    assert response.status_code == 200
    body = response.json()
    assert [event["to_status"] for event in body] == [
        "needs_changes",
        "pending",
        "approved",
    ]


def test_review_history_returns_404_for_an_unknown_candidate(
    api_client: TestClient,
) -> None:
    response = api_client.get("/review-candidates/999/history")

    assert response.status_code == 404


def test_review_candidate_rejects_an_archived_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client)
    claim = _propose_claim_for_a_fresh_document(
        api_client,
        project_id=project["id"],
    )
    candidate = _create_candidate(api_client, proposed_claim_id=claim["id"])

    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    response = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer@acme.com"},
    )

    assert response.status_code == 409


def test_review_candidate_shape_no_longer_accepts_an_engineering_index_entry_id(
    api_client: TestClient,
) -> None:
    """
    Migration proof for Milestone 10.1: ``ReviewCandidate`` now
    references a Proposed Claim, not an Engineering Index entry
    directly. The old request shape is rejected as a validation error,
    not silently accepted with a missing ``proposed_claim_id``.
    """

    response = api_client.post(
        "/review-candidates",
        json={"engineering_index_entry_id": 1},
    )

    assert response.status_code == 422
