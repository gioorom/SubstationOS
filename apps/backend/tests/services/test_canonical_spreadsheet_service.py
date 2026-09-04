"""
Service tests for the Canonical Spreadsheet Representation (ADR-0034).

The whole governed flow, against a real (in-memory) database, the real
SQLAlchemy adapters, the real openpyxl reader and real files in
``tmp_path``. A fake repository could agree with the domain and disagree
with the schema; a fake reader could agree with both and disagree with
workbooks.

The mirror of ``test_canonical_pdf_service``, deliberately: the two
lineages fork at the bytes, so the spreadsheet family has to prove the
same properties for itself rather than inheriting them.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
    WorkbookCanonicalizationFailureCode,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_exceptions import (  # noqa: E501
    InvalidCanonicalWorkbookError,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCellType,
    CanonicalWorkbook,
    WorkbookDateSystem,
    WorksheetVisibility,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_policy import (  # noqa: E501
    MAX_COMPRESSED_BYTES,
)
from app.domain.canonical_spreadsheet.canonical_workbook_repository import (
    CanonicalWorkbookRepository,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.project.project_document_scope import DocumentScope
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
from app.models.canonical_spreadsheet import (
    CanonicalCellRecord,
    CanonicalRowRecord,
    CanonicalWorkbookRecord,
    CanonicalWorksheetRecord,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_entities import EngineeringEntityRecord
from app.models.engineering_index import EngineeringIndexEntry
from app.models.governed_knowledge_graph import (
    GovernedGraphEdgeRecord,
    GovernedGraphNodeRecord,
)
from app.models.project import Project as ProjectRecord
from app.services import canonical_spreadsheet_service
from app.services import document_ingestion_service
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
    db: Session,
    tmp_path: Path,
    *,
    content: bytes | None = None,
    filename: str = "cable-register.xlsx",
    file_format: DocumentFormat = DocumentFormat.XLSX,
) -> DocumentRecord:
    """Writes real bytes and registers a document pointing at them."""

    path = tmp_path / filename

    if content is not None:
        path.write_bytes(content)

    project = _project(db)

    document = DocumentRecord(
        filename=filename,
        file_path=str(path),
        project_id=project.id,
        project_name=project.name,
        file_format=file_format,
        category=DocumentCategory.CABLE_LIST,
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _ingest(db: Session, document_id: int) -> None:
    """The governed predecessor: reading starts at
    READY_FOR_EXTRACTION."""

    document_ingestion_service.ingest_document(
        SqlAlchemyIngestionJobRepository(db),
        SqlAlchemyDocumentMetadataRepository(db),
        document_id=document_id,
        now=NOW,
        content_port=FilesystemDocumentContentAdapter(),
        storage_location_port=SqlAlchemyDocumentStorageLocation(db),
    )


def _canonicalize(
    db: Session,
    document_id: int,
    *,
    repository: CanonicalWorkbookRepository | None = None,
) -> canonical_spreadsheet_service.WorkbookCanonicalizationResult:
    return canonical_spreadsheet_service.canonicalize_workbook(
        OpenpyxlWorkbookReader(),
        repository or SqlAlchemyCanonicalWorkbookRepository(db),
        FilesystemDocumentContentAdapter(),
        SqlAlchemyDocumentStorageLocation(db),
        SqlAlchemyDocumentMetadataRepository(db),
        SqlAlchemyIngestionJobRepository(db),
        document_id=document_id,
    )


def _ready_document(
    db: Session, tmp_path: Path, content: bytes | None = None, **kwargs
) -> DocumentRecord:
    document = _document(
        db,
        tmp_path,
        content=content or synthetic_workbooks.simple_register(),
        **kwargs,
    )
    _ingest(db, document.id)

    return document


# --- The happy path -------------------------------------------------------


def test_a_ready_workbook_is_canonicalised(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)

    result = _canonicalize(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.representation.worksheet_count == 1
    assert result.representation.worksheets[0].name == "Register"


def test_the_representation_is_bound_to_the_bytes_it_came_from(
    db_session: Session, tmp_path: Path
) -> None:
    """The checksum ingestion established, carried onto the
    representation - which is what makes it explainable years later."""

    document = _ready_document(db_session, tmp_path)

    representation = _canonicalize(db_session, document.id).representation
    job = SqlAlchemyIngestionJobRepository(db_session).list_by_document(
        document.id
    )[0]

    assert representation.content_checksum == job.document.content.checksum
    assert representation.checksum_algorithm == "sha256"


def test_the_representation_records_its_derivation_identity(
    db_session: Session, tmp_path: Path
) -> None:
    """An artifact that cannot say what it was derived from can never
    prove a reuse is valid."""

    document = _ready_document(db_session, tmp_path)

    representation = _canonicalize(db_session, document.id).representation

    assert representation.artifact_identity
    assert representation.upstream_identity
    assert (
        representation.artifact_identity
        != representation.upstream_identity
    )


def test_every_worksheet_survives_the_round_trip(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.multiple_sheets()
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )

    assert tuple(sheet.name for sheet in stored.worksheets) == (
        "Cables",
        "Equipment",
        "Superseded",
    )


def test_the_stored_representation_equals_the_one_that_was_built(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.mixed_value_types()
    )

    built = _canonicalize(db_session, document.id).representation
    stored = SqlAlchemyCanonicalWorkbookRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_a_hidden_worksheet_survives_persistence_with_its_visibility(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.multiple_sheets()
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )

    assert stored.worksheet(2).visibility is WorksheetVisibility.HIDDEN
    assert stored.worksheet(2).rows[0].cells[0].literal.text == "CBL-099"


def test_a_gap_in_the_grid_survives_persistence(
    db_session: Session, tmp_path: Path
) -> None:
    """The workbook's own numbers are stored, so a gap is still a gap
    after a round trip through the schema."""

    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.sparse_and_blank()
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )
    worksheet = stored.worksheets[0]

    assert tuple(row.row_number for row in worksheet.rows) == (1, 3, 4, 6)
    assert tuple(
        cell.column_number for cell in worksheet.row(3).cells
    ) == (1, 3)


def test_a_formula_without_a_cached_result_survives_as_exactly_that(
    db_session: Session, tmp_path: Path
) -> None:
    """Stored as "no application has ever computed a value here" - never
    as a blank cell, an empty string or a zero."""

    document = _ready_document(
        db_session,
        tmp_path,
        synthetic_workbooks.formula_without_cached_result(),
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )
    computed = stored.worksheets[0].row(2).cells[2]

    assert computed.formula.expression == "=A2*B2"
    assert computed.formula.cached_result is None
    assert computed.literal is None


def test_verbatim_text_survives_persistence(
    db_session: Session, tmp_path: Path
) -> None:
    """A trailing space and a non-breaking space are what the register
    says; a round trip that normalised either would silently rewrite the
    document."""

    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.mixed_value_types()
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )
    worksheet = stored.worksheets[0]

    assert worksheet.row(7).cells[0].literal.text == "QMT01 "
    assert worksheet.row(8).cells[0].literal.text == "PANEL\u00a0A"
    assert worksheet.row(9).cells[0].literal.text == "first\nsecond"


def test_decimal_values_survive_persistence_exactly(
    db_session: Session, tmp_path: Path
) -> None:
    """``Numeric``, never ``Float``: a cable section that read back as
    2.4999999999999996 would be a defect nobody could explain."""

    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.mixed_value_types()
    )

    _canonicalize(db_session, document.id)
    stored = canonical_spreadsheet_service.get_workbook(
        SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
    )
    number = stored.worksheets[0].row(3).cells[0].literal.number

    assert number == Decimal("2.5")
    assert isinstance(number, Decimal)


def test_a_document_never_read_has_no_representation(
    db_session: Session, tmp_path: Path
) -> None:
    """Not an error: most documents have not been read, and inventing an
    empty representation would be indistinguishable from a register that
    genuinely says nothing."""

    document = _ready_document(db_session, tmp_path)

    assert (
        canonical_spreadsheet_service.get_workbook(
            SqlAlchemyCanonicalWorkbookRepository(db_session), document.id
        )
        is None
    )


# --- Idempotency ----------------------------------------------------------


def test_re_running_reuses_the_stored_representation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)

    first = _canonicalize(db_session, document.id)
    second = _canonicalize(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.representation == first.representation


def test_re_running_creates_no_second_row(
    db_session: Session, tmp_path: Path
) -> None:
    """The same bytes under the same contract already have a
    representation; a second row saying the same thing is what makes a
    re-run unsafe."""

    document = _ready_document(db_session, tmp_path)

    _canonicalize(db_session, document.id)
    _canonicalize(db_session, document.id)
    _canonicalize(db_session, document.id)

    assert (
        db_session.query(CanonicalWorkbookRecord)
        .filter(CanonicalWorkbookRecord.document_id == document.id)
        .count()
        == 1
    )


def test_changed_bytes_produce_a_second_representation(
    db_session: Session, tmp_path: Path
) -> None:
    """A new checksum makes the new representation a different value
    rather than an overwrite, so a conclusion drawn last year stays
    explainable."""

    document = _ready_document(db_session, tmp_path)
    first = _canonicalize(db_session, document.id).representation

    Path(document.file_path).write_bytes(
        synthetic_workbooks.multiple_sheets()
    )
    _ingest(db_session, document.id)
    second = _canonicalize(db_session, document.id)

    assert second.reused is False
    assert (
        second.representation.content_checksum != first.content_checksum
    )
    assert (
        db_session.query(CanonicalWorkbookRecord)
        .filter(CanonicalWorkbookRecord.document_id == document.id)
        .count()
        == 2
    )


def test_the_historical_representation_remains_readable(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)
    first = _canonicalize(db_session, document.id).representation

    Path(document.file_path).write_bytes(
        synthetic_workbooks.multiple_sheets()
    )
    _ingest(db_session, document.id)
    _canonicalize(db_session, document.id)

    historical = SqlAlchemyCanonicalWorkbookRepository(
        db_session
    ).find_by_identity(document.id, first.artifact_identity)

    assert historical == first


# --- Typed failures -------------------------------------------------------


def test_an_unknown_document_is_refused(db_session: Session) -> None:
    result = _canonicalize(db_session, 4321)

    assert result.succeeded is False
    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.DOCUMENT_NOT_FOUND
    )


def test_a_format_that_is_not_a_workbook_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """A legacy BIFF ``.xls``, an ``.xlsb``, a CSV and an ODS are four
    different problems, not four dialects of this one."""

    document = _document(
        db_session,
        tmp_path,
        content=synthetic_workbooks.simple_register(),
        filename="schema.pdf",
        file_format=DocumentFormat.PDF,
    )
    _ingest(db_session, document.id)

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.UNSUPPORTED_FORMAT
    )
    assert result.representation is None


def test_a_document_no_ingestion_job_accepted_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Reading is the step after ingestion. Reading without it would be a
    second, quieter path to the same artefact."""

    document = _document(
        db_session,
        tmp_path,
        content=synthetic_workbooks.simple_register(),
    )

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.NOT_READY_FOR_EXTRACTION
    )


