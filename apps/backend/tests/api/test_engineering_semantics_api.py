"""
API tests for Engineering Semantic Interpretation (Milestone 30.1).

They run the whole real chain - upload, ingest, canonicalise, segment,
extract, resolve, construct, interpret - so what they prove is that eight
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
            ("Trasformatore TR2 20 kV", (72.0, 130.0), 11.0),
            ("Trasformatore TR3 400 kVA 500 kVA", (72.0, 160.0), 11.0),
        ]
    ]
)

NO_MEANING = build_pdf(
    [[("Trasformatore TR1 20 kV nominale", (72.0, 100.0), 11.0)]]
)


def _prepared(api_client: TestClient, content: bytes) -> int:
    """A document taken to constructed facts - the state interpretation
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
        f"/documents/{document_id}/engineering-facts",
    ):
        assert api_client.post(path).status_code == 201, path

    return document_id


def _interpret(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(
        f"/documents/{document_id}/engineering-semantics"
    )


# --- Interpretation completed --------------------------------------------------------


def test_interpreting_facts_returns_201(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)

    response = _interpret(api_client, document_id)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["found_semantics"] is True


def test_the_result_distinguishes_ambiguity_from_failure(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)

    body = _interpret(api_client, document_id).json()

    assert body["succeeded"] is True
    assert body["has_ambiguities"] is True
    assert body["failure"] is None
    assert body["semantic_set"]["statement_count"] == 1


def test_a_document_with_no_declared_meaning_completes_empty(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, NO_MEANING)

    body = _interpret(api_client, document_id).json()

    assert body["succeeded"] is True
    assert body["found_semantics"] is False
    assert body["failure"] is None


def test_re_interpreting_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    response = _interpret(api_client, document_id)

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Inspecting the set -----------------------------------------------------------------


def test_the_semantic_set_can_be_read_back(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    response = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["statements"]) == 1
    assert len(body["diagnostics"]) == 1
    assert body["statements"][0]["statement_type"] == "has_rated_power"


def test_a_statement_exposes_the_rule_that_produced_it(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    statement = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"][0]

    assert statement["semantic_rule_id"] == (
        "rated_power_from_associated_power_quantity"
    )
    assert statement["semantic_rule_version"] == "1.0"
    assert statement["semantic_contract_version"] == "1.0"
    assert statement["status"] == "interpreted"


def test_a_statement_exposes_no_value_or_unit(
    api_client: TestClient,
) -> None:
    """The figure lives on the quantity entity - a copy here would be a
    second source of truth for a rated value."""

    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    statement = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"][0]

    assert "value" not in statement
    assert "unit" not in statement
    assert "confidence" not in statement
    assert set(statement) == {
        "statement_key",
        "statement_type",
        "subject_entity_key",
        "object_entity_key",
        "status",
        "semantic_contract_version",
        "semantic_rule_id",
        "semantic_rule_version",
        "supporting_fact_keys",
    }


def test_the_diagnostic_names_no_object_or_statement_type(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    diagnostic = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["diagnostics"][0]

    assert diagnostic["reason"] == "multiple_candidate_quantities"
    assert len(diagnostic["candidate_fact_keys"]) == 2
    assert "object_entity_key" not in diagnostic
    assert "statement_type" not in diagnostic


# --- The support chain, over the API ------------------------------------------------------


def test_one_statement_can_be_read_by_key(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    statement_key = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"][0]["statement_key"]

    response = api_client.get(
        f"/documents/{document_id}/engineering-semantics/{statement_key}"
    )

    assert response.status_code == 200
    assert response.json()["statement_key"] == statement_key


def test_a_statement_enumerates_the_facts_supporting_it(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    statement = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"][0]

    response = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement['statement_key']}/facts"
    )

    assert response.status_code == 200
    facts = response.json()
    assert len(facts) == 1
    assert facts[0]["predicate"] == "has_associated_quantity"
    assert facts[0]["subject_entity_key"] == statement["subject_entity_key"]


def test_the_whole_chain_is_walkable_over_the_api(
    api_client: TestClient,
) -> None:
    """
    Meaning -> fact -> support -> evidence -> the characters on the page.

    Every link is a key resolving against the endpoint below it, which is
    what lets an engineer disputing an interpretation be shown the line
    it came from.
    """

    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    statement = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"][0]
    fact = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement['statement_key']}/facts"
    ).json()[0]
    evidence = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()["evidence"]
    by_key = {item["evidence_key"]: item for item in evidence}

    supporting = [
        by_key[reference["evidence_key"]]
        for reference in fact["support"]
    ]

    assert supporting
    for item in supporting:
        assert item["provenance"]["spans"]
        assert item["provenance"]["page_number"] == 1


def test_an_unknown_statement_returns_404(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-semantics/nope"
        ).status_code
        == 404
    )


# --- Refusals -----------------------------------------------------------------------------


def test_a_document_without_facts_returns_404(
    api_client: TestClient,
) -> None:
    document = api_client.post(
        "/documents/upload",
        files={
            "file": ("schema.pdf", io.BytesIO(DATA_SHEET), "application/pdf")
        },
        data={"scope": "canonical_library"},
    ).json()["document"]

    assert _interpret(api_client, document["id"]).status_code == 404


def test_reading_semantics_that_were_never_interpreted_returns_404(
    api_client: TestClient,
) -> None:
    document_id = _prepared(api_client, DATA_SHEET)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-semantics"
        ).status_code
        == 404
    )


# --- No graph is written ---------------------------------------------------------------------


def test_interpretation_writes_no_graph_node_or_edge(
    api_client: TestClient, db_session: Session
) -> None:
    from app.models.knowledge_graph import EntityRelation, ProjectEntity

    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    assert db_session.query(ProjectEntity).count() == 0
    assert db_session.query(EntityRelation).count() == 0


def test_no_orm_model_is_exposed(api_client: TestClient) -> None:
    document_id = _prepared(api_client, DATA_SHEET)
    _interpret(api_client, document_id)

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()

    assert "id" not in body
    assert "created_at" not in body
    for statement in body["statements"]:
        assert "id" not in statement
        assert "semantic_set_id" not in statement
