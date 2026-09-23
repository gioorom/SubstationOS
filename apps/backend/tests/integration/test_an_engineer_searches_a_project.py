"""
Searching a project's documents, from indexing to answer.

These tests are written from the engineer's side of the screen. They
ask the questions somebody standing in front of a substation would ask
- *where does it say TR1?*, *is that -Q1 or Q1?*, *which sheet is that
cable on?* - and assert on what comes back, not on how it was found.

The corpus is invented, deterministic, and built as canonical
representations (see ``tests/_search_corpus.py``).
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.domain.document_search.search_models import SegmentKind
from app.models.canonical_pdf import CanonicalPdfRepresentation
from app.infrastructure.document_search.canonical_segment_reader import (
    CanonicalSegmentReader,
)
from app.infrastructure.document_search.sqlalchemy_document_search_repository import (  # noqa: E501
    SqlAlchemyDocumentSearchRepository,
)
from app.models.canonical_spreadsheet import (
    CanonicalWorksheetRecord,
    WorksheetVisibility,
)
from app.services.document_search_service import (
    MAX_QUERY_TERMS,
    DocumentSearchService,
)
from tests._search_corpus import (
    CABLE_SCHEDULE,
    SINGLE_LINE_DIAGRAM,
    add_pdf_pages,
    add_worksheet,
    make_document,
    make_project,
)


@pytest.fixture()
def search(db_session: Session) -> DocumentSearchService:
    return DocumentSearchService(
        SqlAlchemyDocumentSearchRepository(db_session),
        CanonicalSegmentReader(db_session),
    )


@pytest.fixture()
def station(db_session: Session, search: DocumentSearchService):
    """
    One project holding a single-line diagram and a cable schedule,
    both indexed.
    """

    project = make_project(db_session, name="Stazione Alfa", code="ALF")

    diagram = make_document(
        db_session,
        project=project,
        filename="schema_unifilare.pdf",
        checksum="a" * 64,
    )
    add_pdf_pages(db_session, diagram, SINGLE_LINE_DIAGRAM)

    schedule = make_document(
        db_session,
        project=project,
        filename="elenco_cavi.xlsx",
        checksum="b" * 64,
    )
    add_worksheet(
        db_session, schedule, sheet_name="Cavi", rows=CABLE_SCHEDULE
    )

    search.index_document(diagram.id)
    search.index_document(schedule.id)

    return project, diagram, schedule


def _texts(outcome) -> list[str]:
    return [
        hit.text for group in outcome.documents for hit in group.hits
    ]


class TestFindingATechnicalIdentifier:
    def test_a_transformer_is_found_by_its_tag(self, search, station):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR1")

        assert outcome.total_segments > 0
        assert all("TR1" in text for text in _texts(outcome))

    def test_the_search_is_not_case_sensitive(self, search, station):
        project, _, _ = station

        assert search.search(
            project_id=project.id, query="tr1"
        ).total_segments == search.search(
            project_id=project.id, query="TR1"
        ).total_segments

    @pytest.mark.parametrize(
        "designation", ["TR1", "Q01", "-Q1", "+189L", "M1", "189L"]
    )
    def test_every_designation_in_the_corpus_is_findable(
        self, search, station, designation: str
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query=designation)

        assert outcome.total_segments > 0, designation

    def test_a_tag_is_not_found_inside_a_longer_tag(self, search, station):
        """``TR1`` must not answer for ``TR2``, and vice versa."""

        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR2")

        assert all("TR2" in text for text in _texts(outcome))
        assert not any(
            "TR1" in text and "TR2" not in text for text in _texts(outcome)
        )


class TestAnAspectPrefixIsNotDiscarded:
    """
    The requirement this epic turned on: ``-Q1`` and ``Q1`` must not
    become one thing.
    """

    def test_the_two_designations_return_different_results(
        self, search, station
    ):
        project, _, _ = station

        with_prefix = search.search(project_id=project.id, query="-Q1")
        without = search.search(project_id=project.id, query="Q1")

        assert with_prefix.total_segments > 0
        assert without.found_nothing

    def test_every_hit_for_the_prefixed_form_really_carries_the_prefix(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="-Q1")

        assert all("-Q1" in text for text in _texts(outcome))

    def test_the_location_designation_is_distinct_from_the_bare_number(
        self, search, station
    ):
        project, _, _ = station

        located = search.search(project_id=project.id, query="+189L")
        bare = search.search(project_id=project.id, query="189L")

        assert located.total_segments > 0
        assert bare.total_segments > 0
        assert _texts(located) != _texts(bare)


class TestMixedAndOrdinaryQueries:
    def test_a_word_of_ordinary_italian_is_found(self, search, station):
        project, _, _ = station

        outcome = search.search(
            project_id=project.id, query="trasformatore"
        )

        assert outcome.total_segments > 0

    def test_two_words_narrow_the_search(self, search, station):
        project, _, _ = station

        one = search.search(project_id=project.id, query="quadro")
        two = search.search(project_id=project.id, query="quadro MT")

        assert 0 < two.total_segments <= one.total_segments

    def test_a_tag_with_a_rating_finds_the_line_carrying_both(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(
            project_id=project.id, query="TR1 150 kV"
        )

        assert outcome.total_segments > 0

        for text in _texts(outcome):
            assert "TR1" in text and "150" in text and "kV" in text

    def test_a_rating_written_with_a_slash_is_found_by_either_value(
        self, search, station
    ):
        project, _, _ = station

        assert (
            search.search(project_id=project.id, query="150").total_segments
            > 0
        )
        assert (
            search.search(project_id=project.id, query="20").total_segments
            > 0
        )

    def test_a_query_of_nothing_returns_nothing(self, search, station):
        project, _, _ = station

        for query in ("", "   ", "()"):
            outcome = search.search(project_id=project.id, query=query)

            assert outcome.terms == ()
            assert outcome.found_nothing


class TestAResultSaysWhereItCameFrom:
    def test_results_are_grouped_under_their_document(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR1")
        filenames = [
            group.document_filename for group in outcome.documents
        ]

        assert len(filenames) == len(set(filenames))

    def test_a_document_is_named_and_its_version_carried(
        self, search, station
    ):
        project, diagram, _ = station

        outcome = search.search(project_id=project.id, query="MORSETTIERA")
        group = next(
            g
            for g in outcome.documents
            if g.document_id == diagram.id
        )

        assert group.document_filename == "schema_unifilare.pdf"
        assert group.content_checksum == "a" * 64
        assert group.kind is SegmentKind.PDF_LINE

    def test_a_pdf_hit_knows_its_page(self, search, station):
        project, diagram, _ = station

        outcome = search.search(project_id=project.id, query="M1")
        hit = next(
            hit
            for group in outcome.documents
            if group.document_id == diagram.id
            for hit in group.hits
        )

        assert hit.location.page_number == 3

    def test_a_spreadsheet_hit_knows_its_sheet_and_row(
        self, search, station
    ):
        project, _, schedule = station

        outcome = search.search(project_id=project.id, query="-W2")
        hit = next(
            hit
            for group in outcome.documents
            if group.document_id == schedule.id
            for hit in group.hits
        )

        assert hit.kind is SegmentKind.SPREADSHEET_ROW
        assert hit.location.worksheet_name == "Cavi"
        assert hit.location.row_number == 3

    def test_a_spreadsheet_row_records_where_each_cell_begins(
        self, search, station
    ):
        """
        The boundaries are what let a hit name a cell rather than only
        a row.
        """

        project, _, schedule = station

        outcome = search.search(project_id=project.id, query="-W2")
        hit = next(
            hit
            for group in outcome.documents
            if group.document_id == schedule.id
            for hit in group.hits
        )

        assert hit.location.cell_offsets
        assert hit.location.cell_offsets[0] == (1, 0)


class TestNothingFound:
    def test_a_term_the_project_does_not_contain_finds_nothing(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR9")

        assert outcome.found_nothing
        assert outcome.documents == ()

    def test_an_empty_result_still_reports_what_was_searched_for(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR9 Quadro")

        assert outcome.terms == ("tr9", "quadro")

    def test_a_missing_designation_names_the_prefixed_one_that_exists(
        self, search, station
    ):
        """
        Searching ``Q1`` in a project that writes ``-Q1`` is told so -
        and is not silently given ``-Q1`` instead.
        """

        project, _, _ = station

        outcome = search.search(project_id=project.id, query="Q1")

        assert outcome.found_nothing

        suggestion = next(s for s in outcome.suggestions if s.term == "q1")

        assert "-q1" in suggestion.present_variants

    def test_a_term_with_no_relative_in_the_project_suggests_nothing(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR9")

        assert all(
            not s.present_variants for s in outcome.suggestions
        )


class TestOneProjectCannotSeeAnother:
    """
    The acceptance test this epic was specified around: two projects,
    each with a document naming a different transformer, and neither
    search may reach across.
    """

    @pytest.fixture()
    def two_stations(self, db_session: Session, search):
        alfa = make_project(db_session, name="Stazione Alfa", code="ALF")
        beta = make_project(db_session, name="Stazione Beta", code="BET")

        alfa_document = make_document(
            db_session,
            project=alfa,
            filename="alfa.pdf",
            checksum="1" * 64,
        )
        add_pdf_pages(
            db_session,
            alfa_document,
            {1: ["Trasformatore TR1 della stazione Alfa"]},
        )

        beta_document = make_document(
            db_session,
            project=beta,
            filename="beta.pdf",
            checksum="2" * 64,
        )
        add_pdf_pages(
            db_session,
            beta_document,
            {1: ["Trasformatore TR2 della stazione Beta"]},
        )

        search.index_document(alfa_document.id)
        search.index_document(beta_document.id)

        return alfa, beta

    def test_each_project_finds_only_its_own_transformer(
        self, search, two_stations
    ):
        alfa, beta = two_stations

        assert (
            search.search(project_id=alfa.id, query="TR1").total_segments
            == 1
        )
        assert search.search(
            project_id=alfa.id, query="TR2"
        ).found_nothing

        assert (
            search.search(project_id=beta.id, query="TR2").total_segments
            == 1
        )
        assert search.search(
            project_id=beta.id, query="TR1"
        ).found_nothing

    def test_the_same_identifier_in_two_projects_stays_separate(
        self, db_session: Session, search, two_stations
    ):
        """
        The realistic case: every station has a ``TR1``. A search must
        answer for one station's, never both.
        """

        alfa, beta = two_stations

        beta_second = make_document(
            db_session,
            project=beta,
            filename="beta_secondo.pdf",
            checksum="3" * 64,
        )
        add_pdf_pages(
            db_session, beta_second, {1: ["Trasformatore TR1 di Beta"]}
        )
        search.index_document(beta_second.id)

        alfa_hits = search.search(project_id=alfa.id, query="TR1")
        beta_hits = search.search(project_id=beta.id, query="TR1")

        assert alfa_hits.total_segments == 1
        assert beta_hits.total_segments == 1
        assert (
            alfa_hits.documents[0].document_filename == "alfa.pdf"
        )
        assert (
            beta_hits.documents[0].document_filename == "beta_secondo.pdf"
        )

    def test_a_document_belonging_to_no_project_answers_no_project(
        self, db_session: Session, search, two_stations
    ):
        """
        A Canonical Library document is filed under no project
        (ADR-0005), so no project-scoped search may return it.
        """

        alfa, beta = two_stations

        library = make_document(
            db_session,
            project=None,
            filename="norma.pdf",
            checksum="4" * 64,
        )
        add_pdf_pages(
            db_session, library, {1: ["Trasformatore TR1 secondo norma"]}
        )
        search.index_document(library.id)

        assert (
            search.search(project_id=alfa.id, query="TR1").total_segments
            == 1
        )
        assert search.search(
            project_id=beta.id, query="TR1"
        ).found_nothing


class TestIndexingAgainDoesNotDuplicate:
    def test_a_document_indexed_twice_answers_once(
        self, search, station
    ):
        project, diagram, _ = station

        before = search.search(project_id=project.id, query="TR1")
        search.index_document(diagram.id)
        after = search.search(project_id=project.id, query="TR1")

        assert after.total_segments == before.total_segments

    def test_a_document_that_can_no_longer_be_read_stops_answering(
        self, db_session: Session, search, station
    ):
        """
        Re-indexing with nothing to read clears what was indexed
        before. This is the only way a document leaves the index, and
        the reason the port offers no separate deletion.
        """

        project, diagram, _ = station

        db_session.query(CanonicalPdfRepresentation).filter(
            CanonicalPdfRepresentation.document_id == diagram.id
        ).delete()
        db_session.commit()

        assert search.index_document(diagram.id) == 0

        outcome = search.search(project_id=project.id, query="MORSETTIERA")

        assert all(
            group.document_id != diagram.id
            for group in outcome.documents
        )

    def test_a_document_with_nothing_to_read_indexes_to_nothing(
        self, db_session: Session, search, station
    ):
        project, _, _ = station

        unprocessed = make_document(
            db_session,
            project=project,
            filename="non_elaborato.pdf",
            checksum="9" * 64,
        )

        assert search.index_document(unprocessed.id) == 0


class TestAPageOfResults:
    def test_a_page_never_exceeds_what_was_asked_for(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(
            project_id=project.id, query="trasformatore", limit=1
        )
        returned = sum(len(g.hits) for g in outcome.documents)

        assert returned == 1
        assert outcome.total_segments >= 1

    def test_the_totals_describe_the_whole_result_not_the_page(
        self, search, station
    ):
        project, _, _ = station

        full = search.search(project_id=project.id, query="trasformatore")
        paged = search.search(
            project_id=project.id, query="trasformatore", limit=1
        )

        assert paged.total_segments == full.total_segments
        assert paged.total_documents == full.total_documents

    def test_the_same_query_returns_the_same_page_every_time(
        self, search, station
    ):
        project, _, _ = station

        first = search.search(project_id=project.id, query="trasformatore")
        second = search.search(project_id=project.id, query="trasformatore")

        assert _texts(first) == _texts(second)


class TestPagingPastTheEnd:
    """
    An empty page of a non-empty result is not an empty result. Saying
    otherwise would make any "showing 1-20 of N" display lie on the
    last page, and would run the near-miss explanation for a query that
    matched perfectly well.
    """

    def test_the_totals_still_describe_the_whole_result(
        self, search, station
    ):
        project, _, _ = station

        full = search.search(project_id=project.id, query="trasformatore")
        past = search.search(
            project_id=project.id, query="trasformatore", offset=500
        )

        assert full.total_segments > 0
        assert past.total_segments == full.total_segments
        assert past.total_documents == full.total_documents

    def test_no_document_is_returned_past_the_end(self, search, station):
        project, _, _ = station

        past = search.search(
            project_id=project.id, query="trasformatore", offset=500
        )

        assert past.documents == ()

    def test_a_query_that_matched_is_never_explained_away(
        self, search, station
    ):
        project, _, _ = station

        past = search.search(
            project_id=project.id, query="trasformatore", offset=500
        )

        assert past.suggestions == ()
        assert not past.found_nothing


class TestWhichTermIsBlamedForAnEmptyResult:
    """
    In ``TR1 XYZ`` it is ``XYZ`` that failed. Telling the engineer that
    ``TR1`` was the problem - because the query as a whole matched
    nothing - would say something untrue about their own query.
    """

    def test_only_the_term_that_matched_nothing_is_reported(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR1 XYZ")

        assert outcome.found_nothing
        assert [s.term for s in outcome.suggestions] == ["xyz"]

    def test_a_term_that_matches_on_its_own_is_not_blamed(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="Q1 -Q1")

        assert outcome.found_nothing
        assert [s.term for s in outcome.suggestions] == ["q1"]

    def test_the_blamed_term_still_carries_its_near_miss(
        self, search, station
    ):
        project, _, _ = station

        outcome = search.search(project_id=project.id, query="TR1 Q1")
        suggestion = next(s for s in outcome.suggestions if s.term == "q1")

        assert suggestion.present_variants == ("-q1",)


class TestAQueryCannotAskForUnboundedWork:
    def test_only_the_first_terms_of_a_long_query_are_searched(
        self, search, station
    ):
        """
        Each term is a separate scan of the project's text, so an
        unbounded query is unbounded work bought with one request.
        """

        project, _, _ = station
        outcome = search.search(
            project_id=project.id,
            query=" ".join(f"t{index}" for index in range(200)),
        )

        assert len(outcome.terms) == MAX_QUERY_TERMS

    def test_a_long_query_still_answers_rather_than_failing(
        self, search, station
    ):
        project, _, _ = station
        outcome = search.search(
            project_id=project.id,
            query=" ".join(f"t{index}" for index in range(2000)),
        )

        assert outcome.found_nothing


class TestAHiddenWorksheetIsStillPartOfTheDocument:
    def test_its_rows_are_searchable_and_name_their_sheet(
        self, db_session: Session, search
    ):
        """
        A hidden sheet in a cable schedule is a working sheet, not a
        secret one. Skipping it would answer "the document does not say
        that" about text the document does say.
        """

        project = make_project(db_session, name="Stazione Alfa", code="ALF")
        document = make_document(
            db_session,
            project=project,
            filename="elenco_cavi.xlsx",
            checksum="c" * 64,
        )
        workbook = add_worksheet(
            db_session,
            document,
            sheet_name="Calcoli",
            rows=[["-W9", "TR7", 400]],
        )

        worksheet = (
            db_session.query(CanonicalWorksheetRecord)
            .filter(CanonicalWorksheetRecord.workbook_id == workbook.id)
            .one()
        )
        worksheet.visibility = WorksheetVisibility.HIDDEN
        db_session.commit()

        search.index_document(document.id)
        outcome = search.search(project_id=project.id, query="TR7")

        assert outcome.total_segments == 1
        assert (
            outcome.documents[0].hits[0].location.worksheet_name
            == "Calcoli"
        )
