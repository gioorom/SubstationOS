"""
What a hit shows the engineer: the text that matched, and the position
it was found at.

Two rules run through this file. A snippet shows the **source**, never
the matcher's version of it - ``150/20 kV`` and ``-Q1`` reach the
screen exactly as the document wrote them. And a location is either
known or declared unknown; it is never inferred, because a page number
that is merely plausible sends somebody to the wrong drawing.
"""

from __future__ import annotations

import pytest

from app.domain.document_search import search_location, search_snippet
from app.domain.document_search.search_location import (
    cell_reference,
    column_at_offset,
    column_letter,
)
from app.domain.document_search.search_models import (
    SegmentKind,
    SegmentLocation,
)
from app.domain.document_search.search_snippet import (
    MAX_SNIPPET_CHARACTERS,
)


def _highlighted(text: str, terms: tuple[str, ...]) -> list[str]:
    """The exact source substrings a snippet would emphasise."""

    snippet = search_snippet.build(text, terms)

    return [
        snippet.text[highlight.start : highlight.end]
        for highlight in snippet.highlights
    ]


class TestASnippetShowsWhyItMatched:
    def test_every_matched_term_is_highlighted(self) -> None:
        text = "Sezionatore -Q1 del trasformatore TR1 da 150/20 kV"

        assert _highlighted(text, ("-q1", "tr1")) == ["-Q1", "TR1"]

    def test_a_highlight_shows_the_source_spelling_not_the_folded_one(
        self,
    ) -> None:
        """
        The matcher compared ``tr1``. The engineer reads ``TR1``.
        """

        assert _highlighted("Trasformatore TR1", ("tr1",)) == ["TR1"]

    def test_an_aspect_prefix_is_inside_the_highlight(self) -> None:
        """
        Highlighting ``Q1`` while the document says ``-Q1`` would show
        the engineer a designation the document does not contain.
        """

        assert _highlighted("Interruttore -Q1 aperto", ("-q1",)) == ["-Q1"]

    def test_a_term_that_is_not_present_highlights_nothing(self) -> None:
        assert _highlighted("Trasformatore TR1", ("tr9",)) == []

    def test_a_short_segment_is_shown_whole(self) -> None:
        text = "Trasformatore TR1"
        snippet = search_snippet.build(text, ("tr1",))

        assert snippet.text == text
        assert not snippet.truncated_before
        assert not snippet.truncated_after


class TestALongSegmentIsCutHonestly:
    @pytest.fixture()
    def long_line(self) -> str:
        return (
            "premessa " * 30 + "il sezionatore -Q1 protegge " + "coda " * 40
        )

    def test_the_match_is_inside_the_part_that_is_shown(
        self, long_line: str
    ) -> None:
        snippet = search_snippet.build(long_line, ("-q1",))

        assert "-Q1" in snippet.text

    def test_cutting_is_declared_at_both_ends(
        self, long_line: str
    ) -> None:
        snippet = search_snippet.build(long_line, ("-q1",))

        assert snippet.truncated_before
        assert snippet.truncated_after

    def test_the_snippet_reports_where_it_starts_in_the_segment(
        self, long_line: str
    ) -> None:
        """
        Without this a highlight could not be turned back into a
        position in the row - which is how a spreadsheet hit finds its
        cell.
        """

        snippet = search_snippet.build(long_line, ("-q1",))
        offset = snippet.source_start + snippet.highlights[0].start

        assert long_line[offset : offset + 3] == "-Q1"

    def test_the_cut_does_not_slice_a_designation_in_half(
        self, long_line: str
    ) -> None:
        snippet = search_snippet.build(long_line, ("-q1",))

        assert not snippet.text.startswith("remessa")
        assert snippet.text[0] != "a"

    def test_a_segment_with_no_match_still_shows_its_opening(self) -> None:
        text = "x" * (MAX_SNIPPET_CHARACTERS * 2)
        snippet = search_snippet.build(text, ("tr1",))

        assert snippet.text
        assert snippet.highlights == ()
        assert snippet.truncated_after


