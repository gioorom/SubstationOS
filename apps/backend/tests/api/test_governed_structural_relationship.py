"""
The first governed structural relationship, end to end (EPIC 32.P1).

EPIC 32.2 stopped with `BLOCKED_BY_ONTOLOGY`: the governed graph held one
relationship, `HAS_RATED_POWER`, whose object is a quantity, so no
governed relationship existed between two **structural** objects. This
milestone adds one, and these tests are the proof that it travelled the
whole governed path rather than being inserted somewhere convenient.

The chain, and every stage of it is real here - a real PDF, the real
pipeline endpoints, a real review, the real promotion service:

```
+E01-QA1 in the document
   -> designation evidence   +E01-QA1
   -> location aspect evidence   +E01        (new)
   -> equipment_designation entity / structural_location entity
   -> HAS_LOCATION_ASPECT fact                (new)
   -> IS_LOCATED_IN semantic statement        (new)
   -> Human Review
   -> IS_LOCATED_IN governed edge             (new)
```

What these tests exist to prove, beyond the happy path:

1. **The relationship is written in the document, not inferred.** The
   evidence points at the four characters ``+E01``, and a token that
   does not carry a location aspect produces nothing.
2. **Co-occurrence is still not a relationship.** Two designations on one
   line, in one document, sharing a location - none of it creates a
   relationship that the syntax did not state.
3. **Governance is unchanged.** Unreviewed, rejected and inconclusive
   statements produce no queryable structural knowledge, exactly as for
   the rated-power relationship.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from tests._pdf_builder import single_page_pdf

#: One compound IEC 81346 reference designation. ``+E01`` is the location
#: aspect; ``-QA1`` is the product aspect.
SWITCHGEAR = "Interruttore +E01-QA1 in cabina"

#: Two devices designated in the same location, so the shared structural
#: parent EPIC 32.2 will want actually exists in governed knowledge.
TWO_DEVICES = "Quadro +E01-QA1 e +E01-QB1 installati"

#: A product-within-product compound. IEC 81346 gives ``-`` to the
#: product aspect, so this names a component of a product - **not** a
#: location - and no location relationship may come from it.
SUBASSEMBLY = "Modulo -QA1-XB2 montato"


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


def _statements(api_client: TestClient, document_id: int) -> list[dict]:
    return api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"]


def _located_in_key(api_client: TestClient, document_id: int) -> str:
    keys = [
        statement["statement_key"]
        for statement in _statements(api_client, document_id)
        if statement["statement_type"] == "is_located_in"
    ]

    assert len(keys) == 1, "expected exactly one location statement"

    return keys[0]


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


def _promote(api_client: TestClient, document_id: int):
    return api_client.post(
        "/knowledge-graph/promotions", params={"document_id": document_id}
    )


def _nodes(api_client: TestClient, **query) -> list[dict]:
    response = api_client.get("/knowledge-graph/nodes", params=query)

    assert response.status_code == 200

    return response.json()["items"]


def _edges(api_client: TestClient, **query) -> list[dict]:
    response = api_client.get("/knowledge-graph/edges", params=query)

    assert response.status_code == 200

    return response.json()["items"]


@pytest.fixture()
def interpreted(api_client: TestClient) -> int:
    """A document carrying one compound reference designation, not yet
    reviewed."""

    document_id = _upload(api_client, single_page_pdf(SWITCHGEAR))
    _run_pipeline(api_client, document_id)

    return document_id


@pytest.fixture()
def approved(api_client: TestClient, interpreted: int) -> int:
    """The same document, with its location statement approved."""

    statement_key = _located_in_key(api_client, interpreted)

    assert (
        _review(api_client, interpreted, statement_key).status_code == 201
    )

    return interpreted


# --- The relationship exists, and comes from the document ----------------


def test_a_compound_reference_designation_yields_a_location_statement(
    interpreted: int, api_client: TestClient
) -> None:
    """The semantic layer reads the standard's syntax, and says so with a
    versioned rule."""

    statement = next(
        item
        for item in _statements(api_client, interpreted)
        if item["statement_type"] == "is_located_in"
    )

    assert statement["semantic_rule_id"] == (
        "location_from_compound_reference_designation"
    )
    assert statement["semantic_rule_version"] == "1.0"


def test_the_location_evidence_points_at_the_location_characters(
    interpreted: int, api_client: TestClient
) -> None:
    """
    Provenance is the whole claim here. An observation that pointed at
    the whole token would be recording the designation a second time
    under another name.
    """

    evidence = api_client.get(
        f"/documents/{interpreted}/engineering-evidence"
    ).json()["evidence"]

    location = [
        item for item in evidence if item["evidence_type"] == "location_aspect"
    ]

    assert len(location) == 1
    assert location[0]["observed_text"] == "+E01"
    assert location[0]["rule_id"] == "location_aspect_iec_81346"

    span = location[0]["provenance"]["spans"][0]

    assert span["character_end"] - span["character_start"] == len("+E01")


def test_an_approved_statement_becomes_a_governed_structural_edge(
    approved: int, api_client: TestClient
) -> None:
    assert _promote(api_client, approved).status_code == 201

    edges = _edges(api_client, document_id=approved, kind="is_located_in")

    assert len(edges) == 1

    subjects = {
        node["node_id"]: node
        for node in _nodes(api_client, document_id=approved)
    }
    edge = edges[0]

    assert subjects[edge["subject_node_id"]]["kind"] == "engineering_asset"
    assert subjects[edge["subject_node_id"]]["label"] == "+E01-QA1"
    assert (
        subjects[edge["object_node_id"]]["kind"] == "structural_location"
    )
    assert subjects[edge["object_node_id"]]["label"] == "+E01"


def test_the_structural_edge_carries_complete_provenance(
    approved: int, api_client: TestClient
) -> None:
    """
    The chain an engineer walks back to the page: the statement it was
    promoted from, the review that authorised it, the rule that produced
    it, and the document bytes it was read from.
    """

    _promote(api_client, approved)

    edge = _edges(api_client, document_id=approved, kind="is_located_in")[0]
    provenance = edge["provenance"]

    assert provenance["statement_key"]
    assert provenance["review_id"] > 0
    assert provenance["reviewer_display_name"]
    assert provenance["document_id"] == approved
    assert provenance["content_checksum"]
    assert provenance["semantic_rule_id"] == (
        "location_from_compound_reference_designation"
    )
    assert provenance["semantic_rule_version"] == "1.0"


def test_two_devices_in_one_location_share_the_governed_location(
    api_client: TestClient
) -> None:
    """
    The shape EPIC 32.2 will reason over: two assets, one governed
    structural parent, **two** relationships - never one merged object
    and never an inferred relationship between the two devices.
    """

    document_id = _upload(api_client, single_page_pdf(TWO_DEVICES))
    _run_pipeline(api_client, document_id)

    for statement in _statements(api_client, document_id):
        if statement["statement_type"] == "is_located_in":
            _review(api_client, document_id, statement["statement_key"])

    _promote(api_client, document_id)

    edges = _edges(api_client, document_id=document_id, kind="is_located_in")

    assert len(edges) == 2
    assert len({edge["subject_node_id"] for edge in edges}) == 2
    assert len({edge["object_node_id"] for edge in edges}) == 1

    # And no relationship between the two devices was invented.
    assert not [
        edge
        for edge in _edges(api_client, document_id=document_id)
        if edge["kind"] not in ("is_located_in", "has_rated_power")
    ]


# --- Governance is unchanged --------------------------------------------


def test_an_unreviewed_location_statement_never_becomes_knowledge(
    interpreted: int, api_client: TestClient
) -> None:
    _promote(api_client, interpreted)

    assert _edges(api_client, document_id=interpreted) == []
    assert _nodes(api_client, document_id=interpreted) == []


@pytest.mark.parametrize(
    "decision, reason",
    (
        ("rejected", "incorrect_interpretation"),
        ("needs_investigation", "ambiguous_evidence"),
    ),
)
def test_a_refused_location_statement_never_becomes_knowledge(
    interpreted: int, api_client: TestClient, decision: str, reason: str
) -> None:
    """A judgement that is not an approval is not a weak approval."""

    statement_key = _located_in_key(api_client, interpreted)

    assert (
        _review(
            api_client,
            interpreted,
            statement_key,
            decision=decision,
            reason=reason,
            comment="la sigla non indica un'ubicazione",
        ).status_code
        == 201
    )

    _promote(api_client, interpreted)

    assert _edges(api_client, document_id=interpreted, kind="is_located_in") == []


def test_promoting_twice_produces_one_structural_edge(
    approved: int, api_client: TestClient
) -> None:
    _promote(api_client, approved)
    _promote(api_client, approved)

    assert (
        len(_edges(api_client, document_id=approved, kind="is_located_in"))
        == 1
    )


def test_a_rebuild_reproduces_the_same_structural_edge(
    approved: int, api_client: TestClient
) -> None:
    """The graph is a projection: dropping it and rebuilding from the
    statements and the reviews reproduces it exactly."""

    _promote(api_client, approved)
    before = _edges(api_client, document_id=approved, kind="is_located_in")

    rebuild = api_client.post("/knowledge-graph/rebuilds")

    assert rebuild.status_code == 201

    after = _edges(api_client, document_id=approved, kind="is_located_in")

    assert [edge["edge_id"] for edge in after] == [
        edge["edge_id"] for edge in before
    ]


# --- Ontology safety: what may NOT become a relationship ----------------


def test_a_product_within_a_product_yields_no_location(
    api_client: TestClient
) -> None:
    """
    ``-QA1-XB2`` is a component of a product, not a product in a place.
    Reading its first segment as a location would be inventing a meaning
    the standard assigns elsewhere.
    """

    document_id = _upload(api_client, single_page_pdf(SUBASSEMBLY))
    _run_pipeline(api_client, document_id)

    evidence = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).json()["evidence"]

    assert not [
        item for item in evidence if item["evidence_type"] == "location_aspect"
    ]
    assert not [
        statement
        for statement in _statements(api_client, document_id)
        if statement["statement_type"] == "is_located_in"
    ]


def test_a_plain_designation_yields_no_location(
    api_client: TestClient
) -> None:
    """``TR1`` says nothing about where it is. Neither does this
    pipeline."""

    document_id = _upload(
        api_client, single_page_pdf("Trasformatore TR1 630 kVA")
    )
    _run_pipeline(api_client, document_id)

    assert not [
        statement
        for statement in _statements(api_client, document_id)
        if statement["statement_type"] == "is_located_in"
    ]


def test_the_same_location_in_two_documents_is_two_governed_locations(
    api_client: TestClient
) -> None:
    """
    Cross-document entity resolution remains out of scope. Two documents
    writing ``+E01`` may mean two different places, and deciding
    otherwise is a capability nobody has reviewed.
    """

    first = _upload(api_client, single_page_pdf(SWITCHGEAR))
    second = _upload(api_client, single_page_pdf(SWITCHGEAR))

    for document_id in (first, second):
        _run_pipeline(api_client, document_id)
        _review(
            api_client, document_id, _located_in_key(api_client, document_id)
        )
        _promote(api_client, document_id)

    locations = [
        node
        for document_id in (first, second)
        for node in _nodes(api_client, document_id=document_id)
        if node["kind"] == "structural_location"
    ]

    assert len(locations) == 2
    assert len({node["node_id"] for node in locations}) == 2
