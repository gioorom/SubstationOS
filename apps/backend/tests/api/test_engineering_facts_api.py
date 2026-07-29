"""
API tests for Engineering Fact Construction (Milestone 29.2).

They run the whole real chain - upload, ingest, canonicalise, segment,
extract, resolve, construct - so what they prove is that the pipeline's
stages actually meet.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests._pdf_builder import build_pdf

DATA_SHEET = build_pdf(
    [
        [
            ("Trasformatore TR1 630 kVA", (72.0, 100.0), 11.0),
            ("Interruttore 52-Q1 1250 A", (72.0, 130.0), 11.0),
            ("TR2 TR3 20 kV", (72.0, 160.0), 11.0),
        ]
    ]
)

NOTHING_ASSOCIABLE = build_pdf(
    [[("Trasformatore TR1 in cabina primaria", (72.0, 100.0), 11.0)]]
)


def _prepared(api_client: TestClient, content: bytes) -> int:
    """A document taken to resolved entities - the state construction
    starts from."""

    document = api_client.post(
        "/documents/upload",
        files={"file": ("schema.pdf", io.BytesIO(content), "application/pdf")},
        data={"scope": "canonical_library"},
    ).json()["document"]
    document_id = document["id"]

    assert (
        api_client.post(
            "/documents/ingestion/jobs", json={"document_id": document_id}
        ).status_code
        == 201
    )

    for path in (
        f"/documents/{document_id}/canonical-representation",
        f"/documents/{document_id}/canonical-text",
        f"/documents/{document_id}/engineering-evidence",
        f"/documents/{document_id}/engineering-entities",
    ):
        assert api_client.post(path).status_code == 201, path

    return document_id


def _construct(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(f"/documents/{document_id}/engineering-facts")


# --- Construction completed ---------------------------------------------------------


def test_constructing_facts_returns_201(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)

    response = _construct(api_client, document_id)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["found_facts"] is True


def test_the_result_distinguishes_ambiguity_from_failure(
    api_client: TestClient,
) -> None:
    """``TR2 TR3 20 kV`` was declined. The construction still succeeded -
    the rules working is not a system failure."""

    document_id = _prepared(api_client, DATA_SHEET)

    body = _construct(api_client, document_id).json()

    assert body["succeeded"] is True
    assert body["has_ambiguities"] is True
    assert body["failure"] is None
    assert body["fact_set"]["fact_count"] == 2


def test_a_document_with_nothing_associable_completes_without_facts(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, NOTHING_ASSOCIABLE)

    body = _construct(api_client, document_id).json()

    assert body["succeeded"] is True
    assert body["found_facts"] is False
    assert body["has_ambiguities"] is False


def test_re_constructing_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    response = _construct(api_client, document_id)

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Inspecting the set ----------------------------------------------------------------


def test_the_fact_set_can_be_read_back(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    response = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["facts"]) == 2
    assert len(body["diagnostics"]) == 1


def test_every_fact_uses_the_narrow_predicate(
    api_client: TestClient,
) -> None:
    """A power and a current produce the same predicate - the quantity's
    kind is not promoted into a semantic property."""

    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()

    assert {fact["predicate"] for fact in body["facts"]} == {
        "has_associated_quantity"
    }
    for fact in body["facts"]:
        assert "rated_power" not in fact
        assert "role" not in fact
        assert "property_name" not in fact


def test_the_supported_evidence_types_differ_while_the_predicate_does_not(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()
    types = {
        reference["evidence_type"]
        for fact in body["facts"]
        for reference in fact["support"]
        if reference["role"] == "object"
    }

    assert types == {"power_value", "current_value"}


def test_the_diagnostic_names_no_subject_or_object(
    api_client: TestClient,
) -> None:
    """An ambiguous line must not be readable as a confirmed
    association."""

    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()
    diagnostic = body["diagnostics"][0]

    assert diagnostic["reason"] == "multiple_subjects"
    assert len(diagnostic["subject_entity_keys"]) == 2
    assert "subject_entity_key" not in diagnostic
    assert "predicate" not in diagnostic
    assert "status" not in diagnostic


# --- Inspecting one fact and its support --------------------------------------------------


def test_one_fact_can_be_read_by_key(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    fact_key = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()["facts"][0]["fact_key"]

    response = api_client.get(
        f"/documents/{document_id}/engineering-facts/{fact_key}"
    )

    assert response.status_code == 200
    assert response.json()["fact_key"] == fact_key


def test_a_fact_enumerates_the_observations_supporting_it(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    fact_key = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()["facts"][0]["fact_key"]

    response = api_client.get(
        f"/documents/{document_id}/engineering-facts/{fact_key}/support"
    )

    assert response.status_code == 200
    support = response.json()
    assert {reference["role"] for reference in support} == {
        "subject",
        "object",
    }
    # A same-line association: every supporting observation is on one line.
    assert len({reference["line_index"] for reference in support}) == 1


def test_support_resolves_against_the_evidence_endpoint(
    api_client: TestClient,
) -> None:
    """The chain from fact to characters is unbroken: the support names
    an evidence key, and the evidence carries the provenance."""

    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    fact = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()["facts"][0]
    evidence = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()
    keys = {item["evidence_key"] for item in evidence["evidence"]}

    assert {
        reference["evidence_key"] for reference in fact["support"]
    } <= keys


def test_the_subject_and_object_resolve_against_the_entity_endpoint(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    fact = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()["facts"][0]
    entities = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()["entities"]
    keys = {entity["entity_key"] for entity in entities}

    assert fact["subject_entity_key"] in keys
    assert fact["object_entity_key"] in keys


def test_an_unknown_fact_returns_404(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-facts/nope"
        ).status_code
        == 404
    )


# --- Refusals -------------------------------------------------------------------------------


def test_a_document_without_entities_returns_404(
    api_client: TestClient,
) -> None:
    document = api_client.post(
        "/documents/upload",
        files={
            "file": ("schema.pdf", io.BytesIO(DATA_SHEET), "application/pdf")
        },
        data={"scope": "canonical_library"},
    ).json()["document"]

    assert _construct(api_client, document["id"]).status_code == 404


def test_reading_facts_that_were_never_constructed_returns_404(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-facts"
        ).status_code
        == 404
    )


# --- No graph is written -----------------------------------------------------------------------


def test_construction_writes_no_graph_node_or_edge(
    api_client: TestClient, db_session: Session
) -> None:
    from app.models.knowledge_graph import EntityRelation, ProjectEntity

    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    assert db_session.query(ProjectEntity).count() == 0
    assert db_session.query(EntityRelation).count() == 0


def test_no_orm_model_is_exposed(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _construct(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-facts"
    ).json()

    assert "id" not in body
    assert "created_at" not in body
    for fact in body["facts"]:
        assert "id" not in fact
        assert "fact_set_id" not in fact
