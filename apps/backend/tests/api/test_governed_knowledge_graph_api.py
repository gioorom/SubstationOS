"""
The Governed Knowledge Graph, end to end.

Driven through real documents, real pipeline runs and real reviews. Four
things these tests exist to prove above everything else:

1. **Only approved, applicable semantics become knowledge.** Every other
   review state is refused, and each refusal is checked separately.
2. **Promotion modifies no artefact.** The semantic set and the review
   history compare equal before and after.
3. **The graph is rebuildable.** Dropping it and rebuilding from the
   pipeline and the reviews reproduces identical content.
4. **Stale knowledge is never silently retained.** A judgement that stops
   holding retires the knowledge it authorised, with a stated reason.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests._pdf_builder import single_page_pdf
from tests.conftest import _make_user, authenticate

TRANSFORMER = "Trasformatore TR1 630 kVA"


def _upload(api_client: TestClient, content: bytes) -> int:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": ("schema.pdf", io.BytesIO(content), "application/pdf")
        },
        data={"scope": "canonical_library"},
    )

    assert response.status_code == 200

    return response.json()["document"]["id"]


def _run_pipeline(api_client: TestClient, document_id: int) -> None:
    api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document_id}
    )

    for stage in (
        "canonical-representation",
        "canonical-text",
        "engineering-evidence",
        "engineering-entities",
        "engineering-facts",
        "engineering-semantics",
    ):
        api_client.post(f"/documents/{document_id}/{stage}")


def _statement_key(api_client: TestClient, document_id: int) -> str:
    statements = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"]

    assert statements, "the fixture document produced no statement"

    return statements[0]["statement_key"]


def _review(
    api_client: TestClient,
    document_id: int,
    statement_key: str,
    *,
    decision: str = "approved",
    reason: str = "confirmed_by_source",
    comment: str | None = None,
):
    return api_client.post(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        json={
            "decision": decision,
            "reason": reason,
            "comment": comment,
        },
    )


def _promote(
    api_client: TestClient, document_id: int, statement_key: str | None = None
):
    params = {"document_id": document_id}

    if statement_key is not None:
        params["statement_key"] = statement_key

    return api_client.post("/knowledge-graph/promotions", params=params)


def _nodes(api_client: TestClient, **query) -> list[dict]:
    response = api_client.get("/knowledge-graph/nodes", params=query)

    assert response.status_code == 200

    return response.json()["items"]


def _edges(api_client: TestClient, **query) -> list[dict]:
    response = api_client.get("/knowledge-graph/edges", params=query)

    assert response.status_code == 200

    return response.json()["items"]


@pytest.fixture()
def interpreted(api_client: TestClient) -> tuple[int, str]:
    """A document with one interpreted statement, not yet reviewed."""

    document_id = _upload(api_client, single_page_pdf(TRANSFORMER))
    _run_pipeline(api_client, document_id)

    return (document_id, _statement_key(api_client, document_id))


@pytest.fixture()
def approved(api_client: TestClient, interpreted) -> tuple[int, str]:
    """A document whose one statement an engineer has approved."""

    document_id, statement_key = interpreted

    assert _review(api_client, document_id, statement_key).status_code == 201

    return (document_id, statement_key)


# --- Only approved, applicable semantics become knowledge ---------------


def test_an_approved_applicable_statement_is_promoted(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    response = _promote(api_client, document_id, statement_key)

    assert response.status_code == 201
    assert response.json()["promoted"] == 1

    edges = _edges(api_client)

    assert len(edges) == 1
    assert edges[0]["kind"] == "has_rated_power"
    assert edges[0]["statement_key"] == statement_key
    assert edges[0]["state"] == "active"


def test_an_unreviewed_statement_never_becomes_knowledge(
    api_client: TestClient, interpreted
) -> None:
    document_id, statement_key = interpreted

    _promote(api_client, document_id, statement_key)

    assert _edges(api_client) == []
    assert _nodes(api_client) == []


def test_a_rejected_statement_never_becomes_a_graph_node(
    api_client: TestClient, interpreted
) -> None:
    document_id, statement_key = interpreted

    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="incorrect_interpretation",
        comment="la potenza non è quella nominale",
    )

    _promote(api_client, document_id, statement_key)

    assert _edges(api_client) == []


def test_needs_investigation_never_becomes_graph_knowledge(
    api_client: TestClient, interpreted
) -> None:
    document_id, statement_key = interpreted

    _review(
        api_client,
        document_id,
        statement_key,
        decision="needs_investigation",
        reason="ambiguous_evidence",
        comment="due potenze sulla stessa riga",
    )

    _promote(api_client, document_id, statement_key)

    assert _edges(api_client) == []


def test_requires_revalidation_never_becomes_graph_knowledge(
    api_client: TestClient, db_session: Session, approved
) -> None:
    """
    The statement was approved, then the pipeline moved on. The judgement
    was passed on something derived under different rules, so it cannot
    authorise knowledge about what exists now.
    """

    document_id, statement_key = approved

    from app.models.engineering_semantics import (
        EngineeringSemanticStatementRecord,
    )

    db_session.query(EngineeringSemanticStatementRecord).filter(
        EngineeringSemanticStatementRecord.statement_key == statement_key
    ).delete()
    db_session.commit()

    _promote(api_client, document_id, statement_key)

    assert _edges(api_client) == []


def test_an_orphaned_review_never_becomes_graph_knowledge(
    api_client: TestClient, db_session: Session, approved
) -> None:
    document_id, statement_key = approved

    from app.models.engineering_semantics import EngineeringSemanticSetRecord

    db_session.query(EngineeringSemanticSetRecord).filter(
        EngineeringSemanticSetRecord.document_id == document_id
    ).delete()
    db_session.commit()

    _promote(api_client, document_id, statement_key)

    assert _edges(api_client) == []


def test_a_statement_reports_why_it_is_not_promoted(
    api_client: TestClient, interpreted
) -> None:
    """
    "Not promoted" and "not promoted because nobody has approved it" are
    different things to an engineer looking at the screen.
    """

    document_id, statement_key = interpreted

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/promotion"
    ).json()

    assert body["promoted"] is False
    assert body["refusal"] == "not_reviewed"


# --- Promotion modifies nothing upstream --------------------------------


def test_promotion_changes_no_engineering_artefact(
    api_client: TestClient, approved
) -> None:
    """
    Engineering artefacts stay immutable. The graph is a projection.
    """

    document_id, statement_key = approved

    before = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()

    _promote(api_client, document_id, statement_key)

    assert (
        api_client.get(
            f"/documents/{document_id}/engineering-semantics"
        ).json()
        == before
    )


def test_promotion_changes_no_review(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    path = (
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews"
    )
    before = api_client.get(path).json()

    _promote(api_client, document_id, statement_key)

    assert api_client.get(path).json() == before


# --- Identity and duplicate prevention ----------------------------------


def test_promoting_twice_produces_one_edge(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    first = _promote(api_client, document_id, statement_key).json()
    second = _promote(api_client, document_id, statement_key).json()

    assert first["promoted"] == 1
    # Idempotent: the second run reconciles and reports nothing new.
    assert second["promoted"] == 0
    assert len(_edges(api_client)) == 1
    assert len(_nodes(api_client)) == 2


def test_node_identity_is_stable_across_promotions(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    first = sorted(node["node_id"] for node in _nodes(api_client))

    _promote(api_client, document_id, statement_key)
    second = sorted(node["node_id"] for node in _nodes(api_client))

    assert first == second


def test_two_documents_designating_the_same_name_are_two_assets(
    api_client: TestClient, approved
) -> None:
    """
    A stated limit rather than a bug: deciding that `TR1` in two drawings
    is the same transformer is cross-document entity resolution, which no
    governed rule performs. Merging them here would be the label-matching
    the identity model exists to refuse.
    """

    document_id, statement_key = approved
    _promote(api_client, document_id, statement_key)

    other_id = _upload(api_client, single_page_pdf(TRANSFORMER + " "))
    _run_pipeline(api_client, other_id)
    other_key = _statement_key(api_client, other_id)
    _review(api_client, other_id, other_key)
    _promote(api_client, other_id, other_key)

    assets = _nodes(api_client, kind="engineering_asset")

    assert len(assets) == 2
    assert len({asset["node_id"] for asset in assets}) == 2
    assert {asset["label"] for asset in assets} == {"TR1"}


# --- Revalidation: knowledge never silently stale -----------------------


def test_reversing_a_judgement_retires_the_knowledge(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    assert len(_edges(api_client)) == 1

    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="il disegno è superato",
    )

    result = _promote(api_client, document_id, statement_key).json()

    assert result["retired"] == 1
    assert _edges(api_client) == []


def test_retired_knowledge_is_kept_with_its_reason(
    api_client: TestClient, approved
) -> None:
    """
    Not deleted. An engineering system that silently forgets having
    claimed something cannot answer "what did the graph say when we
    ordered that transformer?".
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="superato",
    )
    _promote(api_client, document_id, statement_key)

    historical = _edges(api_client, include_historical=True)

    assert len(historical) == 1
    assert historical[0]["state"] == "historical"
    assert historical[0]["retirement"]["reason"] == "review_reversed"
    assert historical[0]["provenance"]["statement_key"] == statement_key