def test_an_encrypted_workbook_is_refused_as_locked(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.encrypted_workbook()
    )

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.ENCRYPTED_WORKBOOK
    )


def test_a_corrupted_package_is_refused_as_malformed(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.corrupted_package()
    )

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.MALFORMED_PACKAGE
    )


def test_a_workbook_with_no_populated_cell_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Persisting it would give every future consumer a register that
    appears to say nothing."""

    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.empty_workbook()
    )

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode.NO_POPULATED_CELL
    )
    assert (
        db_session.query(CanonicalWorkbookRecord)
        .filter(CanonicalWorkbookRecord.document_id == document.id)
        .count()
        == 0
    )


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session, tmp_path: Path
) -> None:
    class FailingRepository(CanonicalWorkbookRepository):
        def save(self, representation: CanonicalWorkbook) -> None:
            raise RuntimeError("the disk is full")

        def find_by_identity(
            self, document_id: int, artifact_identity: str
        ) -> CanonicalWorkbook | None:
            return None

        def find_latest_for_document(
            self, document_id: int
        ) -> CanonicalWorkbook | None:
            return None

    document = _ready_document(db_session, tmp_path)

    result = _canonicalize(
        db_session, document.id, repository=FailingRepository()
    )

    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode
        .REPRESENTATION_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    result = _canonicalize(db_session, 4321)

    assert result.failure.message
    assert result.representation is None


# --- The chain stops at the representation --------------------------------


def test_canonicalisation_writes_no_graph_no_index_and_no_entity(
    db_session: Session, tmp_path: Path
) -> None:
    """This stage transcribes a workbook. The tables a later milestone
    will populate stay empty, and the assertion is over counts rather
    than intent."""

    document = _ready_document(
        db_session, tmp_path, synthetic_workbooks.simple_register()
    )

    assert _canonicalize(db_session, document.id).succeeded
    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0
    assert db_session.query(EngineeringEntityRecord).count() == 0


# --- The session a failed write leaves behind ----------------------------


class _ReuseBlindRepository(SqlAlchemyCanonicalWorkbookRepository):
    """
    The real adapter with reuse defeated.

    Subclassed rather than mocked because the behaviour under test is
    the *real* adapter's: what a genuine constraint violation does to
    the session it was handed. Only the reuse short-circuit is removed,
    so a second run reaches the write instead of returning the stored
    representation.
    """

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> CanonicalWorkbook | None:
        return None


def test_a_failed_save_leaves_the_caller_s_session_usable(
    db_session: Session, tmp_path: Path
) -> None:
    """
    A refused write is reported, and costs the caller nothing else.

    The adapter commits the session it was given, and this service
    converts a failed commit into a typed result rather than re-raising.
    Nothing above it would therefore ever roll back - so unless the
    adapter repairs what it broke, the *next* unrelated query on that
    session raises ``PendingRollbackError``.

    In the upload endpoint it lands sooner than one might guess: the
    ingestion stage has already committed, so the ``Document`` instance
    is expired, and merely reading ``document.id`` to report the
    failure issues a SELECT on the poisoned session. The registry read
    and the audit write that follow would fail for the same reason.

    Either way a pipeline failure becomes a failed upload for a
    document already stored and committed - the one thing that endpoint
    promises never to do.
    """

    document = _ready_document(db_session, tmp_path)
    repository = _ReuseBlindRepository(db_session)

    first = _canonicalize(db_session, document.id, repository=repository)
    assert first.succeeded

    result = _canonicalize(db_session, document.id, repository=repository)

    assert result.succeeded is False
    assert result.failure.code is (
        WorkbookCanonicalizationFailureCode
        .REPRESENTATION_PERSISTENCE_FAILURE
    )

    # The assertion this test exists for. The count is incidental; that
    # the query runs at all is the point.
    assert db_session.query(CanonicalWorkbookRecord).count() == 1


# --- A stored row that should never have existed -------------------------


@pytest.mark.parametrize("magnitude", ["Infinity", "-Infinity", "NaN"])
def test_a_stored_non_finite_number_is_refused_by_name(
    db_session: Session, magnitude: str
) -> None:
    """
    A row written outside the governed path is refused on the way out,
    and refused *legibly*.

    Nothing this system writes can produce one - the factory rejects a
    non-finite value at construction. But the adapter used to reach
    ``Decimal.quantize`` before the factory saw the row, so such a row
    surfaced as a bare ``InvalidOperation`` from the decimal library:
    an error naming no document, no cell and no rule.
    """

    record = CanonicalWorkbookRecord(
        artifact_identity="legacy",
        upstream_identity="upstream",
        document_id=1,
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        representation_version="1.0",
        reader_name="openpyxl",
        reader_version="3.1.5",
        date_system=WorkbookDateSystem.EPOCH_1900,
        has_vba_project=False,
        has_external_links=False,
        worksheet_count=1,
    )
    worksheet = CanonicalWorksheetRecord(
        worksheet_index=0,
        name="Ratings",
        visibility=WorksheetVisibility.VISIBLE,
        used_first_row=1,
        used_last_row=1,
        used_first_column=1,
        used_last_column=1,
    )
    row = CanonicalRowRecord(row_number=1)
    row.cells.append(
        CanonicalCellRecord(
            column_number=1,
            literal_type=CanonicalCellType.NUMBER,
            literal_text=magnitude,
            literal_number=Decimal(magnitude),
        )
    )
    worksheet.rows.append(row)
    record.worksheets.append(worksheet)
    db_session.add(record)
    db_session.commit()

    with pytest.raises(InvalidCanonicalWorkbookError):
        SqlAlchemyCanonicalWorkbookRepository(db_session).find_by_identity(
            1, "legacy"
        )


# --- The bound has to act before the memory is spent ---------------------


class _EndlessContent(DocumentContentPort):
    """
    A stored document that never ends.

    Not a contrived shape: a port cannot know how much there is until it
    has read it, which is exactly why the caller must stop rather than
    ask. It counts what was pulled, because the property under test is
    *how much was read*, not what was returned.
    """

    def __init__(self) -> None:
        self.chunks_yielded = 0

    def describe(self, storage_reference: str):
        raise NotImplementedError

    def read_prefix(self, storage_reference: str, length: int) -> bytes:
        raise NotImplementedError

    def iter_chunks(self, storage_reference: str, chunk_size: int):
        while True:
            self.chunks_yielded += 1
            yield bytes(chunk_size)


def test_reading_stops_at_the_bound_not_at_the_end_of_the_document() -> None:
    """
    The bound must cost what it saves.

    Loading the whole document and *then* measuring it makes the limit a
    report rather than a protection: the memory is already spent by the
    time the number is known. This proves the read stops within one
    chunk of the bound against content that would otherwise never end.
    """

    port = _EndlessContent()

    load = canonical_spreadsheet_service._read_bounded(port, "anywhere")

    assert load.exceeded_bound is True
    assert load.content is None

    chunk_size = canonical_spreadsheet_service._READ_CHUNK_SIZE
    assert port.chunks_yielded <= MAX_COMPRESSED_BYTES // chunk_size + 1
    assert port.chunks_yielded * chunk_size <= (
        MAX_COMPRESSED_BYTES + chunk_size
    )


def test_a_document_within_the_bound_is_read_whole() -> None:
    """The control: the bound refuses excess, not ordinary documents."""

    class _SmallContent(_EndlessContent):
        def iter_chunks(self, storage_reference: str, chunk_size: int):
            self.chunks_yielded += 1
            yield b"workbook bytes"

    load = canonical_spreadsheet_service._read_bounded(
        _SmallContent(), "anywhere"
    )

    assert load.exceeded_bound is False
    assert load.content == b"workbook bytes"


def _stored_number(db: Session, magnitude: str, identity: str) -> None:
    """A workbook row carrying exactly one numeric cell."""

    record = CanonicalWorkbookRecord(
        artifact_identity=identity,
        upstream_identity="upstream",
        document_id=1,
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        representation_version="1.0",
        reader_name="openpyxl",
        reader_version="3.1.5",
        date_system=WorkbookDateSystem.EPOCH_1900,
        has_vba_project=False,
        has_external_links=False,
        worksheet_count=1,
    )
    worksheet = CanonicalWorksheetRecord(
        worksheet_index=0,
        name="Ratings",
        visibility=WorksheetVisibility.VISIBLE,
        used_first_row=1,
        used_last_row=1,
        used_first_column=1,
        used_last_column=1,
    )
    row = CanonicalRowRecord(row_number=1)
    row.cells.append(
        CanonicalCellRecord(
            column_number=1,
            literal_type=CanonicalCellType.NUMBER,
            literal_text=magnitude,
            literal_number=Decimal(magnitude),
        )
    )
    worksheet.rows.append(row)
    record.worksheets.append(worksheet)
    db.add(record)
    db.commit()


@pytest.mark.parametrize(
    "magnitude",
    ["1E+12", "-1E+12", "630000", "2.5", "0", "0.000000000001", "9" * 15],
)
def test_a_number_within_the_columns_scale_reads_back_unchanged(
    db_session: Session, magnitude: str
) -> None:
    """
    Being large is not being invalid.

    Restoring an integral value to plain notation is a *presentation*
    step, and it is only defined while the plain form fits the
    arithmetic context. Applied unconditionally it raised
    ``InvalidOperation`` on magnitudes a register may legitimately
    carry - so a number that stored perfectly well could never be read
    back, which is the same broken invariant as a non-finite value
    reached by a different route.
    """

    _stored_number(db_session, magnitude, f"finite-{magnitude}")

    workbook = SqlAlchemyCanonicalWorkbookRepository(
        db_session
    ).find_by_identity(1, f"finite-{magnitude}")
    number = workbook.worksheets[0].rows[0].cells[0].literal.number

    # Equality, not merely "a finite number came back". The weaker
    # assertion passed while the value was silently altered by the
    # store, which is the failure this is here to catch.
    assert number == Decimal(magnitude)


@pytest.mark.parametrize(
    "written, recorded",
    [
        # Pi as a spreadsheet holds it: seventeen significant digits,
        # rounded to the column's twelve decimal places.
        ("3.141592653589793", "3.14159265359"),
        # Smaller than the column's smallest step, so it records as
        # nothing at all.
        ("1E-20", "0"),
        ("0.1234567890123", "0.123456789012"),
    ],
)
def test_a_number_needing_more_scale_than_the_column_is_still_read(
    db_session: Session, written: str, recorded: str
) -> None:
    """
    Scale is **not** bounded, and this pins what that costs.

    The magnitude bound refuses values the column cannot hold at all.
    Decimal places are a different matter: the column carries twelve,
    and a value needing more is recorded rounded rather than refused -
    because a register legitimately holds such numbers and losing the
    workbook over one would be the worse trade.

    So this asserts the rounding rather than pretending it does not
    happen. ``literal_text`` keeps the reading the file states, and
    ADR-0034 makes it the authoritative rendering for exactly this
    reason: these columns make a number queryable, they are not a
    second original.
    """

    _stored_number(db_session, written, f"scale-{written}")

    cell = (
        SqlAlchemyCanonicalWorkbookRepository(db_session)
        .find_by_identity(1, f"scale-{written}")
        .worksheets[0]
        .rows[0]
        .cells[0]
    )

    assert cell.literal.number == Decimal(recorded)
    # The exact reading survives, in the column that is authoritative
    # for it.
    assert cell.literal.text == written
