"""
Service tests for spreadsheet evidence extraction (ADR-0034), against a
real (in-memory) database through the real SQLAlchemy adapters.

The canonical workbook is stored through its own repository and read back
through the port, so these prove the two layers meet correctly: a fake
source could agree with the domain and disagree with what the schema
actually persists.

They also carry this milestone's most consequential negative claim. A
cable register is read here end to end, and what it must produce is
observations about cells and **nothing else** - no entity, no graph node,
no graph edge, no index entry. That is asserted over counts in the real
tables rather than over intent.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.canonical_spreadsheet.canonical_workbook_repository import (
    CanonicalWorkbookRepository,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.spreadsheet_evidence.spreadsheet_evidence_exceptions import (
    SpreadsheetEvidenceFailureCode,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    SpreadsheetEvidenceSet,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_repository import (
    SpreadsheetEvidenceRepository,
)
from app.infrastructure.canonical_spreadsheet.openpyxl_workbook_reader import (
    OpenpyxlWorkbookReader,
)
from app.infrastructure.canonical_spreadsheet.sqlalchemy_canonical_workbook_repository import (  # noqa: E501
    SqlAlchemyCanonicalWorkbookRepository,
)
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_storage_location import (  # noqa: E501
    SqlAlchemyDocumentStorageLocation,
)
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.infrastructure.spreadsheet_evidence.sqlalchemy_spreadsheet_evidence_repository import (  # noqa: E501
    SqlAlchemySpreadsheetEvidenceRepository,
)
from app.models.canonical_spreadsheet import CanonicalWorkbookRecord
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_entities import EngineeringEntityRecord
from app.models.engineering_index import EngineeringIndexEntry
from app.models.governed_knowledge_graph import (
    GovernedGraphEdgeRecord,
    GovernedGraphNodeRecord,
)
from app.models.project import Project as ProjectRecord
from app.models.spreadsheet_evidence import SpreadsheetEvidenceSetRecord
from app.services import canonical_spreadsheet_service
from app.services import document_ingestion_service
from app.services import spreadsheet_evidence_service
from tests.fixtures import synthetic_workbooks

NOW = datetime(2026, 2, 1, 9, 0, 0)


def _project(db: Session) -> ProjectRecord:
    existing = (
        db.query(ProjectRecord)
        .filter(ProjectRecord.code == "ALPHA-001")
        .first()
    )

    if existing is not None:
        return existing

    project = ProjectRecord(
        name="Alpha Substation", code="ALPHA-001", customer="Acme Utilities"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project


def _document(
    db: Session, tmp_path: Path, content: bytes, *, filename: str
) -> DocumentRecord:
    path = tmp_path / filename
    path.write_bytes(content)
    project = _project(db)

    document = DocumentRecord(
        filename=filename,
        file_path=str(path),
        project_id=project.id,
        project_name=project.name,
        file_format=DocumentFormat.XLSX,
        category=DocumentCategory.CABLE_LIST,
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _canonicalised(
    db: Session,
    tmp_path: Path,
    content: bytes | None = None,
    *,
    filename: str = "equipment-register.xlsx",
) -> DocumentRecord:
    """A document taken through the governed predecessors: ingested, then
    read into a canonical workbook."""

    document = _document(
        db,
        tmp_path,
        content or synthetic_workbooks.multiple_sheets(),
        filename=filename,
    )
    document_ingestion_service.ingest_document(
        SqlAlchemyIngestionJobRepository(db),
        SqlAlchemyDocumentMetadataRepository(db),
        document_id=document.id,
        now=NOW,
        content_port=FilesystemDocumentContentAdapter(),
        storage_location_port=SqlAlchemyDocumentStorageLocation(db),
    )
    result = canonical_spreadsheet_service.canonicalize_workbook(
        OpenpyxlWorkbookReader(),
        SqlAlchemyCanonicalWorkbookRepository(db),
        FilesystemDocumentContentAdapter(),
        SqlAlchemyDocumentStorageLocation(db),
        SqlAlchemyDocumentMetadataRepository(db),
        SqlAlchemyIngestionJobRepository(db),
        document_id=document.id,
    )

    assert result.succeeded, result.failure

    return document


def _extract(
    db: Session, document_id: int, **kwargs: object
) -> spreadsheet_evidence_service.SpreadsheetEvidenceExtractionResult:
    return spreadsheet_evidence_service.extract_workbook_evidence(
        kwargs.pop(
            "workbook_repository",
            SqlAlchemyCanonicalWorkbookRepository(db),
        ),
        kwargs.pop(
            "evidence_repository",
            SqlAlchemySpreadsheetEvidenceRepository(db),
        ),
        document_id=document_id,
        **kwargs,
    )


# --- The happy path -------------------------------------------------------


def test_a_canonical_workbook_is_extracted_into_evidence(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)

    result = _extract(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.found_evidence is True
    assert [
        item.observed_text
        for item in result.evidence_set.of_type(EvidenceType.DESIGNATION)
    ] == ["QA1", "TR1"]


def test_the_set_records_the_workbook_and_the_policy_that_read_it(
    db_session: Session, tmp_path: Path
) -> None:
    """A set whose provenance is unknown cannot be trusted by anything
    downstream: which document, which bytes, which recording contract,
    which rules."""

    document = _canonicalised(db_session, tmp_path)

    evidence_set = _extract(
        db_session, document.id, project_id=9
    ).evidence_set
    workbook = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )

    assert evidence_set.document_id == document.id
    assert evidence_set.project_id == 9
    assert evidence_set.content_checksum == workbook.content_checksum
    assert evidence_set.representation_version == "1.0"
    assert evidence_set.extraction_policy_version == "1.0"
    assert evidence_set.upstream_identity == workbook.artifact_identity


def test_the_evidence_survives_a_round_trip_through_the_database(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)

    built = _extract(db_session, document.id).evidence_set
    stored = SqlAlchemySpreadsheetEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_cell_provenance_survives_persistence(
    db_session: Session, tmp_path: Path
) -> None:
    """An observation whose source cannot be located is an assertion, and
    this system does not store assertions - so the coordinates have to
    come back exactly as they went in."""

    document = _canonicalised(db_session, tmp_path)
    _extract(db_session, document.id)

    stored = spreadsheet_evidence_service.get_spreadsheet_evidence_set(
        SqlAlchemySpreadsheetEvidenceRepository(db_session), document.id
    )
    item = stored.of_type(EvidenceType.DESIGNATION)[0]

    assert item.provenance.worksheet_index == 1
    assert item.provenance.worksheet_name == "Equipment"
    assert item.provenance.a1_reference == "A2"
    assert item.provenance.character_start == 0
    assert item.provenance.character_end == 3
    assert item.provenance.source_text == "QA1"


def test_the_rule_that_matched_is_persisted_with_its_version(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)
    _extract(db_session, document.id)

    stored = spreadsheet_evidence_service.get_spreadsheet_evidence_set(
        SqlAlchemySpreadsheetEvidenceRepository(db_session), document.id
    )

    for item in stored.evidence:
        assert item.rule_id
        assert item.rule_version


def test_a_workbook_with_nothing_recognisable_is_a_success(
    db_session: Session, tmp_path: Path
) -> None:
    """Finding nothing is not a failure: a register may simply contain
    nothing these rules recognise, and a cable register is exactly such a
    register today."""

    document = _canonicalised(
        db_session, tmp_path, synthetic_workbooks.simple_register()
    )

    result = _extract(db_session, document.id)

    assert result.succeeded is True
    assert result.found_evidence is False
    assert result.evidence_set.is_empty


def test_a_document_never_extracted_has_no_evidence_set(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)

    assert (
        spreadsheet_evidence_service.get_spreadsheet_evidence_set(
            SqlAlchemySpreadsheetEvidenceRepository(db_session), document.id
        )
        is None
    )


def test_rejected_candidates_never_reach_storage(
    db_session: Session, tmp_path: Path
) -> None:
    """``REJECTED`` items are the extractor's diagnostics; stored, a later
    reader could mistake them for engineering evidence."""

    document = _canonicalised(db_session, tmp_path)
    _extract(db_session, document.id)

    stored = spreadsheet_evidence_service.get_spreadsheet_evidence_set(
        SqlAlchemySpreadsheetEvidenceRepository(db_session), document.id
    )

    assert stored.with_status(EvidenceStatus.REJECTED) == ()


# --- Idempotency ----------------------------------------------------------


def test_re_running_reuses_the_stored_set(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)

    first = _extract(db_session, document.id)
    second = _extract(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.evidence_set == first.evidence_set


def test_re_running_creates_no_second_row(
    db_session: Session, tmp_path: Path
) -> None:
    document = _canonicalised(db_session, tmp_path)

    _extract(db_session, document.id)
    _extract(db_session, document.id)
    _extract(db_session, document.id)

    assert (
        db_session.query(SpreadsheetEvidenceSetRecord)
        .filter(SpreadsheetEvidenceSetRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_new_policy_version_extracts_again(
    db_session: Session, tmp_path: Path
) -> None:
    """
    The rules changed, so the result is a different set even though the
    workbook is identical - which is why the policy version is part of
    the key.

    The version used here is deliberately far ahead of the real one: the
    point is that *any* change of policy re-extracts, and a literal that
    happened to equal the current default would assert nothing.
    """

    document = _canonicalised(db_session, tmp_path)
    _extract(db_session, document.id)

    result = _extract(
        db_session, document.id, extraction_policy_version="99.0"
    )

    assert result.reused is False
    assert (
        db_session.query(SpreadsheetEvidenceSetRecord)
        .filter(SpreadsheetEvidenceSetRecord.document_id == document.id)
        .count()
        == 2
    )


# --- Typed failures -------------------------------------------------------


def test_a_document_without_a_canonical_workbook_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Extraction is the step after the workbook was read; this context
    never opens a file itself."""

    document = _document(
        db_session,
        tmp_path,
        synthetic_workbooks.multiple_sheets(),
        filename="unread.xlsx",
    )

    result = _extract(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.CANONICAL_WORKBOOK_MISSING
    )