def test_a_pipeline_rerun_that_drops_a_statement_retires_its_knowledge(
    api_client: TestClient, db_session: Session, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    from app.models.engineering_semantics import (
        EngineeringSemanticStatementRecord,
    )

    db_session.query(EngineeringSemanticStatementRecord).filter(
        EngineeringSemanticStatementRecord.statement_key == statement_key
    ).delete()
    db_session.commit()

    result = _promote(api_client, document_id).json()

    assert _edges(api_client) == []

    historical = _edges(api_client, include_historical=True)

    assert historical[0]["retirement"]["reason"] == "requires_revalidation"


def test_re_approving_reactivates_the_same_edge(
    api_client: TestClient, approved
) -> None:
    """
    The identity survives the round trip, so every reference to the edge
    does too.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    original = _edges(api_client)[0]["edge_id"]

    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="superato",
    )
    _promote(api_client, document_id, statement_key)

    _review(api_client, document_id, statement_key)
    result = _promote(api_client, document_id, statement_key).json()

    assert result["revalidated"] == 1

    edges = _edges(api_client)

    assert len(edges) == 1
    assert edges[0]["edge_id"] == original


def test_a_node_with_no_remaining_relationships_is_retired(
    api_client: TestClient, approved
) -> None:
    """
    A node exists to be an endpoint of governed relationships. Leaving one
    active with none would let "every approved asset" return assets
    nothing is asserted about.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="superato",
    )
    _promote(api_client, document_id, statement_key)

    assert _nodes(api_client) == []

    retired = _nodes(api_client, include_historical=True)

    assert len(retired) == 2
    assert all(
        node["retirement"]["reason"] == "no_remaining_relationships"
        for node in retired
    )


