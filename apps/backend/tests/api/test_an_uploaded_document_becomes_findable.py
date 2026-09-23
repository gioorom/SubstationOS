"""
A document becomes searchable by being uploaded, and by nothing else.

This is the promise the whole feature rests on. An engineer uploads a
drawing and then looks for something in it; if indexing were a second
step somebody had to remember, the search box would be quietly wrong
for every document whose upload predated the habit.

These tests run the real chain - upload, pipeline, index - against a
generated PDF, so what they prove is that the stages actually meet.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document_search import DocumentSearchSegment
from tests._pdf_builder import multi_page_pdf, single_page_pdf
from tests._search_corpus import make_project


def _upload(
    api_client: TestClient, content: bytes, project_id: int
) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema_unifilare.pdf",
                io.BytesIO(content),
                "application/pdf",
            )
        },
        data={"scope": "project", "project_id": str(project_id)},
    )

    assert response.status_code == 200, response.text

    return response.json()["document"]


def _search(api_client: TestClient, project_id: int, query: str) -> dict:
    response = api_client.get(
        f"/projects/{project_id}/search", params={"q": query}
    )

    assert response.status_code == 200, response.text

    return response.json()


class TestUploadingMakesADocumentFindable:
    def test_an_uploaded_drawing_answers_a_search_with_no_further_step(
        self, api_client: TestClient, db_session: Session
    ):
        project = make_project(
            db_session, name="Stazione Alfa", code="ALF"
        )

        _upload(
            api_client,
            single_page_pdf("Trasformatore TR1 150/20 kV"),
            project.id,
        )

        body = _search(api_client, project.id, "TR1")

        assert body["total_matches"] >= 1
        assert body["documents"][0]["filename"] == "schema_unifilare.pdf"

    def test_the_result_names_the_page_the_text_is_on(
        self, api_client: TestClient, db_session: Session
    ):
        project = make_project(
            db_session, name="Stazione Alfa", code="ALF"
        )

        _upload(
            api_client,
            multi_page_pdf(
                "Copertina del progetto",
                "Sezionatore -Q1 lato alta tensione",
            ),
            project.id,
        )

        body = _search(api_client, project.id, "-Q1")
        location = body["documents"][0]["matches"][0]["location"]

        assert location["determined"] is True
        assert location["page_number"] == 2

    def test_the_result_carries_the_version_it_was_read_from(
        self, api_client: TestClient, db_session: Session
    ):
        """
        The checksum on a hit is the uploaded document's own, so a
        reader can tell which version of a drawing answered them.
        """

        project = make_project(
            db_session, name="Stazione Alfa", code="ALF"
        )

        document = _upload(
            api_client, single_page_pdf("Quadro MT +189L"), project.id
        )
        body = _search(api_client, project.id, "+189L")

        assert (
            body["documents"][0]["content_checksum"]
            == document["content_checksum"]
        )

    def test_uploading_a_document_twice_does_not_double_its_hits(
        self, api_client: TestClient, db_session: Session
    ):
        """
        Two uploads of the same bytes are two documents, each answering
        once - not one document answering twice.
        """

        project = make_project(
            db_session, name="Stazione Alfa", code="ALF"
        )
        content = single_page_pdf("Trasformatore TR1")

        _upload(api_client, content, project.id)
        first = _search(api_client, project.id, "TR1")

        _upload(api_client, content, project.id)
        second = _search(api_client, project.id, "TR1")

        assert second["total_documents"] == first["total_documents"] + 1

        for document in second["documents"]:
            assert len(document["matches"]) == 1


class TestUploadingIntoOneProjectDoesNotReachAnother:
    def test_a_second_project_cannot_see_the_first_ones_drawing(
        self, api_client: TestClient, db_session: Session
    ):
        alfa = make_project(db_session, name="Stazione Alfa", code="ALF")
        beta = make_project(db_session, name="Stazione Beta", code="BET")

        _upload(
            api_client,
            single_page_pdf("Trasformatore TR1 della stazione Alfa"),
            alfa.id,
        )

        assert _search(api_client, alfa.id, "TR1")["total_matches"] == 1
        assert _search(api_client, beta.id, "TR1")["total_matches"] == 0

    def test_a_canonical_library_upload_indexes_nothing_at_all(
        self, api_client: TestClient, db_session: Session
    ):
        """
        A Canonical Library upload runs no lineage, so it is never
        canonicalised and there is nothing for indexing to read.

        This asserts that emptiness directly. It is **not** a test of
        project scoping - it would pass with the project filter deleted,
        because no segment is ever written. Scoping is proved where a
        representation actually exists, in
        ``tests/integration/test_an_engineer_searches_a_project.py``.
        """

        project = make_project(
            db_session, name="Stazione Alfa", code="ALF"
        )

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "norma.pdf",
                    io.BytesIO(single_page_pdf("Trasformatore TR1")),
                    "application/pdf",
                )
            },
            data={"scope": "canonical_library"},
        )

        assert response.status_code == 200

        library_id = response.json()["document"]["id"]

        assert (
            db_session.query(DocumentSearchSegment)
            .filter(DocumentSearchSegment.document_id == library_id)
            .count()
            == 0
        )
        assert _search(api_client, project.id, "TR1")["total_matches"] == 0
