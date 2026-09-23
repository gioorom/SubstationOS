"""
The Friday delivery, exercised end to end as an engineer would.

Two projects are created over the API, four real files are uploaded
through the real endpoint, the real pipeline canonicalises them and the
real index makes them findable. Nothing here is hand-built: if a stage
does not actually meet the next one, these tests fail.

The corpus is invented. Every designation, rating and sheet name below
was written for this test file and corresponds to no real installation,
customer or drawing.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models.document_search import DocumentSearchSegment
from tests._pdf_builder import multi_page_pdf

#: What a browser sends for a `.xlsx`.
XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _cable_list() -> bytes:
    """A cable schedule, as a real ``.xlsx``."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Elenco Cavi"

    for row in (
        ("Sigla", "Partenza", "Arrivo", "Tensione kV", "Sezione mm2"),
        ("-W1", "TR1", "Q01", 150, 240),
        ("-W2", "TR2", "-Q1", 150, 185),
        ("-W3", "Quadro MT", "MORSETTIERA E1", 20, 95),
    ):
        sheet.append(list(row))

    buffer = io.BytesIO()
    workbook.save(buffer)

    return buffer.getvalue()


def _upload(
    client: TestClient,
    *,
    project_id: int,
    filename: str,
    content: bytes,
    media_type: str = "application/pdf",
) -> dict:
    response = client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), media_type)},
        data={"scope": "project", "project_id": str(project_id)},
    )

    assert response.status_code == 200, response.text

    return response.json()