# --- Rebuild ------------------------------------------------------------


def test_a_rebuild_reproduces_identical_content(
    api_client: TestClient, approved
) -> None:
    """
    **The property the whole context is designed around.** Drop the graph,
    rebuild from the pipeline and the reviews, and the content is the
    same - which is what makes the graph safe to treat as derived.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    before_nodes = _nodes(api_client)
    before_edges = _edges(api_client)

    response = api_client.post("/knowledge-graph/rebuilds")

    assert response.status_code == 201

    assert _nodes(api_client) == before_nodes
    assert _edges(api_client) == before_edges


def test_rebuilding_twice_is_stable(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    api_client.post("/knowledge-graph/rebuilds")
    first = _edges(api_client)

    api_client.post("/knowledge-graph/rebuilds")
    second = _edges(api_client)

    assert first == second


def test_a_rebuild_reports_that_nothing_changed(
    api_client: TestClient, approved
) -> None:
    """
    The cheapest possible drift detector: a rebuild over unchanged sources
    that reports changes is a rebuild worth looking at.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    api_client.post("/knowledge-graph/rebuilds")

    events = api_client.post("/knowledge-graph/rebuilds").json()["result"][
        "events"
    ]

    rebuilt = [
        event for event in events if event["event_type"] == "graph_rebuilt"
    ]

    assert len(rebuilt) == 1


