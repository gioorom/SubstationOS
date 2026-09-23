"""
The search endpoint as an engineer's browser meets it.

What matters here is the *contract*: a result names a document, says
where in it, shows the text, and says plainly when it knows no position.
Nothing in the response mentions segments, canonical representations or
artifact identities - the reader is an electrical engineer, not a
maintainer of this system.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.document_search.canonical_segment_reader import (
    CanonicalSegmentReader,
)
from app.infrastructure.document_search.sqlalchemy_document_search_repository import (  # noqa: E501
    SqlAlchemyDocumentSearchRepository,
)
from app.routers.document_search import MAX_QUERY_CHARACTERS
from app.services.document_search_service import (
    SEARCH_MAX_PAGE_SIZE,
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
def indexed_project(db_session: Session):
    """A project with a diagram and a cable schedule, both indexed."""

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

    service = DocumentSearchService(
        SqlAlchemyDocumentSearchRepository(db_session),
        CanonicalSegmentReader(db_session),
    )
    service.index_document(diagram.id)
    service.index_document(schedule.id)

    return project


def _search(client: TestClient, project_id: int, query: str, **params):
    return client.get(
        f"/projects/{project_id}/search",
        params={"q": query, **params},
    )


class TestTheShapeOfAnAnswer:
    def test_a_search_returns_what_it_searched_for(
        self, api_client: TestClient, indexed_project
    ):
        response = _search(api_client, indexed_project.id, "TR1 150 kV")

        assert response.status_code == 200

        body = response.json()

        assert body["query"] == "TR1 150 kV"
        assert body["terms"] == ["tr1", "150", "kv"]
        assert body["project_id"] == indexed_project.id

    def test_results_arrive_grouped_under_their_document(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "TR1").json()

        assert body["total_documents"] == len(body["documents"])

        for document in body["documents"]:
            assert document["filename"]
            assert document["source_type"] in {"pdf", "spreadsheet"}
            assert document["matches"]

    def test_a_pdf_result_names_its_page(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "MORSETTIERA").json()
        document = next(
            d for d in body["documents"] if d["source_type"] == "pdf"
        )
        location = document["matches"][0]["location"]

        assert location["determined"] is True
        assert location["page_number"] == 3

    def test_a_spreadsheet_result_names_its_sheet_and_cell(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "-W3").json()
        document = next(
            d
            for d in body["documents"]
            if d["source_type"] == "spreadsheet"
        )
        location = document["matches"][0]["location"]

        assert location["determined"] is True
        assert location["worksheet_name"] == "Cavi"
        assert location["row_number"] == 4
        assert location["cell_reference"] == "A4"

    def test_a_match_in_a_later_column_names_that_column(
        self, api_client: TestClient, indexed_project
    ):
        """
        The row is the segment, so the cell has to be worked out from
        where the match fell. ``MORSETTIERA E1`` is in the third column.
        """

        body = _search(
            api_client, indexed_project.id, "MORSETTIERA"
        ).json()
        document = next(
            d
            for d in body["documents"]
            if d["source_type"] == "spreadsheet"
        )
        location = document["matches"][0]["location"]

        assert location["cell_reference"] == "C4"

    def test_the_document_version_is_carried_with_the_result(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "MORSETTIERA").json()
        document = next(
            d for d in body["documents"] if d["source_type"] == "pdf"
        )

        assert document["content_checksum"] == "a" * 64


class TestTheSnippetShownToTheReader:
    def test_the_snippet_is_the_source_text(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "-Q1").json()
        snippet = body["documents"][0]["matches"][0]["snippet"]

        assert "-Q1" in snippet["text"]

    def test_the_highlight_covers_exactly_what_was_searched(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "-Q1").json()
        match = body["documents"][0]["matches"][0]
        text = match["snippet"]["text"]

        highlighted = [
            text[h["start"] : h["end"]]
            for h in match["snippet"]["highlights"]
        ]

        assert highlighted == ["-Q1"]

    def test_a_highlight_keeps_the_aspect_prefix(
        self, api_client: TestClient, indexed_project
    ):
        """
        Emphasising ``Q1`` inside ``-Q1`` would show the engineer a
        designation the document does not contain.
        """

        body = _search(api_client, indexed_project.id, "-Q1").json()
        match = body["documents"][0]["matches"][0]
        text = match["snippet"]["text"]
        first = match["snippet"]["highlights"][0]

        assert text[first["start"]] == "-"


class TestWhenNothingMatches:
    def test_nothing_found_is_said_plainly(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "TR9").json()

        assert body["total_matches"] == 0
        assert body["total_documents"] == 0
        assert body["documents"] == []

    def test_a_prefixed_designation_that_exists_is_offered_not_applied(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "Q1").json()

        assert body["documents"] == []
        assert body["suggestions"] == [
            {"term": "q1", "present_variants": ["-q1"]}
        ]

    def test_a_term_with_no_near_miss_offers_nothing(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "TR9").json()

        assert body["suggestions"] == []

    def test_an_empty_query_returns_an_empty_answer(
        self, api_client: TestClient, indexed_project
    ):
        body = _search(api_client, indexed_project.id, "").json()

        assert body["terms"] == []
        assert body["documents"] == []
        assert body["total_matches"] == 0


class TestTheEndpointIsScopedAndBounded:
    def test_a_project_that_does_not_exist_is_reported_not_empty(
        self, api_client: TestClient, indexed_project
    ):
        """
        An empty result would read as "nothing in this project", which
        is a different and misleading statement.
        """

        response = _search(api_client, indexed_project.id + 999, "TR1")

        assert response.status_code == 404

    def test_a_page_larger_than_the_ceiling_is_refused(
        self, api_client: TestClient, indexed_project
    ):
        response = _search(
            api_client, indexed_project.id, "TR1", limit=SEARCH_MAX_PAGE_SIZE + 1
        )

        assert response.status_code == 422

    def test_a_negative_offset_is_refused(
        self, api_client: TestClient, indexed_project
    ):
        response = _search(
            api_client, indexed_project.id, "TR1", offset=-1
        )

        assert response.status_code == 422

    def test_a_query_longer_than_the_ceiling_is_refused(
        self, api_client: TestClient, indexed_project
    ):
        """
        Every term becomes a scan of the project's text, so an endpoint
        that accepts unbounded text does unbounded work for whoever
        asks.
        """

        response = _search(
            api_client,
            indexed_project.id,
            "TR1 " * MAX_QUERY_CHARACTERS,
        )

        assert response.status_code == 422

    def test_paging_past_the_end_still_reports_the_real_totals(
        self, api_client: TestClient, indexed_project
    ):
        """
        Otherwise a "showing 1-20 of N" display would report zero on the
        last page.
        """

        first = _search(api_client, indexed_project.id, "TR1").json()
        past = _search(
            api_client, indexed_project.id, "TR1", offset=500
        ).json()

        assert first["total_matches"] > 0
        assert past["total_matches"] == first["total_matches"]
        assert past["documents"] == []
        assert past["suggestions"] == []

    def test_an_anonymous_caller_cannot_search(
        self, anonymous_client: TestClient, indexed_project
    ):
        response = _search(anonymous_client, indexed_project.id, "TR1")

        assert response.status_code in (401, 403)