def _create_project(client: TestClient, *, name: str, code: str) -> dict:
    response = client.post(
        "/projects/",
        json={
            "name": name,
            "code": code,
            "customer": "Cliente di prova",
            "status": "planning",
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def _only(body: dict, *, source_type: str) -> dict:
    """
    The one result of this source family.

    Results are picked by family rather than by position, because a
    designation legitimately appears in more than one document -
    ``-Q1`` is in the drawing *and* in the cable list - and which one
    sorts first is an ordering detail, not something a reader relies
    on.
    """

    matching = [
        document
        for document in body["documents"]
        if document["source_type"] == source_type
    ]

    assert matching, f"no {source_type} result in {body['documents']}"

    return matching[0]


def _search(
    client: TestClient, project_id: int, query: str, **params
) -> dict:
    response = client.get(
        f"/projects/{project_id}/search", params={"q": query, **params}
    )

    assert response.status_code == 200, response.text

    return response.json()


@pytest.fixture()
def release(api_client: TestClient):
    """
    Project A with three documents, Project B with one unrelated
    document. Everything created the way a user creates it.
    """

    alfa = _create_project(
        api_client, name="Stazione Alfa", code="REL-ALFA"
    )
    beta = _create_project(
        api_client, name="Stazione Beta", code="REL-BETA"
    )

    functional = _upload(
        api_client,
        project_id=alfa["id"],
        filename="specifica_funzionale.pdf",
        content=multi_page_pdf(
            "SPECIFICA FUNZIONALE - STAZIONE DI PROVA",
            "Il trasformatore TR1 alimenta il quadro MT",
            "Protezione differenziale M1 su TR1",
        ),
    )

    cables = _upload(
        api_client,
        project_id=alfa["id"],
        filename="elenco_cavi.xlsx",
        content=_cable_list(),
        media_type=XLSX_MEDIA_TYPE,
    )

    drawing = _upload(
        api_client,
        project_id=alfa["id"],
        filename="schema_unifilare.pdf",
        content=multi_page_pdf(
            "SCHEMA UNIFILARE - Disegno 189L",
            "Sezionatore -Q1 lato alta tensione",
            "Trasformatore TR1 150/20 kV - Quadro MT +189L",
        ),
    )

    unrelated = _upload(
        api_client,
        project_id=beta["id"],
        filename="relazione_beta.pdf",
        content=multi_page_pdf(
            "RELAZIONE TECNICA - STAZIONE BETA",
            "Il trasformatore TR9 della stazione Beta",
        ),
    )

    return {
        "alfa": alfa,
        "beta": beta,
        "functional": functional["document"],
        "cables": cables["document"],
        "drawing": drawing["document"],
        "unrelated": unrelated["document"],
    }


# --- A. Project creation -------------------------------------------------


class TestAProjectCanBeCreatedAndOpened:
    def test_a_created_project_can_be_opened_again(
        self, api_client: TestClient, release
    ):
        response = api_client.get(f"/projects/{release['alfa']['id']}")

        assert response.status_code == 200
        assert response.json()["code"] == "REL-ALFA"


# --- B. Document upload --------------------------------------------------


class TestDocumentsCanBeUploaded:
    def test_every_document_is_filed_under_its_project(
        self, api_client: TestClient, release
    ):
        response = api_client.get(
            "/documents/", params={"project_id": release["alfa"]["id"]}
        )

        assert response.status_code == 200

        filenames = {
            item["filename"] for item in response.json()["items"]
        }

        assert filenames == {
            "specifica_funzionale.pdf",
            "elenco_cavi.xlsx",
            "schema_unifilare.pdf",
        }

    def test_both_supported_formats_are_recognised(self, release):
        assert release["functional"]["file_format"] == "pdf"
        assert release["cables"]["file_format"] == "xlsx"


# --- C. Processing -------------------------------------------------------


class TestDocumentsReachASearchableState:
    @pytest.mark.parametrize(
        "key", ["functional", "cables", "drawing", "unrelated"]
    )
    def test_each_uploaded_document_is_indexed(
        self, db_session: Session, release, key: str
    ):
        indexed = (
            db_session.query(DocumentSearchSegment)
            .filter(
                DocumentSearchSegment.document_id == release[key]["id"]
            )
            .count()
        )

        assert indexed > 0, key

    def test_a_real_workbook_becomes_searchable_through_upload_alone(
        self, api_client: TestClient, release
    ):
        """
        The spreadsheet lineage runs on upload and the index reads what
        it produced - no hand-built canonical rows anywhere in this
        path.
        """

        body = _search(api_client, release["alfa"]["id"], "-W2")

        assert body["total_matches"] >= 1
        assert (
            _only(body, source_type="spreadsheet")["filename"]
            == "elenco_cavi.xlsx"
        )


# --- D. Search -----------------------------------------------------------


class TestSearchReturnsMatchingEvidence:
    @pytest.mark.parametrize(
        "query", ["TR1", "-Q1", "+189L", "M1", "trasformatore", "quadro MT"]
    )
    def test_the_corpus_answers_the_queries_an_engineer_asks(
        self, api_client: TestClient, release, query: str
    ):
        body = _search(api_client, release["alfa"]["id"], query)

        assert body["total_matches"] > 0, query

    def test_a_result_carries_the_text_that_matched(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-Q1")
        snippet = body["documents"][0]["matches"][0]["snippet"]

        assert "-Q1" in snippet["text"]
        assert snippet["highlights"]

    def test_a_search_spans_every_document_of_the_project(
        self, api_client: TestClient, release
    ):
        """``TR1`` appears in the specification, the drawing and the
        cable list."""

        body = _search(api_client, release["alfa"]["id"], "TR1")

        assert body["total_documents"] == 3


# --- E. Project isolation ------------------------------------------------


class TestProjectIsolation:
    def test_project_a_never_returns_project_b_content(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "TR9")

        assert body["total_matches"] == 0

    def test_project_b_never_returns_project_a_content(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["beta"]["id"], "-Q1")

        assert body["total_matches"] == 0

    def test_project_b_answers_only_for_its_own_document(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["beta"]["id"], "TR9")

        assert body["total_matches"] > 0
        assert body["documents"][0]["filename"] == "relazione_beta.pdf"

    def test_no_result_names_a_document_of_another_project(
        self, api_client: TestClient, release
    ):
        foreign = {
            release["unrelated"]["id"],
        }

        for query in ("TR1", "trasformatore", "-Q1", "150"):
            body = _search(api_client, release["alfa"]["id"], query)

            for document in body["documents"]:
                assert document["document_id"] not in foreign


# --- F. Provenance -------------------------------------------------------


class TestEveryResultIdentifiesItsSource:
    def test_a_result_names_the_document_and_the_version_read(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "TR1")

        for document in body["documents"]:
            assert document["document_id"]
            assert document["filename"]
            assert document["source_type"] in {"pdf", "spreadsheet"}
            assert document["content_checksum"]

    def test_the_checksum_is_the_uploaded_documents_own(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-Q1")
        result = _only(body, source_type="pdf")

        assert (
            result["content_checksum"]
            == release["drawing"]["content_checksum"]
        )


# --- G. Location ---------------------------------------------------------


class TestLocationIsShownWhereAvailable:
    def test_a_pdf_result_names_its_page(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-Q1")
        location = _only(body, source_type="pdf")["matches"][0]["location"]

        assert location["determined"] is True
        assert location["page_number"] == 2

    def test_a_workbook_result_names_its_sheet_and_cell(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-W3")
        location = _only(body, source_type="spreadsheet")["matches"][0][
            "location"
        ]

        assert location["determined"] is True
        assert location["worksheet_name"] == "Elenco Cavi"
        assert location["row_number"] == 4
        assert location["cell_reference"] == "A4"

    def test_every_location_is_either_determined_or_says_it_is_not(
        self, api_client: TestClient, release
    ):
        for query in ("TR1", "-Q1", "MORSETTIERA", "150"):
            body = _search(api_client, release["alfa"]["id"], query)

            for document in body["documents"]:
                for match in document["matches"]:
                    location = match["location"]

                    if location["determined"]:
                        assert (
                            location["page_number"] is not None
                            or location["worksheet_name"] is not None
                        )
                    else:
                        assert location["page_number"] is None
                        assert location["cell_reference"] is None


# --- Inspecting the source (scope item 9) --------------------------------


class TestTheSourceCanBeOpened:
    def test_a_result_leads_to_a_document_that_can_be_read(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-Q1")
        document_id = _only(body, source_type="pdf")["document_id"]

        detail = api_client.get(f"/documents/{document_id}")

        assert detail.status_code == 200
        assert detail.json()["filename"] == "schema_unifilare.pdf"

    def test_the_source_bytes_can_be_retrieved(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "-Q1")
        document_id = _only(body, source_type="pdf")["document_id"]

        content = api_client.get(f"/documents/{document_id}/content")

        assert content.status_code == 200
        assert content.content.startswith(b"%PDF")


# --- H. No result --------------------------------------------------------


class TestAnUnsupportedQuestionIsNotAnswered:
    @pytest.mark.parametrize(
        "query",
        [
            "TR99",
            "interruttore SF6 630A",
            "coordinate GPS",
            "resistenza di terra 0.5 ohm",
        ],
    )
    def test_the_corpus_does_not_invent_what_it_does_not_contain(
        self, api_client: TestClient, release, query: str
    ):
        body = _search(api_client, release["alfa"]["id"], query)

        assert body["total_matches"] == 0, query
        assert body["documents"] == [], query

    def test_an_empty_result_still_reports_what_was_searched(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "TR99")

        assert body["terms"] == ["tr99"]

    def test_a_near_miss_is_offered_rather_than_applied(
        self, api_client: TestClient, release
    ):
        body = _search(api_client, release["alfa"]["id"], "Q1")

        assert body["documents"] == []
        assert body["suggestions"] == [
            {"term": "q1", "present_variants": ["-q1"]}
        ]


# --- I. Document identity (ADR-0036) -------------------------------------


class TestIdenticalContentStaysTwoDocuments:
    def test_the_same_bytes_uploaded_twice_are_two_records(
        self, api_client: TestClient, release
    ):
        """
        ADR-0036: content identity identifies a *version*, not a
        document. Two uploads of the same bytes are two filings.
        """

        content = multi_page_pdf("Documento ripetuto TR5")

        first = _upload(
            api_client,
            project_id=release["alfa"]["id"],
            filename="ripetuto.pdf",
            content=content,
        )["document"]
        second = _upload(
            api_client,
            project_id=release["alfa"]["id"],
            filename="ripetuto.pdf",
            content=content,
        )["document"]

        assert first["id"] != second["id"]
        assert first["content_checksum"] == second["content_checksum"]

    def test_both_records_answer_a_search_independently(
        self, api_client: TestClient, release
    ):
        content = multi_page_pdf("Documento ripetuto TR5")

        _upload(
            api_client,
            project_id=release["alfa"]["id"],
            filename="ripetuto.pdf",
            content=content,
        )
        _upload(
            api_client,
            project_id=release["alfa"]["id"],
            filename="ripetuto.pdf",
            content=content,
        )

        body = _search(api_client, release["alfa"]["id"], "TR5")

        assert body["total_documents"] == 2

        for document in body["documents"]:
            assert len(document["matches"]) == 1


# --- J. Retention --------------------------------------------------------


class TestLifecycleCannotSilentlyDestroyADocument:
    def test_archiving_a_project_keeps_its_documents_and_their_identity(
        self, api_client: TestClient, release
    ):
        project_id = release["alfa"]["id"]

        assert (
            api_client.post(f"/projects/{project_id}/activate").status_code
            == 200
        )
        assert (
            api_client.post(f"/projects/{project_id}/archive").status_code
            == 200
        )

        detail = api_client.get(f"/documents/{release['drawing']['id']}")

        assert detail.status_code == 200
        assert (
            detail.json()["content_checksum"]
            == release["drawing"]["content_checksum"]
        )

    def test_a_soft_deleted_project_still_has_its_documents(
        self, api_client: TestClient, release
    ):
        project_id = release["alfa"]["id"]

        api_client.post(f"/projects/{project_id}/activate")
        api_client.post(f"/projects/{project_id}/archive")

        assert (
            api_client.delete(f"/projects/{project_id}").status_code == 200
        )

        detail = api_client.get(f"/documents/{release['drawing']['id']}")

        assert detail.status_code == 200
        assert detail.json()["content_checksum"]


# --- M. Error handling ---------------------------------------------------


class TestFailuresAreSurfacedCleanly:
    def test_uploading_to_a_project_that_does_not_exist_is_refused(
        self, api_client: TestClient, release
    ):
        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "x.pdf",
                    io.BytesIO(multi_page_pdf("x")),
                    "application/pdf",
                )
            },
            data={"scope": "project", "project_id": "999999"},
        )

        assert response.status_code in (404, 422)
        assert response.json()["detail"]

    def test_a_project_scoped_upload_without_a_project_is_refused(
        self, api_client: TestClient, release
    ):
        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "x.pdf",
                    io.BytesIO(multi_page_pdf("x")),
                    "application/pdf",
                )
            },
            data={"scope": "project"},
        )

        assert response.status_code == 422
        assert response.json()["detail"]

    def test_an_unreadable_document_does_not_lose_the_upload(
        self, api_client: TestClient, release
    ):
        """
        A pipeline that cannot read a file must still leave the file
        stored and recorded - losing it would be the worst trade.
        """

        response = api_client.post(
            "/documents/upload",
            files={
                "file": (
                    "rotto.pdf",
                    io.BytesIO(b"%PDF-1.4 not really a pdf"),
                    "application/pdf",
                )
            },
            data={
                "scope": "project",
                "project_id": str(release["alfa"]["id"]),
            },
        )

        assert response.status_code == 200
        assert response.json()["document"]["id"]

    def test_searching_a_project_that_does_not_exist_is_refused(
        self, api_client: TestClient, release
    ):
        response = api_client.get(
            "/projects/999999/search", params={"q": "TR1"}
        )

        assert response.status_code == 404
        assert response.json()["detail"]


# --- N. Security boundary ------------------------------------------------


class TestTheSearchBoundary:
    def test_an_anonymous_caller_cannot_search_any_project(
        self, anonymous_client: TestClient, release
    ):
        for project in (release["alfa"], release["beta"]):
            response = anonymous_client.get(
                f"/projects/{project['id']}/search", params={"q": "TR1"}
            )

            assert response.status_code in (401, 403)

    def test_changing_the_project_id_changes_which_corpus_is_searched(
        self, api_client: TestClient, release
    ):
        """
        The scope of a search is the project in the URL and nothing
        else: substituting another project's id searches *that*
        project, and never merges the two.

        This documents the boundary that exists. It is **not** a claim
        that one authenticated user is kept out of another's project -
        this platform has no per-project membership, and every document
        read endpoint is equally open (see ADR-0038 §5).
        """

        alfa = _search(api_client, release["alfa"]["id"], "TR1")
        beta = _search(api_client, release["beta"]["id"], "TR1")

        assert alfa["total_matches"] > 0
        assert beta["total_matches"] == 0

        alfa_ids = {d["document_id"] for d in alfa["documents"]}

        assert release["unrelated"]["id"] not in alfa_ids
