"""
The three identity columns on ``documents``, against a real (in-memory)
database (ADR-0036 §18, §19).

What is proven here is not that a value can be written - the upload
tests cover that - but that it **stays**. A document's recorded content
identity is written once, at creation, and every later operation on that
row leaves it exactly as it was. That includes the case §19 calls the
one most likely to be waved through as harmless: filling in a ``NULL``.

``NULL`` here means *honestly unknown*, never "empty" and never "zero",
and two of them are never the same unknown - which is why the lookup
that pairs documents by checksum must never pair two unidentified rows.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session, aliased

from app.domain.document_ingestion.ingestion_models import (
    IngestionOutcome,
    IngestionState,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.document_registry.sqlalchemy_document_registry import (  # noqa: E501
    SqlAlchemyDocumentRegistryRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.document_ingestion import DocumentIngestionJob

PDF = b"%PDF-1.7 Schema unifilare - sezione MT"
DOCUMENT_DIGEST = hashlib.sha256(PDF).hexdigest()
JOB_DIGEST = hashlib.sha256(b"a later read of different bytes").hexdigest()


def _document(
    db_session: Session,
    *,
    filename: str = "schema.pdf",
    content_checksum: str | None = DOCUMENT_DIGEST,
    content_checksum_algorithm: str | None = "sha256",
    content_size_bytes: int | None = len(PDF),
) -> DocumentRecord:
    document = DocumentRecord(
        filename=filename,
        file_path=f"documents/{filename}",
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        scope=DocumentScope.CANONICAL_LIBRARY,
        project_name="Cabina Primaria Gamma",
        content_checksum=content_checksum,
        content_checksum_algorithm=content_checksum_algorithm,
        content_size_bytes=content_size_bytes,
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return document


def _ingestion_job(
    db_session: Session,
    document: DocumentRecord,
    *,
    checksum: str | None,
    outcome: IngestionOutcome | None = IngestionOutcome.READY_FOR_EXTRACTION,
) -> DocumentIngestionJob:
    job = DocumentIngestionJob(
        document_id=document.id,
        project_id=document.project_id,
        state=IngestionState.PROCESSED,
        outcome=outcome,
        pipeline_version="1.0",
        created_at=datetime(2026, 9, 18, 9, 0, 0),
        content_checksum=checksum,
        content_checksum_algorithm=None if checksum is None else "sha256",
        content_size_bytes=None if checksum is None else 1,
    )

    db_session.add(job)
    db_session.commit()

    return job


def _identity_of(document: DocumentRecord) -> tuple:
    return (
        document.content_checksum,
        document.content_checksum_algorithm,
        document.content_size_bytes,
    )


# --- Written once, never updated (§18) ----------------------------------


def test_a_recorded_identity_survives_later_edits_to_the_same_row(
    db_session: Session,
) -> None:
    """
    ADR-0036 §28 row 8.

    ``category``, ``revision``, ``project_name`` and ``scope`` are
    editable registry metadata; the identity is not. Without this, a
    routine re-filing re-identifies the document and retroactively
    re-attributes every artifact keyed to the old value.
    """

    document = _document(db_session)
    recorded = _identity_of(document)

    document.category = DocumentCategory.RELAY_SETTINGS
    document.revision = "02"
    document.project_name = "Cabina Primaria Delta"
    db_session.commit()
    db_session.refresh(document)

    assert _identity_of(document) == recorded


def test_a_recorded_identity_survives_a_later_ingestion_job(
    db_session: Session,
) -> None:
    """
    ADR-0036 §28 row 10.

    "What this document is" and "what one attempt saw" are two
    questions. A re-ingestion that reads different bytes records that on
    its own job; if it moved the document's value instead, the only
    evidence that the bytes changed would be destroyed by the very read
    that discovered it.
    """

    document = _document(db_session)
    recorded = _identity_of(document)

    _ingestion_job(db_session, document, checksum=JOB_DIGEST)
    db_session.refresh(document)

    assert _identity_of(document) == recorded
    assert document.content_checksum != JOB_DIGEST


def test_an_unidentified_document_is_not_filled_in_by_an_ingestion_job(
    db_session: Session,
) -> None:
    """
    ADR-0036 §28 rows 8 and 10, on the case §19 singles out.

    A ``NULL`` -> value write is the one that looks harmless: nothing is
    overwritten, a gap is merely closed. It is the same forbidden
    ``UPDATE``, because the value it writes is a claim about bytes the
    document row never observed.
    """

    document = _document(
        db_session,
        content_checksum=None,
        content_checksum_algorithm=None,
        content_size_bytes=None,
    )

    _ingestion_job(db_session, document, checksum=JOB_DIGEST)
    db_session.refresh(document)

    assert _identity_of(document) == (None, None, None)


def test_re_ingestion_accumulates_jobs_and_moves_nothing(
    db_session: Session,
) -> None:
    """
    §15: the accumulated jobs are the document's audit trail, and each
    keeps its own checksum. Two attempts that disagree stay two
    disagreeing attempts rather than collapsing into one mutable value.
    """

    document = _document(db_session)
    recorded = _identity_of(document)

    _ingestion_job(db_session, document, checksum=DOCUMENT_DIGEST)
    _ingestion_job(
        db_session,
        document,
        checksum=JOB_DIGEST,
        outcome=IngestionOutcome.FAILED,
    )
    db_session.refresh(document)

    jobs = (
        db_session.query(DocumentIngestionJob)
        .filter(DocumentIngestionJob.document_id == document.id)
        .all()
    )

    assert len(jobs) == 2
    assert _identity_of(document) == recorded


# --- A NULL identity matches nothing (§19) ------------------------------


def test_documents_with_no_identity_are_never_paired_by_checksum(
    db_session: Session,
) -> None:
    """
    ADR-0036 §28 row 11.

    The non-unique index exists for one read: *which documents recorded
    these exact bytes?* Two unidentified rows are two different unknowns,
    so that read must never put them together - the failure
    ``test_unknown_legacy_identity_is_never_current_compatible`` already
    names for the artifact chain.
    """

    identified = _document(db_session, filename="one.pdf")
    also_identified = _document(db_session, filename="two.pdf")
    legacy = _document(
        db_session,
        filename="legacy.pdf",
        content_checksum=None,
        content_checksum_algorithm=None,
        content_size_bytes=None,
    )
    _document(
        db_session,
        filename="another-legacy.pdf",
        content_checksum=None,
        content_checksum_algorithm=None,
        content_size_bytes=None,
    )

    other = aliased(DocumentRecord)

    pairs = (
        db_session.query(DocumentRecord.id, other.id)
        .join(
            other,
            DocumentRecord.content_checksum == other.content_checksum,
        )
        .filter(DocumentRecord.id < other.id)
        .all()
    )

    assert pairs == [(identified.id, also_identified.id)]
    assert legacy.content_checksum is None


def test_a_lookup_by_a_real_digest_never_returns_an_unidentified_document(
    db_session: Session,
) -> None:
    """The other direction of the same rule: an unknown identity is not
    a wildcard either."""

    identified = _document(db_session, filename="one.pdf")
    _document(
        db_session,
        filename="legacy.pdf",
        content_checksum=None,
        content_checksum_algorithm=None,
        content_size_bytes=None,
    )

    found = (
        db_session.query(DocumentRecord)
        .filter(DocumentRecord.content_checksum == DOCUMENT_DIGEST)
        .all()
    )

    assert [document.id for document in found] == [identified.id]


# --- The registry reads the document, not the job (§22) -----------------


def test_the_detail_reports_the_documents_identity_not_the_jobs(
    db_session: Session,
) -> None:
    """
    ADR-0036 §28 row 19.

    The two values are made to disagree on purpose, because that is the
    only arrangement in which the source of the answer is observable. If
    this reverts, the field silently keeps its old, job-derived meaning
    - whichever attempt has the highest row id, succeeded or not - while
    the column sits unused.
    """

    document = _document(db_session)
    _ingestion_job(db_session, document, checksum=JOB_DIGEST)

    detail = SqlAlchemyDocumentRegistryRepository(db_session).find_detail(
        document.id
    )

    assert detail.content_checksum == DOCUMENT_DIGEST
    assert detail.checksum_algorithm == "sha256"
    assert detail.size_bytes == len(PDF)


def test_the_detail_still_reports_the_ingestion_state_from_the_job(
    db_session: Session,
) -> None:
    """The job is still the source of ingestion state. ADR-0036 moved
    one answer, not the whole read - and a fix that detached the job
    entirely would leave the detail unable to say what has happened to
    the document."""

    document = _document(db_session)
    _ingestion_job(db_session, document, checksum=JOB_DIGEST)

    detail = SqlAlchemyDocumentRegistryRepository(db_session).find_detail(
        document.id
    )

    assert detail.ingestion_state == IngestionState.PROCESSED.value
    assert detail.ingestion_outcome == (
        IngestionOutcome.READY_FOR_EXTRACTION.value
    )


def test_an_unidentified_document_reports_no_checksum_even_with_a_job(
    db_session: Session,
) -> None:
    """
    §19's cost, made visible.

    A legacy row stays unidentified for the life of that row. A read
    that quietly borrowed an ingestion job's checksum to fill the gap
    would be the backfill §19 refuses, performed once per request.
    """

    document = _document(
        db_session,
        content_checksum=None,
        content_checksum_algorithm=None,
        content_size_bytes=None,
    )
    _ingestion_job(db_session, document, checksum=JOB_DIGEST)

    detail = SqlAlchemyDocumentRegistryRepository(db_session).find_detail(
        document.id
    )

    assert detail.content_checksum is None
    assert detail.checksum_algorithm is None
    assert detail.size_bytes is None