def test_a_rebuild_promotes_from_reviews_alone(
    api_client: TestClient, approved
) -> None:
    """
    Never promoted incrementally - the rebuild finds the approval on its
    own, which is what "rebuildable from pipeline + reviews" means.
    """

    document_id, _ = approved

    assert _edges(api_client) == []

    api_client.post("/knowledge-graph/rebuilds")

    assert len(_edges(api_client)) == 1


def test_a_rebuild_records_a_generation(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    body = api_client.post("/knowledge-graph/rebuilds").json()

    assert body["generation"]["generation_number"] == 1
    assert body["generation"]["trigger"] == "rebuild"
    assert body["generation"]["promotion_contract_version"]
    assert body["generation"]["edge_count"] == 1
    assert body["generation"]["node_count"] == 2

    second = api_client.post("/knowledge-graph/rebuilds").json()

    assert second["generation"]["generation_number"] == 2


def test_an_incremental_promotion_records_no_generation(
    api_client: TestClient, approved
) -> None:
    """
    A generation says "this is the projection as recomputed from
    scratch". Promoting one statement recomputes nothing.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    assert api_client.get("/knowledge-graph/status").json()[
        "latest_generation"
    ] is None


def test_a_rebuild_drops_knowledge_whose_review_was_reversed(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="superato",
    )

    api_client.post("/knowledge-graph/rebuilds")

    assert _edges(api_client) == []


# --- Provenance ---------------------------------------------------------


def test_every_edge_explains_itself(
    api_client: TestClient, approved
) -> None:
    """
    Explainability is mandatory. An edge that could not say where it came
    from would not have been storable.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    provenance = _edges(api_client)[0]["provenance"]

    assert provenance["statement_key"] == statement_key
    assert provenance["document_id"] == document_id
    assert provenance["content_checksum"]
    assert provenance["review_id"] >= 1
    assert provenance["reviewer_display_name"] == "Test Engineer"
    assert provenance["semantic_rule_id"]
    assert provenance["semantic_rule_version"]
    assert provenance["semantic_policy_version"]
    assert provenance["fact_policy_version"]
    assert provenance["resolution_policy_version"]
    assert provenance["support_fingerprint"]


def test_every_node_explains_itself(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    for node in _nodes(api_client):
        assert node["provenance"]["statement_key"] == statement_key
        assert node["provenance"]["review_id"] >= 1


def test_a_graph_answer_carries_no_engineering_payload(
    api_client: TestClient, approved
) -> None:
    """
    The graph names governed artefacts; the pipeline stays their single
    account.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    body = str(_edges(api_client)[0])

    for forbidden in ("supporting_fact_keys", "observed_text", "comment"):
        assert forbidden not in body


# --- Queries ------------------------------------------------------------


def test_an_asset_can_be_found_by_its_designation(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    found = _nodes(api_client, kind="engineering_asset", search="TR1")

    assert len(found) == 1
    assert found[0]["label"] == "TR1"


def test_a_node_answers_with_everything_asserted_about_it(
    api_client: TestClient, approved
) -> None:
    """
    "Find rated power" is this: the asset, its relationships, and the
    quantity on the other end - with the provenance of each.
    """

    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    asset = _nodes(api_client, kind="engineering_asset")[0]

    body = api_client.get(
        f"/knowledge-graph/nodes/{asset['node_id']}"
    ).json()

    assert body["node"]["label"] == "TR1"
    assert len(body["relationships"]) == 1

    relationship = body["relationships"][0]

    assert relationship["direction"] == "outgoing"
    assert relationship["edge"]["kind"] == "has_rated_power"
    assert relationship["other_node"]["kind"] == "engineering_quantity"
    assert relationship["other_node"]["unit"] == "kVA"
    assert relationship["edge"]["provenance"]["review_id"] >= 1


def test_the_quantity_end_reports_the_relationship_as_incoming(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    quantity = _nodes(api_client, kind="engineering_quantity")[0]

    body = api_client.get(
        f"/knowledge-graph/nodes/{quantity['node_id']}"
    ).json()

    assert body["relationships"][0]["direction"] == "incoming"


def test_queries_return_current_knowledge_by_default(
    api_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)
    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="superato",
    )
    _promote(api_client, document_id, statement_key)

    assert _nodes(api_client) == []
    assert len(_nodes(api_client, include_historical=True)) == 2


def test_an_unknown_node_is_a_404(api_client: TestClient) -> None:
    assert (
        api_client.get("/knowledge-graph/nodes/" + "0" * 64).status_code
        == 404
    )


def test_the_vocabulary_is_served_rather_than_duplicated(
    api_client: TestClient,
) -> None:
    body = api_client.get("/knowledge-graph/vocabulary").json()

    assert set(body["node_kinds"]) == {
        "engineering_asset",
        "engineering_quantity",
    }
    assert set(body["edge_kinds"]) == {"has_rated_power"}
    assert body["promotion_contract_version"]


# --- Security -----------------------------------------------------------


def test_an_anonymous_caller_reaches_no_graph_endpoint(
    anonymous_client: TestClient,
) -> None:
    for method, path in (
        ("GET", "/knowledge-graph/vocabulary"),
        ("GET", "/knowledge-graph/status"),
        ("GET", "/knowledge-graph/nodes"),
        ("GET", "/knowledge-graph/edges"),
        ("POST", "/knowledge-graph/promotions?document_id=1"),
        ("POST", "/knowledge-graph/rebuilds"),
    ):
        assert (
            anonymous_client.request(method, path).status_code == 401
        ), path


def test_promotion_is_recorded_in_the_audit_trail(
    api_client: TestClient, administrator_client: TestClient, approved
) -> None:
    document_id, statement_key = approved

    _promote(api_client, document_id, statement_key)

    events = administrator_client.get(
        "/audit/events", params={"action": "knowledge_promoted"}
    ).json()["items"]

    assert len(events) == 1
    assert events[0]["actor"]["authenticated"] is True


def test_a_rebuild_is_recorded_in_the_audit_trail(
    api_client: TestClient, administrator_client: TestClient, approved
) -> None:
    api_client.post("/knowledge-graph/rebuilds")

    events = administrator_client.get(
        "/audit/events", params={"action": "knowledge_graph_rebuilt"}
    ).json()["items"]

    assert len(events) == 1


def test_a_promotion_that_changes_nothing_is_not_audited(
    api_client: TestClient, administrator_client: TestClient, interpreted
) -> None:
    """
    Most statements are unreviewed most of the time. An audit entry per
    no-op run would bury the ones that matter.
    """

    document_id, statement_key = interpreted

    _promote(api_client, document_id, statement_key)

    events = administrator_client.get(
        "/audit/events", params={"action": "knowledge_promoted"}
    ).json()["items"]

    assert events == []


# --- No graph query language --------------------------------------------


def test_the_api_exposes_no_query_language(
    api_client: TestClient,
) -> None:
    """
    A governed graph whose whole value is that every answer is
    explainable should not ship a way to ask questions nobody planned.
    """

    schema = api_client.app.openapi()

    for path in schema["paths"]:
        for forbidden in ("cypher", "graphql", "sparql", "/query"):
            assert forbidden not in path.lower()