def test_an_unknown_document_is_refused_the_same_way(
    db_session: Session,
) -> None:
    result = _extract(db_session, 4321)

    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.CANONICAL_WORKBOOK_MISSING
    )


def test_an_unsupported_workbook_version_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """A newer recording may record a cell's text differently, and
    character offsets taken against the wrong recording would point at
    the wrong characters - which is worse than no evidence at all."""

    document = _canonicalised(db_session, tmp_path)
    stored = (
        db_session.query(CanonicalWorkbookRecord)
        .filter(CanonicalWorkbookRecord.document_id == document.id)
        .one()
    )
    stored.representation_version = "99.0"
    db_session.commit()

    result = _extract(db_session, document.id)

    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.UNSUPPORTED_WORKBOOK_VERSION
    )
    assert "99.0" in result.failure.message


def test_a_workbook_without_a_derivation_identity_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Unknown provenance is not compatible provenance: evidence read
    from it could never prove its own reuse is valid."""

    document = _canonicalised(db_session, tmp_path)
    stored = (
        db_session.query(CanonicalWorkbookRecord)
        .filter(CanonicalWorkbookRecord.document_id == document.id)
        .one()
    )
    stored.artifact_identity = None
    db_session.commit()

    result = _extract(db_session, document.id)

    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY
    )


def test_a_workbook_describing_another_document_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Continuing would attach observations to the wrong document."""

    document = _canonicalised(db_session, tmp_path)
    workbook = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )

    class MisdirectedRepository(CanonicalWorkbookRepository):
        def save(self, representation) -> None:
            raise AssertionError("extraction must not store a workbook")

        def find_by_identity(self, document_id, artifact_identity):
            return None

        def find_latest_for_document(self, document_id):
            return replace(workbook, document_id=workbook.document_id + 1)

    result = _extract(
        db_session,
        document.id,
        workbook_repository=MisdirectedRepository(),
    )

    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY
    )


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session, tmp_path: Path
) -> None:
    class FailingRepository(SpreadsheetEvidenceRepository):
        def save(self, evidence_set: SpreadsheetEvidenceSet) -> None:
            raise RuntimeError("the disk is full")

        def find_by_identity(
            self, document_id: int, artifact_identity: str
        ) -> SpreadsheetEvidenceSet | None:
            return None

        def find_latest_for_document(
            self, document_id: int
        ) -> SpreadsheetEvidenceSet | None:
            return None

    document = _canonicalised(db_session, tmp_path)

    result = _extract(
        db_session, document.id, evidence_repository=FailingRepository()
    )

    assert result.failure.code is (
        SpreadsheetEvidenceFailureCode.EVIDENCE_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    result = _extract(db_session, 4321)

    assert result.failure.message
    assert result.evidence_set is None


# --- The chain stops at evidence ------------------------------------------


def test_reading_a_cable_register_creates_no_entity_and_no_graph(
    db_session: Session, tmp_path: Path
) -> None:
    """
    The register that most invites a conclusion, read end to end.

    Its rows say ``CBL-001`` runs from ``PANEL-A`` to ``PANEL-B``, and
    this milestone must record none of that: no entity, no graph node, no
    graph edge, no index entry. Counted in the real tables, because
    "nothing was written" is a claim about the database, not about the
    code's intentions.
    """

    document = _canonicalised(
        db_session,
        tmp_path,
        synthetic_workbooks.simple_register(),
        filename="cable-register.xlsx",
    )

    result = _extract(db_session, document.id)

    assert result.succeeded
    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0
    assert db_session.query(EngineeringEntityRecord).count() == 0


def test_a_register_that_does_yield_observations_still_creates_no_entity(
    db_session: Session, tmp_path: Path
) -> None:
    """The stronger half of the same claim: the workbook that *does*
    produce evidence produces evidence and nothing else, so the emptiness
    above is not merely the emptiness of an extraction that found
    nothing."""

    document = _canonicalised(db_session, tmp_path)

    result = _extract(db_session, document.id)

    assert result.evidence_set.evidence_count == 2
    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0
    assert db_session.query(EngineeringEntityRecord).count() == 0


def test_extraction_reads_only_the_canonical_workbook(
    db_session: Session, tmp_path: Path
) -> None:
    """The strongest available proof that the original file is never
    reopened: the document's ``file_path`` points at a file that never
    existed, and extraction succeeds regardless."""

    document = _canonicalised(db_session, tmp_path)
    document.file_path = "/nowhere/never_written.xlsx"
    db_session.commit()

    result = _extract(db_session, document.id)

    assert result.succeeded
    assert result.evidence_set.evidence_count == 2
