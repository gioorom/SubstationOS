"""
What the search index does when it reads something it did not write.

The index is a projection, so the realistic fault is not corruption but
**divergence**: a row written by one version of this code read back by
another. Two failure modes follow from that, and they are answered
differently on purpose.

A boundary it cannot decode costs the reader a cell reference, so it is
absorbed and the row is still reported. A *kind* it cannot decode means
the row cannot be placed at all, so it is raised - reporting it as a
missing result would tell an engineer the document does not say
something it does say.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.domain.document_search.search_exceptions import (
    DocumentSearchError,
    UnknownSegmentKindError,
)
from app.domain.document_search.search_models import (
    SearchSegment,
    SegmentKind,
    SegmentLocation,
)
from app.infrastructure.document_search.canonical_segment_reader import (
    CanonicalSegmentReader,
    _number_text,
)
from app.infrastructure.document_search.sqlalchemy_document_search_repository import (  # noqa: E501
    SqlAlchemyDocumentSearchRepository,
)
from app.models.document_search import DocumentSearchSegment
from tests._search_corpus import make_document, make_project


@pytest.fixture()
def repository(db_session: Session) -> SqlAlchemyDocumentSearchRepository:
    return SqlAlchemyDocumentSearchRepository(db_session)


@pytest.fixture()
def indexed_row(
    db_session: Session, repository: SqlAlchemyDocumentSearchRepository
):
    """One spreadsheet row, indexed, ready to be tampered with."""

    project = make_project(db_session, name="Stazione Alfa", code="ALF")
    document = make_document(
        db_session,
        project=project,
        filename="elenco_cavi.xlsx",
        checksum="b" * 64,
    )

    repository.replace_for_document(
        document.id,
        (
            SearchSegment(
                project_id=project.id,
                document_id=document.id,
                content_checksum="b" * 64,
                kind=SegmentKind.SPREADSHEET_ROW,
                location=SegmentLocation(
                    worksheet_index=0,
                    worksheet_name="Cavi",
                    row_number=3,
                    cell_offsets=((1, 0), (2, 6)),
                ),
                text="-W2 | TR2",
            ),
        ),
    )

    return project, document


def _stored(db_session: Session) -> DocumentSearchSegment:
    return db_session.query(DocumentSearchSegment).one()


class TestABoundaryItCannotDecode:
    @pytest.mark.parametrize(
        "stored",
        [
            "not json at all",
            "{}",
            "[1, 2]",
            '[["a", 0]]',
            "[[1]]",
            "null",
        ],
    )
    def test_the_row_is_still_returned(
        self,
        db_session: Session,
        repository: SqlAlchemyDocumentSearchRepository,
        indexed_row,
        stored: str,
    ) -> None:
        project, _ = indexed_row

        _stored(db_session).cell_offsets = stored
        db_session.commit()

        page = repository.search(
            project_id=project.id, terms=("-w2",), limit=10, offset=0
        )

        assert page.total_segments == 1

    def test_the_hit_simply_names_no_cell(
        self,
        db_session: Session,
        repository: SqlAlchemyDocumentSearchRepository,
        indexed_row,
    ) -> None:
        """
        Losing a cell reference is a smaller harm than losing the row -
        the sheet and row are still true.
        """

        project, _ = indexed_row

        _stored(db_session).cell_offsets = "{ not json"
        db_session.commit()

        hit = repository.search(
            project_id=project.id, terms=("-w2",), limit=10, offset=0
        ).hits[0]

        assert hit.location.cell_offsets == ()
        assert hit.location.worksheet_name == "Cavi"
        assert hit.location.row_number == 3


class TestAKindItCannotDecode:
    def test_reading_it_is_refused_rather_than_guessed(
        self,
        db_session: Session,
        repository: SqlAlchemyDocumentSearchRepository,
        indexed_row,
    ) -> None:
        project, _ = indexed_row

        _stored(db_session).kind = "spreadsheet_cell"
        db_session.commit()

        with pytest.raises(UnknownSegmentKindError):
            repository.search(
                project_id=project.id, terms=("-w2",), limit=10, offset=0
            )

    def test_the_failure_names_the_value_it_could_not_read(
        self,
        db_session: Session,
        repository: SqlAlchemyDocumentSearchRepository,
        indexed_row,
    ) -> None:
        project, _ = indexed_row

        _stored(db_session).kind = "carrier_pigeon"
        db_session.commit()

        with pytest.raises(UnknownSegmentKindError) as raised:
            repository.search(
                project_id=project.id, terms=("-w2",), limit=10, offset=0
            )

        assert raised.value.kind == "carrier_pigeon"

    def test_the_failure_belongs_to_this_context(self) -> None:
        assert issubclass(UnknownSegmentKindError, DocumentSearchError)


class TestANumberThatIsNotADecimal:
    """
    SQLite hands back a ``float`` for a ``Numeric`` column where other
    databases hand back a ``Decimal``.
    """

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [(150, "150"), (150.5, "150.5"), (0, "0")],
    )
    def test_it_is_rendered_as_it_stands(
        self, stored: object, expected: str
    ) -> None:
        assert _number_text(stored) == expected


class TestADocumentWithNothingToRead:
    def test_a_document_that_does_not_exist_yields_no_segments(
        self, db_session: Session
    ) -> None:
        assert CanonicalSegmentReader(db_session).segments_for(9999) == ()
