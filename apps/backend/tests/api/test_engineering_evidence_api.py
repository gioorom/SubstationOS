"""
API tests for Engineering Evidence Extraction (Milestone 28.1).

They run the whole real chain - upload, ingest, canonicalise, segment,
extract - so what they prove is that the pipeline's stages actually meet,
and that the four outcomes a client must tell apart are distinguishable.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient

from tests._pdf_builder import build_pdf

SUBSTATION_PAGE = build_pdf(
    [
        [
            ("Trasformatore T1 20 kV / 400 V", (72.0, 100.0), 11.0),
            ("Potenza 630 kVA, corrente 1250 A", (72.0, 130.0), 11.0),
            ("Cavo 240 mm² - interruttore 52-Q1", (72.0, 160.0), 11.0),
        ]
    ]
)

NO_EVIDENCE_PAGE = build_pdf(
    [[("Il presente documento descrive la fornitura.", (72.0, 100.0), 11.0)]]
)


def _prepared(api_client: TestClient, content: bytes) -> int:
    """A document taken to canonical text - the state extraction starts
    from."""

    document = api_client.post(
        "/documents/upload",
        files={"file": ("schema.pdf", io.BytesIO(content), "application/pdf")},
        data={"scope": "canonical_library"},
    ).json()["document"]

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
    assert (
        api_client.post(
            f"/documents/{document['id']}/canonical-text"
        ).status_code
        == 201
    )

    return document["id"]


def _extract(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(
        f"/documents/{document_id}/engineering-evidence"
    )


# --- Extraction completed ------------------------------------------------------


def test_extracting_evidence_returns_201(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    response = _extract(api_client, document_id)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["found_evidence"] is True
    assert body["evidence_set"]["evidence_count"] > 0


def test_the_result_reports_the_source_and_the_policy(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    evidence_set = _extract(api_client, document_id).json()["evidence_set"]

    assert evidence_set["segmentation_version"] == "1.0"
    assert evidence_set["extraction_policy_version"] == "1.0"
    assert evidence_set["content_checksum"]


# --- No supported evidence found ------------------------------------------------


def test_a_document_with_nothing_recognisable_completes_without_evidence(
    api_client: TestClient,
) -> None:
    """Distinguishable from a failure: the extraction ran and observed
    nothing, which is a fact about the document."""

    document_id = _prepared(api_client, NO_EVIDENCE_PAGE)

    response = _extract(api_client, document_id)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["found_evidence"] is False
    assert body["failure"] is None


# --- An existing set was reused ---------------------------------------------------


def test_re_extracting_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    response = _extract(api_client, document_id)

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Extraction failed ------------------------------------------------------------


def test_a_document_without_canonical_text_returns_404(
    api_client: TestClient,
) -> None:
    """Extraction is the step after segmentation, and canonical text is
    its only input."""

    document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema.pdf",
                io.BytesIO(SUBSTATION_PAGE),
                "application/pdf",
            )
        },
        data={"scope": "canonical_library"},
    ).json()["document"]

    assert _extract(api_client, document["id"]).status_code == 404


def test_an_unknown_document_returns_404(api_client: TestClient) -> None:
    assert _extract(api_client, 4321).status_code == 404


# --- Reading evidence with provenance ----------------------------------------------


def test_the_evidence_can_be_read_back_with_full_provenance(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    response = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    )

    assert response.status_code == 200
    body = response.json()
    item = body["evidence"][0]

    assert item["rule_id"]
    assert item["rule_version"] == "1.0"
    assert item["provenance"]["page_number"] == 1
    assert item["provenance"]["spans"]
    assert (
        item["provenance"]["token_end"]
        > item["provenance"]["token_start"]
    )


def test_quantities_are_exposed_as_exact_decimals(
    api_client: TestClient,
) -> None:
    """Serialised as strings, not floats - a rated voltage must not
    acquire a rounding error on its way to a client."""

    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()
    voltages = [
        item
        for item in body["evidence"]
        if item["evidence_type"] == "voltage_value"
    ]

    assert voltages
    assert voltages[0]["quantity"]["value"] == "20"
    assert voltages[0]["quantity"]["unit"] == "kV"
    assert voltages[0]["quantity"]["base_value"] == "20000"


def test_designations_are_exposed_without_an_equipment_type(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()
    designations = [
        item
        for item in body["evidence"]
        if item["evidence_type"] == "designation"
    ]

    assert {item["designation"]["normalized"] for item in designations} == {
        "T1",
        "52-Q1",
    }
    for item in designations:
        assert set(item) == {
            "evidence_key",
            "evidence_type",
            "status",
            "observed_text",
            "rule_id",
            "rule_version",
            "quantity",
            "designation",
            "provenance",
        }


def test_engineering_symbols_survive_to_the_api(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()
    sections = [
        item["observed_text"]
        for item in body["evidence"]
        if item["evidence_type"] == "cable_section_value"
    ]

    assert sections == ["240 mm²"]


def test_reading_evidence_that_was_never_extracted_returns_404(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    response = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    )

    assert response.status_code == 404


def test_no_orm_model_is_exposed(api_client: TestClient) -> None:
    """The response carries the domain's shape, not the schema's - no
    row id, no foreign key, no timestamp."""

    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _extract(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()

    assert "id" not in body
    assert "created_at" not in body
    for item in body["evidence"]:
        assert "id" not in item
        assert "evidence_set_id" not in item


# --- The pipeline holds together ----------------------------------------------------


def test_the_full_pipeline_runs_from_upload_to_evidence(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    evidence = _extract(api_client, document_id).json()
    canonical_text = api_client.get(
        f"/documents/{document_id}/canonical-text"
    )

    assert evidence["succeeded"] is True
    # Extracting did not consume or replace what it read from.
    assert canonical_text.status_code == 200
    assert canonical_text.json()["token_count"] > 0
