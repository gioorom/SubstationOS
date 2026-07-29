"""
API tests for Document Ingestion (Milestone 25.1), over the real upload
endpoint and a real (in-memory) database - so the full path an engineer
actually takes is proved: upload a file, ingest it, read the record.

**Since Milestone 26.2 the upload itself ingests.** A project-scoped
upload now runs the consolidated pipeline, so a document already carries
one job before anything here posts a second. The assertions below account
for that job rather than pretending it is absent: it is the pipeline
working, and a test that ignored it would be testing a system nobody
runs.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient


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


def _upload(api_client: TestClient, project_id: int, filename: str) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"scope": "project", "project_id": str(project_id)},
    )
    assert response.status_code == 200

    return response.json()["document"]


def _ingest(api_client: TestClient, document_id: int):
    return api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document_id}
    )


# --- The full path ------------------------------------------------------


def test_an_uploaded_document_ingests_to_a_recorded_job(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INGEST-001")
    document = _upload(api_client, project["id"], "schema.pdf")

    response = _ingest(api_client, document["id"])

    assert response.status_code == 201
    job = response.json()

    assert job["document_id"] == document["id"]
    assert job["project_id"] == project["id"]
    assert job["state"] == "processed"
    assert job["outcome"] == "ready_for_extraction"
    assert job["ready_for_extraction"] is True
    assert job["pipeline_version"]
    assert job["attempt_count"] == 1
    assert job["completed_at"] is not None


def test_the_job_carries_the_document_snapshot(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INGEST-002")
    document = _upload(api_client, project["id"], "schema.pdf")

    job = _ingest(api_client, document["id"]).json()
    snapshot = job["document"]

    assert snapshot is not None
    assert snapshot["document_id"] == document["id"]
    assert snapshot["title"] == "schema.pdf"
    assert snapshot["document_format"] == document["file_format"]
    assert snapshot["revision"] == document["revision"]


def test_the_job_is_readable_afterwards(api_client: TestClient) -> None:
    project = _create_project(api_client, "INGEST-003")
    document = _upload(api_client, project["id"], "schema.pdf")

    created = _ingest(api_client, document["id"]).json()
    reread = api_client.get(
        f"/documents/ingestion/jobs/{created['id']}"
    )

    assert reread.status_code == 200
    assert reread.json() == created


def test_jobs_are_listed_for_a_document_and_a_project(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INGEST-004")
    document = _upload(api_client, project["id"], "schema.pdf")

    before = len(
        api_client.get(
            f"/documents/{document['id']}/ingestion/jobs"
        ).json()
    )
    _ingest(api_client, document["id"])

    by_document = api_client.get(
        f"/documents/{document['id']}/ingestion/jobs"
    )
    by_project = api_client.get(
        f"/projects/{project['id']}/ingestion/jobs"
    )

    # Counted relative to what the upload itself already recorded
    # (Milestone 26.2), so this stays a test of the two listing endpoints
    # rather than of how many times the pipeline has run.
    assert by_document.status_code == 200
    assert len(by_document.json()) == before + 1
    assert by_project.status_code == 200
    assert len(by_project.json()) == before + 1


# --- Failures ------------------------------------------------------------


def test_a_missing_document_is_a_failed_job_not_a_client_error(
    api_client: TestClient,
) -> None:
    """The request was well-formed and ingestion answered it correctly, so
    the attempt is recorded rather than thrown away."""

    response = _ingest(api_client, 9999)

    assert response.status_code == 201
    job = response.json()

    assert job["state"] == "failed"
    assert job["outcome"] == "failed"
    assert job["failure"]["code"] == "document_not_found"
    assert job["ready_for_extraction"] is False


def test_an_unknown_job_returns_404(api_client: TestClient) -> None:
    assert api_client.get("/documents/ingestion/jobs/9999").status_code == 404


def test_a_non_positive_project_id_returns_422(
    api_client: TestClient,
) -> None:
    assert api_client.get("/projects/0/ingestion/jobs").status_code == 422


def test_retrying_a_completed_job_conflicts(api_client: TestClient) -> None:
    """A completed job is never re-run in place - re-ingestion is a new
    job, so what was processed when is never overwritten."""

    project = _create_project(api_client, "INGEST-005")
    document = _upload(api_client, project["id"], "schema.pdf")

    job = _ingest(api_client, document["id"]).json()
    assert job["state"] == "processed"

    retry = api_client.post(
        f"/documents/ingestion/jobs/{job['id']}/retry"
    )

    assert retry.status_code == 409


def test_a_failed_job_can_be_retried_over_the_api(
    api_client: TestClient,
) -> None:
    failed = _ingest(api_client, 9999).json()
    assert failed["state"] == "failed"

    retried = api_client.post(
        f"/documents/ingestion/jobs/{failed['id']}/retry"
    )

    assert retried.status_code == 200
    body = retried.json()
    assert body["id"] == failed["id"]
    assert body["attempt_count"] == 2


def test_retrying_an_unknown_job_returns_404(
    api_client: TestClient,
) -> None:
    assert (
        api_client.post("/documents/ingestion/jobs/9999/retry").status_code
        == 404
    )


# --- Re-ingestion --------------------------------------------------------


def test_a_completed_document_can_be_ingested_again(
    api_client: TestClient,
) -> None:
    """Each request produces its own job, and the accumulated jobs are
    the document's audit trail - including the one the upload itself
    created (Milestone 26.2)."""

    project = _create_project(api_client, "INGEST-006")
    document = _upload(api_client, project["id"], "schema.pdf")

    from_upload = api_client.get(
        f"/documents/{document['id']}/ingestion/jobs"
    ).json()
    first = _ingest(api_client, document["id"]).json()
    second = _ingest(api_client, document["id"]).json()

    assert first["id"] != second["id"]

    listed = api_client.get(
        f"/documents/{document['id']}/ingestion/jobs"
    ).json()
    assert [job["id"] for job in listed] == [
        *[job["id"] for job in from_upload],
        first["id"],
        second["id"],
    ]


def test_re_ingesting_an_unchanged_document_concludes_identically(
    api_client: TestClient,
) -> None:
    project = _create_project(api_client, "INGEST-007")
    document = _upload(api_client, project["id"], "schema.pdf")

    first = _ingest(api_client, document["id"]).json()
    second = _ingest(api_client, document["id"]).json()

    assert first["outcome"] == second["outcome"]
    assert first["state"] == second["state"]
    assert first["document"] == second["document"]


def test_the_request_body_accepts_no_lifecycle_or_outcome(
    api_client: TestClient,
) -> None:
    """A caller cannot assert what ingestion concluded."""

    from app.schemas.document_ingestion import IngestDocumentRequestBody

    assert set(IngestDocumentRequestBody.model_fields) == {"document_id"}
