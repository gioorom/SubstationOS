"""
Service tests for Canonical Text Segmentation (Milestone 27.1), against a
real (in-memory) database through the real SQLAlchemy adapters.

The representation is stored through Milestone 26.1's own repository, so
these prove the two layers meet correctly - a fake representation source
could agree with the domain and disagree with what 26.1 actually
persists.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalPdfDocument,
)
from app.domain.canonical_text.canonical_text_failures import (
    SegmentationFailureCode,
)
from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.canonical_text.canonical_text_repository import (
    CanonicalTextRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
)
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.models.canonical_pdf import (
    CanonicalPdfPageRecord,
    CanonicalPdfRepresentation,
)
from app.models.canonical_text import CanonicalTextDocumentRecord
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.services import canonical_text_service
from tests.domain._canonical_text_support import (
    CHECKSUM,
    image_block,
    page,
    representation,
    span,
    text_block,
)


def _document(db: Session, document_id_hint: str = "schema.pdf"):
    document = DocumentRecord(
        filename=document_id_hint,
        file_path=f"/storage/{document_id_hint}",
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        project_name="Unknown",
        scope=DocumentScope.CANONICAL_LIBRARY,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _store_representation(
    db: Session, document_id: int, source: CanonicalPdfDocument
) -> None:
    from dataclasses import replace

    SqlAlchemyCanonicalRepresentationRepository(db).save(
        replace(source, document_id=document_id)
    )


def _segment(db: Session, document_id: int, **kwargs):
    return canonical_text_service.segment_document(
        SqlAlchemyCanonicalRepresentationRepository(db),
        kwargs.pop(
            "text_repository", SqlAlchemyCanonicalTextRepository(db)
        ),
        document_id=document_id,
        **kwargs,
    )


def _prepared(db: Session, source=None, **document_kwargs):
    """A document whose canonical representation is already stored - the
    state segmentation starts from."""

    document = _document(db, **document_kwargs)
    _store_representation(
        db,
        document.id,
        source
        or representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 0, "Rated voltage"),
                    span(1, 0, " 145 kV"),
                    span(2, 1, "Frequency 50 Hz"),
                ),
            )
        ),
    )

    return document


# --- The happy path --------------------------------------------------------


def test_a_representation_is_segmented(db_session: Session) -> None:
    document = _prepared(db_session)

    result = _segment(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.segmentation.section_count == 1
    assert result.segmentation.token_count == 7


def test_the_segmentation_records_the_representation_it_came_from(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    segmentation = _segment(db_session, document.id).segmentation

    assert segmentation.document_id == document.id
    assert segmentation.content_checksum == CHECKSUM
    assert segmentation.representation_version == "1.0"
    assert segmentation.segmentation_version == "1.0"


def test_a_multi_page_representation_segments_every_page(
    db_session: Session,
) -> None:
    document = _prepared(
        db_session,
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21"))),
            page(2, text_block(0, span(0, 0, "Bay 22"))),
            page(3, text_block(0, span(0, 0, "Bay 23"))),
        ),
    )

    segmentation = _segment(db_session, document.id).segmentation

    assert segmentation.section_count == 3
    assert [s.page_number for s in segmentation.sections] == [1, 2, 3]


# --- Persistence round-trip -------------------------------------------------


def test_the_segmentation_survives_a_round_trip_through_the_database(
    db_session: Session,
) -> None:
    document = _prepared(
        db_session,
        representation(
            page(
                1,
                text_block(0, span(0, 0, "Rated voltage"), span(1, 1, "145 kV")),
                image_block(1),
            ),
            page(2, text_block(0, span(0, 0, "Frequency 50 Hz"))),
        ),
    )

    built = _segment(db_session, document.id).segmentation
    stored = SqlAlchemyCanonicalTextRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_the_provenance_chain_survives_persistence(
    db_session: Session,
) -> None:
    """The chain is what every future extractor needs, so it must survive
    storage exactly - not approximately."""

    document = _prepared(
        db_session,
        representation(
            page(1, text_block(0, span(0, 0, "Cover sheet"))),
            page(
                2,
                text_block(0, span(0, 0, "Bay 21")),
                text_block(
                    1,
                    span(0, 0, "Ignored"),
                    span(1, 3, "Rated voltage 145 kV"),
                ),
            ),
        ),
    )
    _segment(db_session, document.id)

    stored = canonical_text_service.get_segmentation(
        SqlAlchemyCanonicalTextRepository(db_session), document.id
    )
    token = [
        token for token in stored.tokens() if token.text == "145"
    ][0]

    assert token.provenance.page_number == 2
    assert token.provenance.block_reading_order == 1
    assert token.provenance.span_reading_order == 1
    assert token.provenance.line_index == 3
    assert token.provenance.character_start == 14
    assert token.provenance.character_end == 17


def test_both_original_and_normalized_text_are_stored(
    db_session: Session,
) -> None:
    document = _prepared(
        db_session, representation(page(1, text_block(0, span(0, 0, "ﬁeld"))))
    )
    _segment(db_session, document.id)

    stored = canonical_text_service.get_segmentation(
        SqlAlchemyCanonicalTextRepository(db_session), document.id
    )
    token = list(stored.tokens())[0]

    assert token.text == "ﬁeld"
    assert token.normalized_text == "field"


def test_empty_sections_and_paragraphs_survive_persistence(
    db_session: Session,
) -> None:
    document = _prepared(
        db_session,
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21")), image_block(1)),
            page(2),
        ),
    )
    _segment(db_session, document.id)

    stored = canonical_text_service.get_segmentation(
        SqlAlchemyCanonicalTextRepository(db_session), document.id
    )

    assert stored.section_count == 2
    assert stored.sections[0].paragraphs[1].is_empty
    assert stored.sections[1].is_empty


def test_a_document_never_segmented_has_no_segmentation(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    assert (
        canonical_text_service.get_segmentation(
            SqlAlchemyCanonicalTextRepository(db_session), document.id
        )
        is None
    )


# --- The representation is never modified ------------------------------------


def test_segmenting_never_modifies_the_canonical_representation(
    db_session: Session,
) -> None:
    """A segmentation is derived *from* a representation, and deriving
    something must never modify what it was derived from."""

    document = _prepared(db_session)
    representation_repository = SqlAlchemyCanonicalRepresentationRepository(
        db_session
    )
    before = representation_repository.find_latest_for_document(document.id)

    _segment(db_session, document.id)

    assert (
        representation_repository.find_latest_for_document(document.id)
        == before
    )
    assert (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document.id)
        .count()
        == 1
    )


def test_segmenting_never_modifies_the_document_row(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    filename, file_path = document.filename, document.file_path

    _segment(db_session, document.id)
    db_session.refresh(document)

    assert document.filename == filename
    assert document.file_path == file_path


# --- Idempotency --------------------------------------------------------------


def test_re_running_reuses_the_stored_segmentation(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    first = _segment(db_session, document.id)
    second = _segment(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.segmentation == first.segmentation


def test_re_running_creates_no_second_row(db_session: Session) -> None:
    document = _prepared(db_session)

    _segment(db_session, document.id)
    _segment(db_session, document.id)
    _segment(db_session, document.id)

    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_new_representation_produces_a_new_segmentation(
    db_session: Session,
) -> None:
    """The document changed, so its checksum changed, so the segmentation
    is a different value - stored alongside, never over, the old one."""

    document = _prepared(
        db_session,
        representation(page(1, text_block(0, span(0, 0, "Revision 02")))),
    )
    first = _segment(db_session, document.id).segmentation

    _store_representation(
        db_session,
        document.id,
        representation(
            page(1, text_block(0, span(0, 0, "Revision 03"))),
            content_checksum="d" * 64,
        ),
    )
    second = _segment(db_session, document.id)

    assert second.reused is False
    assert second.segmentation.content_checksum != first.content_checksum
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 2
    )


def test_the_historical_segmentation_stays_readable(
    db_session: Session,
) -> None:
    document = _prepared(
        db_session,
        representation(page(1, text_block(0, span(0, 0, "Revision 02")))),
    )
    first = _segment(db_session, document.id).segmentation

    _store_representation(
        db_session,
        document.id,
        representation(
            page(1, text_block(0, span(0, 0, "Revision 03"))),
            content_checksum="d" * 64,
        ),
    )
    _segment(db_session, document.id)

    historical = SqlAlchemyCanonicalTextRepository(
        db_session
    ).find_for_representation(document.id, CHECKSUM, "1.0")

    assert historical == first


def test_a_new_segmentation_version_segments_again(
    db_session: Session,
) -> None:
    """The rules changed, so the result is a different value even though
    the representation is identical - which is exactly why the version is
    part of the key."""

    document = _prepared(db_session)
    _segment(db_session, document.id)

    result = _segment(db_session, document.id, segmentation_version="2.0")

    assert result.reused is False
    assert result.segmentation.segmentation_version == "2.0"
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 2
    )


# --- Typed failures -----------------------------------------------------------


def test_a_document_with_no_representation_is_refused(
    db_session: Session,
) -> None:
    """Segmentation is the step after canonicalisation. Its only input is
    the representation - it never reads the original PDF."""

    document = _document(db_session)

    result = _segment(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        SegmentationFailureCode.CANONICAL_REPRESENTATION_MISSING
    )


def test_an_unknown_document_is_refused_the_same_way(
    db_session: Session,
) -> None:
    result = _segment(db_session, 4321)

    assert result.failure.code is (
        SegmentationFailureCode.CANONICAL_REPRESENTATION_MISSING
    )


def test_an_unsupported_representation_version_is_refused(
    db_session: Session,
) -> None:
    """A representation built under a newer contract may carry fields
    whose meaning this code would misinterpret. A wrong structure is
    worse than a visible refusal."""

    document = _document(db_session)
    db_session.add(
        CanonicalPdfRepresentation(
            document_id=document.id,
            content_checksum=CHECKSUM,
            checksum_algorithm="sha256",
            representation_version="99.0",
            parser_name="pymupdf",
            parser_version="1.28.0",
            page_count=0,
        )
    )
    db_session.commit()

    result = _segment(db_session, document.id)

    assert result.failure.code is (
        SegmentationFailureCode.UNSUPPORTED_REPRESENTATION_VERSION
    )
    assert "99.0" in result.failure.message


def test_a_stored_representation_that_no_longer_holds_together_is_refused(
    db_session: Session,
) -> None:
    """
    The representation is rebuilt through the canonical factory on read,
    so a row that violates its own invariants - here, a page sequence
    starting at 2 - is caught before segmentation begins rather than
    discovered halfway through. Distinct from a segmenter fault: the
    input was already wrong.
    """

    document = _document(db_session)
    stored = CanonicalPdfRepresentation(
        document_id=document.id,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
        representation_version="1.0",
        parser_name="pymupdf",
        parser_version="1.28.0",
        page_count=1,
    )
    stored.pages.append(
        CanonicalPdfPageRecord(page_number=2, width=595.0, height=842.0)
    )
    db_session.add(stored)
    db_session.commit()

    result = _segment(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        SegmentationFailureCode.INVALID_CANONICAL_REPRESENTATION
    )


def test_a_representation_that_segments_to_nothing_is_not_persisted(
    db_session: Session,
) -> None:
    """Persisting it would give every future extractor a document that
    appears to say nothing - indistinguishable from one that genuinely
    does."""

    document = _prepared(
        db_session, representation(page(1, text_block(0, span(0, 0, "   "))))
    )

    result = _segment(db_session, document.id)

    assert result.failure.code is (
        SegmentationFailureCode.SEGMENTATION_FAILURE
    )
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 0
    )


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(CanonicalTextRepository):
        def save(self, segmentation: CanonicalTextDocument) -> None:
            raise RuntimeError("the disk is full")

        def find_for_representation(
            self, document_id, content_checksum, segmentation_version
        ):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _prepared(db_session)

    result = _segment(
        db_session, document.id, text_repository=FailingRepository()
    )

    assert result.failure.code is (
        SegmentationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    document = _document(db_session)

    result = _segment(db_session, document.id)

    assert result.failure.message
    assert result.segmentation is None


# --- No PDF is ever reopened ---------------------------------------------------


def test_segmentation_works_with_no_file_on_disk(
    db_session: Session, tmp_path: Path
) -> None:
    """The strongest available proof that the original PDF is not read:
    the document's ``file_path`` points at a file that never existed, and
    segmentation succeeds regardless. Its input is the representation."""

    document = _prepared(db_session)
    document.file_path = str(tmp_path / "never_written.pdf")
    db_session.commit()

    result = _segment(db_session, document.id)

    assert result.succeeded
    assert result.segmentation.token_count == 7
