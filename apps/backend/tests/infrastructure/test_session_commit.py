"""
The transaction rule every self-committing adapter shares.

These adapters are handed the request's ``Session`` rather than owning
one, and each write is its own transaction. The rule under test is what
happens to that shared session when a write *fails*: before it existed,
a failed commit left the session unusable, and because the services
convert adapter failures into typed values rather than re-raising,
nothing above ever repaired it. The reported failure then became a
crash in whatever ran next.

Each case here drops the table an adapter writes to. That is a real
condition - code deployed ahead of its migration - and it produces a
genuine failure inside ``commit()`` rather than a simulated one.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, PendingRollbackError
from sqlalchemy.orm import Session

from app.database.session_commit import commit_or_restore
from app.models.canonical_pdf import CanonicalPdfRepresentation
from app.models.canonical_text import CanonicalTextDocumentRecord
from app.models.document import Document as DocumentRecord
from app.models.document_ingestion import DocumentIngestionJob
from app.models.identity import AuditEventRecord


def _canonical_text() -> CanonicalTextDocumentRecord:
    return CanonicalTextDocumentRecord(
        document_id=1,
        content_checksum="a" * 64,
        representation_version="1.0",
        segmentation_version="1.0",
        section_count=1,
        token_count=1,
    )


def _canonical_pdf() -> CanonicalPdfRepresentation:
    return CanonicalPdfRepresentation(
        document_id=1,
        artifact_identity="identity",
        upstream_identity="upstream",
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        representation_version="1.0",
        parser_name="pymupdf",
        parser_version="1.0",
        page_count=1,
    )


def _ingestion_job() -> DocumentIngestionJob:
    return DocumentIngestionJob(document_id=1, project_id=None)


def _audit_event() -> AuditEventRecord:
    """The audit adapter runs *after* the pipeline, on the same session
    - so it is the write most exposed to a session another write already
    broke, and the one whose failure would discard a reported result."""

    return AuditEventRecord(
        occurred_at=datetime(2026, 3, 1, 9, 0, 0),
        action="document_uploaded",
        outcome="succeeded",
        actor_authenticated=True,
        actor_description="engineer",
        resource_type="document",
    )


WRITES = [
    ("canonical_text_documents", _canonical_text),
    ("canonical_pdf_representations", _canonical_pdf),
    ("document_ingestion_jobs", _ingestion_job),
    ("audit_events", _audit_event),
]


@pytest.mark.parametrize("table, build", WRITES)
def test_a_failed_commit_leaves_the_session_usable(
    db_session: Session, table: str, build
) -> None:
    """
    The property the whole rule exists for.

    A failed write must cost the caller the write and nothing else. The
    session it shares with the rest of the request has to keep working,
    because the request is not over: a response still has to be built,
    and an audit record still has to be written.
    """

    db_session.execute(text(f"DROP TABLE {table}"))
    db_session.commit()
    db_session.add(build())

    with pytest.raises(OperationalError):
        commit_or_restore(db_session)

    # The assertion this test exists for. Before the rule, this raised
    # PendingRollbackError.
    assert db_session.query(DocumentRecord).count() == 0


@pytest.mark.parametrize("table, build", WRITES)
def test_a_valid_write_still_succeeds_after_a_failed_one(
    db_session: Session, table: str, build
) -> None:
    """A recovered session is not merely readable - it can still be
    written to, which is what the audit record after a failed pipeline
    stage actually needs."""

    db_session.execute(text(f"DROP TABLE {table}"))
    db_session.commit()
    db_session.add(build())

    with pytest.raises(OperationalError):
        commit_or_restore(db_session)

    db_session.add(
        DocumentRecord(
            filename="after.pdf",
            file_path="/tmp/after.pdf",
            project_name="Alpha Substation",
        )
    )
    commit_or_restore(db_session)

    assert db_session.query(DocumentRecord).count() == 1


def test_the_commit_failure_is_re_raised_unchanged(
    db_session: Session
) -> None:
    """
    Repairing the session is this rule's business. Deciding what the
    failure *means* is not - that belongs to the service above, which
    reports a typed storage failure - so the original exception is
    passed through rather than translated.
    """

    db_session.execute(text("DROP TABLE canonical_text_documents"))
    db_session.commit()
    db_session.add(_canonical_text())

    with pytest.raises(OperationalError) as raised:
        commit_or_restore(db_session)

    assert "canonical_text_documents" in str(raised.value)


def test_an_ordinary_commit_is_unaffected(db_session: Session) -> None:
    """The rule adds a repair path, not a behaviour change."""

    db_session.add(
        DocumentRecord(
            filename="ordinary.pdf",
            file_path="/tmp/ordinary.pdf",
            project_name="Alpha Substation",
        )
    )

    commit_or_restore(db_session)

    stored = db_session.query(DocumentRecord).one()
    assert stored.id is not None
    assert stored.filename == "ordinary.pdf"


def test_pending_rollback_is_what_this_prevents(
    db_session: Session
) -> None:
    """
    The defect itself, pinned.

    A bare ``commit()`` on the same failure leaves the session in
    exactly the state the rule above removes. If this ever stops
    raising, SQLAlchemy's behaviour has changed and the rule should be
    re-examined rather than silently kept.
    """

    db_session.execute(text("DROP TABLE canonical_text_documents"))
    db_session.commit()
    db_session.add(_canonical_text())

    with pytest.raises(OperationalError):
        db_session.commit()

    with pytest.raises(PendingRollbackError):
        db_session.query(DocumentRecord).count()


# --- The adapters, not just the rule ------------------------------------


def test_the_audit_adapter_restores_the_session_it_breaks(
    db_session: Session
) -> None:
    """
    The rule is only useful where it is actually called.

    Exercising ``commit_or_restore`` alone proves the rule works and
    proves nothing about the adapters: reverting the audit adapter to a
    bare ``commit()`` left every test above green. This drives the real
    adapter, so a regression at the call site is caught too.

    The audit adapter is the one that matters most on the upload path:
    it writes *after* the pipeline, on the same session, so it is both
    the write most exposed to a session an earlier write already broke
    and - if it breaks the session itself - the last thing standing
    between a reported result and a lost response.
    """

    from app.domain.audit.audit_models import (
        AuditAction,
        AuditActor,
        AuditEvent,
        AuditOutcome,
        AuditResource,
    )
    from app.infrastructure.audit.sqlalchemy_audit_repository import (
        SqlAlchemyAuditRepository,
    )

    event = AuditEvent(
        event_id=None,
        occurred_at=datetime(2026, 3, 1, 9, 0, 0),
        action=AuditAction.DOCUMENT_UPLOADED,
        outcome=AuditOutcome.SUCCEEDED,
        actor=AuditActor(
            authenticated=True,
            user_id=None,
            session_id=None,
            description="engineer",
        ),
        resource=AuditResource(resource_type="document", resource_id="1"),
    )

    db_session.execute(text("DROP TABLE audit_events"))
    db_session.commit()

    with pytest.raises(OperationalError):
        SqlAlchemyAuditRepository(db_session).record(event)

    # The session the request still needs.
    assert db_session.query(DocumentRecord).count() == 0