class TestASpreadsheetCellIsNamedAsASheetNamesIt:
    @pytest.mark.parametrize(
        ("number", "letter"),
        [(1, "A"), (2, "B"), (26, "Z"), (27, "AA"), (28, "AB"), (52, "AZ")],
    )
    def test_a_column_is_named_by_its_letter(
        self, number: int, letter: str
    ) -> None:
        assert column_letter(number) == letter

    def test_there_is_no_column_zero_to_name(self) -> None:
        assert column_letter(0) is None

    def test_a_cell_is_named_in_a1_notation(self) -> None:
        assert cell_reference(12, 2) == "B12"

    @pytest.mark.parametrize(
        ("row", "column"), [(None, 2), (12, None), (0, 2)]
    )
    def test_half_a_reference_is_not_a_reference(
        self, row: int | None, column: int | None
    ) -> None:
        assert cell_reference(row, column) is None


class TestTheCellBehindARowHitIsRecovered:
    """
    A spreadsheet segment is a whole row, so that a query spanning
    several columns can match at all. The exact cell is then worked out
    from where the match fell.
    """

    OFFSETS = ((1, 0), (3, 12), (7, 40))

    @pytest.mark.parametrize(
        ("offset", "expected"), [(0, 1), (5, 1), (12, 3), (39, 3), (41, 7)]
    )
    def test_the_cell_that_owns_an_offset_is_found(
        self, offset: int, expected: int
    ) -> None:
        assert column_at_offset(self.OFFSETS, offset) == expected

    def test_an_offset_before_the_first_cell_belongs_to_no_column(
        self,
    ) -> None:
        assert column_at_offset(((2, 5),), 0) is None

    def test_unknown_boundaries_name_no_column(self) -> None:
        assert column_at_offset((), 10) is None

    def test_a_row_hit_names_its_cell_when_the_match_allows(self) -> None:
        descriptor = search_location.describe(
            SegmentKind.SPREADSHEET_ROW,
            SegmentLocation(
                worksheet_name="Cavi",
                row_number=12,
                cell_offsets=self.OFFSETS,
            ),
            match_offset=12,
        )

        assert descriptor.determined
        assert descriptor.worksheet_name == "Cavi"
        assert descriptor.cell_reference == "C12"

    def test_a_row_hit_stops_at_the_row_when_it_cannot_do_better(
        self,
    ) -> None:
        """
        No offset, no boundaries: the sheet and row are still true, and
        a cell is not invented to complete the picture.
        """

        descriptor = search_location.describe(
            SegmentKind.SPREADSHEET_ROW,
            SegmentLocation(worksheet_name="Cavi", row_number=12),
        )

        assert descriptor.determined
        assert descriptor.row_number == 12
        assert descriptor.cell_reference is None


class TestALocationIsNeverInvented:
    def test_a_pdf_line_is_located_by_its_page(self) -> None:
        descriptor = search_location.describe(
            SegmentKind.PDF_LINE, SegmentLocation(page_number=3)
        )

        assert descriptor.determined
        assert descriptor.page_number == 3

    def test_a_pdf_line_without_a_page_says_so(self) -> None:
        descriptor = search_location.describe(
            SegmentKind.PDF_LINE, SegmentLocation(line_index=4)
        )

        assert not descriptor.determined
        assert descriptor.page_number is None

    def test_a_row_with_no_coordinates_at_all_says_so(self) -> None:
        descriptor = search_location.describe(
            SegmentKind.SPREADSHEET_ROW, SegmentLocation()
        )

        assert not descriptor.determined

    def test_an_undetermined_location_carries_nothing_else(self) -> None:
        """
        A caller that ignored ``determined`` must still not find a
        number to display.
        """

        descriptor = search_location.describe(
            SegmentKind.PDF_LINE, SegmentLocation()
        )

        assert (
            descriptor.page_number,
            descriptor.worksheet_name,
            descriptor.row_number,
            descriptor.cell_reference,
        ) == (None, None, None, None)

    def test_a_pdf_is_never_described_with_spreadsheet_coordinates(
        self,
    ) -> None:
        """
        A segment carrying the wrong family's fields is reported
        unknown, not translated into the other family's vocabulary.
        """

        descriptor = search_location.describe(
            SegmentKind.PDF_LINE,
            SegmentLocation(worksheet_name="Cavi", row_number=12),
        )

        assert not descriptor.determined
