"""
API tests for Engineering Entity Resolution (Milestone 29.1).

They run the whole real chain - upload, ingest, canonicalise, segment,
extract, resolve - so what they prove is that the pipeline's stages
actually meet.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests._pdf_builder import build_pdf

SUBSTATION_PAGE = build_pdf(
    [
        [
            ("Trasformatore T1 - potenza 630 kVA", (72.0, 100.0), 11.0),
            ("Il trasformatore (T1) alimenta", (72.0, 130.0), 11.0),
            ("Interruttore 52-Q1, tensione 20 kV", (72.0, 160.0), 11.0),
        ]
    ]
)

NO_ENTITY_PAGE = build_pdf(
    [[("Il presente documento descrive la fornitura.", (72.0, 100.0), 11.0)]]
)


def _prepared(api_client: TestClient, content: bytes) -> int:
    """A document taken to engineering evidence - the state resolution
    starts from."""

    document = api_client.post(
        "/documents/upload",
        files={"file": ("schema.pdf", io.BytesIO(content), "application/pdf")},
        data={"scope": "canonical_library"},
    ).json()["document"]
    document_id = document["id"]

    for path in (
        "/documents/ingestion/jobs",
        f"/documents/{document_id}/canonical-representation",
        f"/documents/{document_id}/canonical-text",
        f"/documents/{document_id}/engineering-evidence",
    ):
        response = (
            api_client.post(path, json={"document_id": document_id})
            if path.endswith("jobs")
            else api_client.post(path)
        )

        assert response.status_code == 201, path

    return document_id


def _resolve(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(
        f"/documents/{document_id}/engineering-entities"
    )


# --- Resolution completed ---------------------------------------------------------


def test_resolving_entities_returns_201(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    response = _resolve(api_client, document_id)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["found_entities"] is True
    assert body["entity_set"]["entity_count"] > 0


def test_the_result_reports_the_source_and_the_policies(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    entity_set = _resolve(api_client, document_id).json()["entity_set"]

    assert entity_set["extraction_policy_version"] == "1.0"
    assert entity_set["resolution_policy_version"] == "1.0"
    assert entity_set["content_checksum"]


def test_a_document_with_nothing_groupable_completes_without_entities(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, NO_ENTITY_PAGE)

    response = _resolve(api_client, document_id)

    assert response.status_code == 201
    assert response.json()["found_entities"] is False
    assert response.json()["failure"] is None


def test_re_resolving_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    response = _resolve(api_client, document_id)

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Inspecting the set --------------------------------------------------------------


def test_the_entity_set_can_be_read_back(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    response = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    )

    assert response.status_code == 200
    body = response.json()
    assert {entity["label"] for entity in body["entities"]} == {
        "T1",
        "52-Q1",
        "630 kVA",
        "20 kV",
    }


def test_repeated_designations_appear_as_one_entity(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()
    t1 = next(
        entity for entity in body["entities"] if entity["label"] == "T1"
    )

    assert t1["entity_type"] == "equipment_designation"
    assert t1["evidence_count"] == 2
    assert t1["designation"]["normalized"] == "T1"
    assert t1["quantity"] is None


def test_a_quantity_entity_carries_an_exact_decimal(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()
    power = next(
        entity
        for entity in body["entities"]
        if entity["label"] == "630 kVA"
    )

    assert power["quantity"]["value"] == "630"
    assert power["quantity"]["unit"] == "kVA"
    assert power["quantity"]["base_value"] == "630000"
    assert power["designation"] is None


def test_an_entity_exposes_the_rule_that_produced_it(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()

    for entity in body["entities"]:
        assert entity["resolution_rule_id"] in (
            "designation_grouping",
            "quantity_identity",
        )
        assert entity["resolution_rule_version"] == "1.0"
        assert entity["entity_version"] == "1.0"


# --- Inspecting one entity and its evidence ---------------------------------------------


def test_one_entity_can_be_read_by_key(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    entity_key = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()["entities"][0]["entity_key"]

    response = api_client.get(
        f"/documents/{document_id}/engineering-entities/{entity_key}"
    )

    assert response.status_code == 200
    assert response.json()["entity_key"] == entity_key


def test_an_entity_lists_the_evidence_that_created_it(
    api_client: TestClient,
) -> None:
    """Every entity must be able to enumerate the observations behind
    it - that is what makes a hypothesis auditable."""

    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    entities = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()["entities"]
    t1 = next(entity for entity in entities if entity["label"] == "T1")

    response = api_client.get(
        f"/documents/{document_id}/engineering-entities/"
        f"{t1['entity_key']}/evidence"
    )

    assert response.status_code == 200
    references = response.json()
    assert len(references) == 2
    assert {reference["observed_text"] for reference in references} == {"T1"}
    # The two observations sit in different paragraphs - the parser makes
    # each text insertion its own block - which is also the proof that
    # grouping spans a whole document rather than one paragraph.
    assert {
        reference["paragraph_index"] for reference in references
    } == {0, 1}


def test_a_contributing_reference_points_at_a_real_evidence_item(
    api_client: TestClient,
) -> None:
    """The evidence key resolves against the evidence endpoint - the
    chain from entity to characters is unbroken."""

    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    entities = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()["entities"]
    reference = entities[0]["evidence"][0]

    evidence = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()
    keys = {item["evidence_key"] for item in evidence["evidence"]}

    assert reference["evidence_key"] in keys


def test_an_unknown_entity_returns_404(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-entities/nope"
        ).status_code
        == 404
    )


# --- Refusals ------------------------------------------------------------------------


def test_a_document_without_evidence_returns_404(
    api_client: TestClient,
) -> None:
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

    assert _resolve(api_client, document["id"]).status_code == 404


def test_reading_entities_that_were_never_resolved_returns_404(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-entities"
        ).status_code
        == 404
    )


# --- No graph is written ----------------------------------------------------------------


def test_resolution_writes_no_graph_node(
    api_client: TestClient, db_session: Session
) -> None:
    # Repointed by EPIC 31.1. This used to query `ProjectEntity`, the
    # ungoverned table that milestone dropped; it now asserts the
    # stronger property against the graph that replaced it - resolving
    # entities writes **no** governed knowledge, because knowledge
    # enters the graph only through an explicit promotion of a statement
    # an engineer approved.
    from app.models.governed_knowledge_graph import (
        GovernedGraphEdgeRecord,
        GovernedGraphNodeRecord,
    )

    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0


def test_no_orm_model_is_exposed(api_client: TestClient) -> None:
    document_id = _prepared(api_client, SUBSTATION_PAGE)
    _resolve(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()

    assert "id" not in body
    assert "created_at" not in body
    for entity in body["entities"]:
        assert "id" not in entity
        assert "entity_set_id" not in entity
