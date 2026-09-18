"""
The upload path, end to end, for Document Version Identity (ADR-0036).

The milestone's claim is that a document records the identity of the
bytes that were actually persisted, at creation, once. Everything below
exercises the real route so that claim is tested where it is made: the
digest is recomputed from the file on disk, the metadata that must not
reach it is varied, and the commit is made to fail so the compensation
has something to compensate.

**Storage is redirected.** ``app.services.storage.BASE_STORAGE`` is a
module constant pointing at the deployment storage root, and a test that
uploaded through it would leave real files in the repository's
``storage/`` tree. Every test here writes into a temporary directory
instead, which is also what makes "exactly one file" a statement about
this test rather than about everything that ran before it.
"""

from __future__ import annotations

import hashlib
import io
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.domain.document_ingestion.ingestion_models import (
    IngestionOutcome,
    IngestionState,
)
from app.domain.project.project_document_scope import DocumentScope
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.document_ingestion import DocumentIngestionJob
from app.routers import documents as documents_router
from app.services import storage

PDF = b"%PDF-1.7 Schema unifilare - sezione MT"
OTHER_PDF = b"%PDF-1.7 Schema unifilare - revisione 01"

EMPTY_DIGEST = (
    "e3b0c44298fc1c149afbf4c8996fb924"
    "27ae41e4649b934ca495991b7852b855"
)


@pytest.fixture()
def storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A storage root belonging to this test, so nothing is written into
    the deployment tree and "how many files exist" has an answer."""

    monkeypatch.setattr(storage, "BASE_STORAGE", tmp_path)

    return tmp_path


def _files(storage_root: Path) -> list[Path]:
    return sorted(
        path for path in storage_root.rglob("*") if path.is_file()
    )


def _project(api_client: TestClient, code: str = "CP-100") -> dict:
    response = api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": code,
            "customer": "Distributore Nazionale",
        },
    )

    assert response.status_code == 201

    return response.json()


def _upload(
    client: TestClient,
    *,
    filename: str = "schema.pdf",
    content: bytes = PDF,
    mime_type: str = "application/pdf",
    project_id: int | None = None,
    extra: dict[str, str] | None = None,
) -> httpx.Response:
    data: dict[str, str] = (
        {"scope": "project", "project_id": str(project_id)}
        if project_id is not None
        else {"scope": "canonical_library"}
    )
    data.update(extra or {})

    return client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), mime_type)},
        data=data,
    )


def _uploaded(client: TestClient, **kwargs) -> dict:
    response = _upload(client, **kwargs)

    assert response.status_code == 200, response.text

    return response.json()["document"]


def _detail(client: TestClient, document_id: int) -> dict:
    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200

    return response.json()


# --- The digest describes what is on disk (§8) --------------------------


def test_the_recorded_digest_matches_the_stored_file(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 13.**

    The whole milestone rests on the digest covering the bytes that were
    persisted rather than some bytes that passed through the process.
    Recomputing it from the file the route actually wrote is the only
    assertion that would notice if ``save_file`` stopped hashing what it
    writes - the ADR names that as the place a future change could
    quietly drop the guarantee.
    """

    document = _uploaded(api_client)

    record = db_session.get(DocumentRecord, document["id"])
    stored_bytes = Path(record.file_path).read_bytes()

    assert record.content_checksum == hashlib.sha256(
        stored_bytes
    ).hexdigest()
    assert record.content_size_bytes == len(stored_bytes)
    assert record.content_checksum_algorithm == "sha256"


