"""
API tests for Canonical Text Segmentation (Milestone 27.1).

They run the whole real chain - upload, ingest, canonicalise, segment -
so what they prove is that the pipeline's stages actually meet, not that
four services each work in isolation.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient

from tests._pdf_builder import multi_page_pdf, single_page_pdf


def _upload(api_client: TestClient, content: bytes) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "montante-T2-schema.pdf",
                io.BytesIO(content),
                "application/pdf",
            )
        },
        data={"scope": "canonical_library"},
    )

    assert response.status_code == 200

    return response.json()


def _canonicalized(api_client: TestClient, content: bytes) -> dict:
    """A document taken all the way to a canonical representation - the
    state segmentation starts from."""

    document = _upload(api_client, content)

    assert (
        api_client.post(
            "/documents/ingestion/jobs", json={"document_id": document["id"]}
        ).status_code
        == 201
    )
    assert (
        api_client.post(
            f"/documents/{document['id']}/canonical-representation"
        ).status_code
        == 201
    )

    return document


def _segment(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(f"/documents/{document_id}/canonical-text")


# --- Segmenting ------------------------------------------------------------


def test_segmenting_a_canonicalised_document_returns_201(
    api_client: TestClient,
) -> None:
    document = _canonicalized(
        api_client, single_page_pdf("Rated voltage 145 kV")
    )

    response = _segment(api_client, document["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["segmentation"]["section_count"] == 1
    assert body["segmentation"]["token_count"] == 4


def test_the_result_reports_which_representation_and_rules_were_used(
    api_client: TestClient,
) -> None:
    document = _canonicalized(api_client, single_page_pdf())

    body = _segment(api_client, document["id"]).json()
    segmentation = body["segmentation"]

    assert segmentation["representation_version"] == "1.0"
    assert segmentation["segmentation_version"] == "1.0"
    assert segmentation["content_checksum"]


def test_a_multi_page_document_segments_into_one_section_per_page(
    api_client: TestClient,
) -> None:
    document = _canonicalized(
        api_client, multi_page_pdf("Bay 21", "Bay 22", "Bay 23")
    )

    body = _segment(api_client, document["id"]).json()

    assert body["segmentation"]["section_count"] == 3


def test_re_segmenting_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    """Nothing was created, so nothing is reported as created."""

    document = _canonicalized(api_client, single_page_pdf())
    _segment(api_client, document["id"])

    response = _segment(api_client, document["id"])

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Reading ----------------------------------------------------------------


def test_the_segmentation_can_be_read_back_in_full(
    api_client: TestClient,
) -> None:
    document = _canonicalized(
        api_client, multi_page_pdf("Bay 21", "Bay 22")
    )
    _segment(api_client, document["id"])

    response = api_client.get(
        f"/documents/{document['id']}/canonical-text"
    )

    assert response.status_code == 200
    body = response.json()
    assert [s["page_number"] for s in body["sections"]] == [1, 2]
    assert body["sections"][0]["paragraphs"][0]["lines"][0]["tokens"]


def test_every_token_exposes_its_provenance_chain(
    api_client: TestClient,
) -> None:
    """The chain a future extractor needs to justify anything it
    concludes: page, block, span, and the characters inside it."""

    document = _canonicalized(
        api_client, single_page_pdf("Rated voltage 145 kV")
    )
    _segment(api_client, document["id"])

    body = api_client.get(
        f"/documents/{document['id']}/canonical-text"
    ).json()
    token = body["sections"][0]["paragraphs"][0]["lines"][0]["tokens"][2]

    assert token["text"] == "145"
    assert token["normalized_text"] == "145"
    assert token["provenance"]["page_number"] == 1
    assert token["provenance"]["block_reading_order"] == 0
    assert token["provenance"]["span_reading_order"] == 0
    assert token["provenance"]["line_index"] == 0
    assert (
        token["provenance"]["character_end"]
        > token["provenance"]["character_start"]
    )


def test_reading_a_segmentation_that_was_never_built_returns_404(
    api_client: TestClient,
) -> None:
    document = _canonicalized(api_client, single_page_pdf())

    response = api_client.get(
        f"/documents/{document['id']}/canonical-text"
    )

    assert response.status_code == 404


# --- Refusals ----------------------------------------------------------------


def test_a_document_with_no_representation_returns_404(
    api_client: TestClient,
) -> None:
    """Segmentation is the step after canonicalisation, and its only
    input is the representation."""

    document = _upload(api_client, single_page_pdf())

    assert _segment(api_client, document["id"]).status_code == 404


def test_an_unknown_document_returns_404(api_client: TestClient) -> None:
    assert _segment(api_client, 4321).status_code == 404


# --- The pipeline holds together -----------------------------------------------


def test_the_full_pipeline_runs_from_upload_to_segmentation(
    api_client: TestClient,
) -> None:
    """upload → ingest → canonicalise → segment, with each stage
    consuming only what the previous one produced."""

    document = _upload(api_client, single_page_pdf("Rated voltage 145 kV"))

    ingestion = api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document["id"]}
    )
    canonicalisation = api_client.post(
        f"/documents/{document['id']}/canonical-representation"
    )
    segmentation = _segment(api_client, document["id"])

    assert ingestion.json()["ready_for_extraction"] is True
    assert canonicalisation.json()["succeeded"] is True
    assert segmentation.json()["succeeded"] is True

    text = api_client.get(
        f"/documents/{document['id']}/canonical-text"
    ).json()
    tokens = [
        token["text"]
        for section in text["sections"]
        for paragraph in section["paragraphs"]
        for line in paragraph["lines"]
        for token in line["tokens"]
    ]

    assert tokens == ["Rated", "voltage", "145", "kV"]


def test_the_canonical_representation_is_still_readable_afterwards(
    api_client: TestClient,
) -> None:
    """Segmenting derives a new artefact; it does not consume or replace
    the one it derived from."""

    document = _canonicalized(api_client, single_page_pdf())
    _segment(api_client, document["id"])

    response = api_client.get(
        f"/documents/{document['id']}/canonical-representation"
    )

    assert response.status_code == 200
    assert response.json()["page_count"] == 1