def test_the_detail_reports_the_digest_of_the_stored_file(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """The same guarantee as seen by a caller, since the column is only
    useful if the public read serves it."""

    document = _uploaded(api_client)

    record = db_session.get(DocumentRecord, document["id"])
    stored_bytes = Path(record.file_path).read_bytes()

    detail = _detail(api_client, document["id"])

    assert detail["content_checksum"] == hashlib.sha256(
        stored_bytes
    ).hexdigest()
    assert detail["size_bytes"] == len(stored_bytes)


# --- What must not reach the identity (§10) -----------------------------


def test_the_uploader_does_not_affect_the_identity(
    api_client: TestClient,
    administrator_client: TestClient,
    storage_root: Path,
) -> None:
    """
    **ADR-0036 §28 row 6.**

    ADR-0035 refuses this failure by name: running the pipeline twice
    under two logins would produce two different artefacts. Who uploaded
    is recorded on the *action*, and an identity that was a function of
    a person would make every artifact keyed to it a function of a
    person too.
    """

    first = _uploaded(api_client)
    second = _uploaded(administrator_client)

    assert (
        _detail(api_client, first["id"])["content_checksum"]
        == _detail(api_client, second["id"])["content_checksum"]
    )


def test_the_project_and_scope_do_not_affect_the_identity(
    api_client: TestClient, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 7.**

    The same drawing filed against a project and against the Canonical
    Library is the same bytes. ADR-0005's scope rule is about filing,
    not content, and scope, category, revision and project name are all
    editable after upload - so an identity that depended on one of them
    would be re-written by ordinary registry housekeeping.
    """

    project = _project(api_client)

    filed = _uploaded(api_client, project_id=project["id"])
    library = _uploaded(api_client)

    filed_detail = _detail(api_client, filed["id"])
    library_detail = _detail(api_client, library["id"])

    assert filed_detail["scope"] != library_detail["scope"]
    assert (
        filed_detail["content_checksum"]
        == library_detail["content_checksum"]
    )


def test_the_upload_timestamp_does_not_affect_the_identity(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 5.**

    ``uploaded_at`` is a wall-clock reading, and a wall-clock reading is
    not a property of the bytes. If it reached the digest the identity
    would stop being reproducible - the same file would identify
    differently every time it was stored - and every test built on it
    would become time-dependent.
    """

    first = _uploaded(api_client)
    second = _uploaded(api_client)

    records = [
        db_session.get(DocumentRecord, first["id"]),
        db_session.get(DocumentRecord, second["id"]),
    ]

    assert records[0].uploaded_at != records[1].uploaded_at
    assert records[0].content_checksum == records[1].content_checksum


def test_a_caller_cannot_supply_the_content_identity(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 17**, at the boundary rather than in the schema.

    AF-PROV-002 already fails any persisting route whose body declares a
    governed provenance field. This asserts the behaviour that invariant
    exists to produce: a caller who sends one anyway is not believed,
    and the value recorded is the one the server computed from the bytes
    it wrote.
    """

    claimed = "f" * 64

    document = _uploaded(
        api_client,
        extra={
            "content_checksum": claimed,
            "content_size_bytes": "999999",
        },
    )

    record = db_session.get(DocumentRecord, document["id"])

    assert record.content_checksum == hashlib.sha256(PDF).hexdigest()
    assert record.content_size_bytes == len(PDF)


# --- The empty upload (§8, §19) -----------------------------------------


def test_a_zero_byte_upload_records_no_identity(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 14**, on the real route.

    A zero-byte upload is accepted and stored - the refusal is of the
    *identity*, not of the request - and records nothing, because there
    is nothing to identify.
    """

    document = _uploaded(api_client, filename="empty.pdf", content=b"")

    record = db_session.get(DocumentRecord, document["id"])

    assert record.content_checksum is None
    assert record.content_checksum_algorithm is None
    assert record.content_size_bytes is None


def test_a_zero_byte_upload_never_records_the_empty_digest(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    SHA-256 of nothing is a real, well-defined value, and that is the
    problem: recorded as an identity it would make every empty document
    in the system look like the same document, and would let a zero-byte
    upload pass as ready for extraction.

    Asserted against the literal so that "record it anyway" is caught by
    name, rather than only by a nullability check a future default could
    satisfy.
    """

    document = _uploaded(api_client, filename="empty.pdf", content=b"")

    record = db_session.get(DocumentRecord, document["id"])
    detail = _detail(api_client, document["id"])

    assert record.content_checksum != EMPTY_DIGEST
    assert detail["content_checksum"] != EMPTY_DIGEST


# --- Failure atomicity (§20) --------------------------------------------


def test_a_failed_commit_leaves_no_stored_file(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 15**, first half.

    The bytes are written before the row exists, which is the right
    order - the alternative leaves a committed row pointing at nothing,
    and that is a lie in the registry rather than invisible waste. So
    the write has to be compensated when the row never arrives, or the
    file sits in a tree excluded from version control that nothing ever
    reconciles.

    The table is dropped to produce a genuine commit failure - code
    deployed ahead of its migration is a real condition - rather than a
    simulated one.
    """

    db_session.execute(text("DROP TABLE documents"))
    db_session.commit()

    with pytest.raises(OperationalError):
        _upload(api_client)

    assert _files(storage_root) == []


def test_a_failed_commit_leaves_the_session_usable(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 15**, second half.

    The upload's commit was the only raw ``commit()`` outside an
    infrastructure adapter. A failed one leaves SQLAlchemy requiring an
    explicit rollback, and until that happens every later statement
    raises ``PendingRollbackError`` - and the handler makes several more
    queries after it, including the audit write that names who did this.
    """

    db_session.execute(text("DROP TABLE documents"))
    db_session.commit()

    with pytest.raises(OperationalError):
        _upload(api_client)

    # The assertion this test exists for: before the rule, this raised
    # PendingRollbackError.
    assert db_session.query(DocumentIngestionJob).count() == 0


def test_a_successful_upload_leaves_exactly_one_file_and_one_row(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    **ADR-0036 §28 row 16.**

    The other side of the compensation: it must not fire on success. A
    cleanup wired to run unconditionally would delete the document it
    had just stored, and the row would survive pointing at nothing -
    which is the failure mode §20 says the write-then-commit order
    exists to avoid.
    """

    document = _uploaded(api_client)

    record = db_session.get(DocumentRecord, document["id"])

    assert db_session.query(DocumentRecord).count() == 1
    assert _files(storage_root) == [Path(record.file_path)]
    assert Path(record.file_path).read_bytes() == PDF


# --- Two uploads are two documents (§12, §16) ---------------------------


def test_two_uploads_of_identical_bytes_are_two_documents_with_one_identity(
    api_client: TestClient, db_session: Session, storage_root: Path
) -> None:
    """
    §12 and §16 together: identity is not deduplication.

    Both rows record the same content identity, nothing is merged, and
    no conclusion is drawn from the match - whether a repeated upload is
    a duplicate, a re-issue under a new revision or the same drawing
    filed twice is a question about the documents, not their bytes.
    """

    first = _uploaded(api_client)
    second = _uploaded(api_client)

    assert first["id"] != second["id"]
    assert db_session.query(DocumentRecord).count() == 2
    assert len(_files(storage_root)) == 2

    assert (
        _detail(api_client, first["id"])["content_checksum"]
        == _detail(api_client, second["id"])["content_checksum"]
    )


def test_different_bytes_are_two_documents_with_two_identities(
    api_client: TestClient, storage_root: Path
) -> None:
    """The distinguishing half of the same rule (§28 row 2, end to end):
    a changed drawing must not be able to reuse the earlier one's
    artifacts."""

    first = _uploaded(api_client)
    second = _uploaded(api_client, content=OTHER_PDF)

    assert (
        _detail(api_client, first["id"])["content_checksum"]
        != _detail(api_client, second["id"])["content_checksum"]
    )


# --- The source of the published checksum (§22) -------------------------


def test_the_detail_checksum_comes_from_the_document_not_an_ingestion_job(
    api_client: TestClient, db_session: Session
) -> None:
    """
    **ADR-0036 §28 row 19.**

    The two values are made to disagree deliberately, because that is
    the only arrangement in which the source of the published answer is
    observable. Before this milestone the field was whichever ingestion
    attempt had the highest row id, with no filter on outcome - so a
    *failed* attempt was as authoritative as a successful one, and two
    reads of one unchanged document could differ.

    The job below is exactly that: the newest, and failed.
    """

    document_digest = hashlib.sha256(PDF).hexdigest()
    job_digest = hashlib.sha256(OTHER_PDF).hexdigest()

    document = DocumentRecord(
        filename="schema.pdf",
        file_path="documents/schema_ab12cd34.pdf",
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        scope=DocumentScope.CANONICAL_LIBRARY,
        project_name="Cabina Primaria Gamma",
        content_checksum=document_digest,
        content_checksum_algorithm="sha256",
        content_size_bytes=len(PDF),
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    db_session.add(
        DocumentIngestionJob(
            document_id=document.id,
            project_id=None,
            state=IngestionState.PROCESSED,
            outcome=IngestionOutcome.FAILED,
            pipeline_version="1.0",
            created_at=datetime(2026, 9, 18, 9, 0, 0),
            content_checksum=job_digest,
            content_checksum_algorithm="sha256",
            content_size_bytes=len(OTHER_PDF),
        )
    )
    db_session.commit()

    detail = _detail(api_client, document.id)

    assert detail["content_checksum"] == document_digest
    assert detail["size_bytes"] == len(PDF)


# --- The compensation window is the whole window (§20) ------------------
#
# The write happens before the row exists, and the commit is not the only
# thing between them: the bytes are classified and a ``Document`` is
# constructed first. A file orphaned by one of those is orphaned exactly
# as thoroughly as one orphaned by a failed commit, and nothing ever
# reconciles the storage tree - it is excluded from version control and
# no row points into it.
#
# Both failures below are induced by replacing a collaborator of the
# route, so the route itself runs unmodified and the compensation is
# observed rather than asserted from reading the source.


def _always_fails(*args, **kwargs):
    raise RuntimeError("the step after the write fell over")


def test_a_failure_while_classifying_the_bytes_discards_the_file(
    api_client: TestClient,
    db_session: Session,
    storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    **ADR-0036 §28 row 15**, on the half the commit-only compensation
    missed.

    Identity resolution reads the file that was just written and can
    raise for reasons that have nothing to do with the database. Before
    the window was widened this exit left the bytes on disk with no row
    referencing them and no error mentioning them.
    """

    monkeypatch.setattr(
        documents_router, "resolve_document_identity", _always_fails
    )

    with pytest.raises(RuntimeError):
        _upload(api_client)

    assert _files(storage_root) == []
    assert db_session.query(DocumentRecord).count() == 0


def test_a_failure_while_building_the_row_discards_the_file(
    api_client: TestClient,
    db_session: Session,
    storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The same window, one step later: the row is constructed from the
    classification before anything is added to the session, so a failure
    there also leaves a stored file no row will ever reference.

    Induced at ``_persisted_format`` because that is the step where the
    classifier's verdict becomes a column - the last thing that can
    raise before the transaction begins.
    """

    monkeypatch.setattr(
        documents_router, "_persisted_format", _always_fails
    )

    with pytest.raises(RuntimeError):
        _upload(api_client)

    assert _files(storage_root) == []
    assert db_session.query(DocumentRecord).count() == 0
