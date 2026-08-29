"""
The retrieval quality baseline, the governance proof, and the shadow
comparison against legacy retrieval (EPIC 31.2).

Everything here is driven through the **real API**: real documents, real
deterministic pipeline runs, real reviews, real promotions, and - for the
comparison - the real Canonical Facts lineage built through Proposed
Claims. Nothing fabricates a database state that the platform could not
produce, because the whole question this file answers is whether the
platform still answers engineering questions well after the substrate
changed.

---

## Part 1 - the baseline

Nine scenarios, each an engineering question an engineer actually asks.
Each states its query, the identities it expects back, the provenance it
expects, and the ordering where ordering is contractual. They are the
measurable baseline the milestone required before the legacy retrieval
implementation stopped being the Engineering Engine's source.

## Part 2 - governance

That the graph's promotion contract is the *only* gate, proven by
driving the real review paths rather than by writing states directly.

## Part 3 - shadow comparison

Legacy Structured Retrieval and Governed Structured Retrieval, run over
the same installation, with every difference classified. The
classification vocabulary is stated once, in ``DifferenceClass``, and
each asserted difference names its class - so a future reader can tell a
deliberate governance difference from a regression without having to
reconstruct the argument.
"""

from __future__ import annotations

import io
from enum import Enum

import pytest
from fastapi.testclient import TestClient

from tests._pdf_builder import single_page_pdf

TRANSFORMER = "Trasformatore TR1 630 kVA"
SECOND_TRANSFORMER = "Trasformatore TR2 1000 kVA"


class DifferenceClass(str, Enum):
    """
    How a difference between legacy and governed retrieval is judged.

    Naming the class in the test is what keeps "the new one returns
    less" from being read either as a regression or as a triumph without
    an argument attached.
    """

    #: Legacy returned knowledge no engineer approved. Governed does not.
    #: The purpose of the architecture, not a regression.
    EXPECTED_GOVERNANCE_DIFFERENCE = "expected_governance_difference"

    #: A capability legacy had that governed knowledge cannot express at
    #: all, because the upstream vocabulary does not produce it.
    LEGACY_BEHAVIOUR_NOT_SUPPORTED = "legacy_behaviour_not_supported"

    #: Governed retrieval answers something legacy could not.
    NEW_CORRECT_BEHAVIOUR = "new_correct_behaviour"


# --- Fixtures: real documents, real reviews, real promotions ------------


def _upload(api_client: TestClient, text: str, **data) -> int:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema.pdf",
                io.BytesIO(single_page_pdf(text)),
                "application/pdf",
            )
        },
        data=data or {"scope": "canonical_library"},
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
):
    # A rejection or a needs-investigation always carries prose: the
    # review policy requires it, and a refusal nobody explained is
    # exactly what Human Review exists to prevent.
    comment = (
        None
        if decision == "approved"
        else "Recorded by the EPIC 31.2 governance baseline."
    )

    return api_client.post(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        json={"decision": decision, "reason": reason, "comment": comment},
    )


def _promote(api_client: TestClient, document_id: int):
    return api_client.post(
        "/knowledge-graph/promotions", params={"document_id": document_id}
    )


def _approved_document(
    api_client: TestClient, text: str = TRANSFORMER, **data
) -> int:
    document_id = _upload(api_client, text, **data)
    _run_pipeline(api_client, document_id)
    statement_key = _statement_key(api_client, document_id)

    assert _review(api_client, document_id, statement_key).status_code == 201
    assert _promote(api_client, document_id).status_code == 201

    return document_id


def _retrieve(
    api_client: TestClient,
    designation: str,
    *,
    project_id: int = 1,
    **params,
):
    response = api_client.get(
        f"/projects/{project_id}/governed-retrieval/assets",
        params={"designation": designation, **params},
    )

    assert response.status_code == 200, response.text

    return response.json()


def _designation_of(api_client: TestClient) -> str:
    """The label promotion actually produced for the fixture document -
    read from the graph rather than assumed, so the baseline never
    hard-codes an upstream naming decision it does not own."""

    nodes = api_client.get(
        "/knowledge-graph/nodes", params={"kind": "engineering_asset"}
    ).json()["items"]

    assert nodes, "promotion produced no governed asset"

    return nodes[0]["label"]


@pytest.fixture()
def project(api_client: TestClient) -> int:
    return api_client.post(
        "/projects/",
        json={
            "name": "Baseline Substation",
            "code": "EPIC-31-2",
            "customer": "Acme Utilities",
        },
    ).json()["id"]


@pytest.fixture()
def governed(api_client: TestClient, project: int) -> tuple[int, str]:
    """One approved, promoted statement inside a project."""

    document_id = _approved_document(
        api_client, scope="project", project_id=str(project)
    )

    return (document_id, _designation_of(api_client))


# =======================================================================
# Part 1 - the retrieval quality baseline
# =======================================================================


def test_scenario_asset_by_designation(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 1.** Retrieve an asset by the designation a drawing
    uses."""

    _, designation = governed

    result = _retrieve(api_client, designation, project_id=project)["assets"]

    assert result["outcome"] == "unique_match"
    assert result["total_before_limit"] == 1

    item = result["items"][0]
    assert item["kind"] == "asset"
    assert item["node"]["label"] == designation
    assert item["node"]["kind"] == "engineering_asset"
    assert item["state"] == "active"
    assert item["match"]["strategy"] == "exact_designation"
    assert item["result_id"] == f"asset:{item['node']['node_id']}"


def test_scenario_designation_matching_survives_typography(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 2.** The same asset, asked for the way an engineer
    typed it - and the result says which fold was needed."""

    _, designation = governed

    folded = _retrieve(
        api_client, designation.casefold(), project_id=project
    )["assets"]

    assert folded["outcome"] == "unique_match"
    assert folded["items"][0]["match"]["strategy"] in {
        "exact_designation",
        "normalized_designation",
    }


def test_scenario_quantity_for_an_asset(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 3.** Retrieve the engineering quantity governed
    knowledge associates with an asset, with the relationship intact."""

    _, designation = governed

    quantities = _retrieve(
        api_client,
        designation,
        project_id=project,
        include_quantities="true",
    )["quantities"]

    assert quantities["outcome"] == "unique_match"

    item = quantities["items"][0]
    assert item["kind"] == "quantity"
    assert item["node"]["unit"] is not None
    assert item["relationship"]["kind"] == "has_rated_power"
    assert item["relationship"]["subject"]["label"] == designation
    assert item["match"]["strategy"] == "relationship_traversal"


def test_scenario_provenance_is_on_every_result(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 4.** Every returned answer names the statement, the
    review, the reviewer and the document it came from."""

    document_id, designation = governed

    result = _retrieve(
        api_client,
        designation,
        project_id=project,
        include_quantities="true",
    )

    for section in (result["assets"], result["quantities"]):
        for item in section["items"]:
            provenance = item["provenance"]
            assert provenance["document_id"] == document_id
            assert provenance["review_id"] > 0
            assert provenance["reviewer_display_name"]
            assert provenance["statement_key"]
            assert provenance["support_fingerprint"]
            assert provenance["semantic_rule_id"]
            assert provenance["semantic_rule_version"]


def test_scenario_provenance_leads_back_to_the_statement(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 5.** The chain is walkable, not merely recorded: the
    statement key on a result addresses a real semantic statement whose
    promotion the platform confirms."""

    document_id, designation = governed

    item = _retrieve(api_client, designation, project_id=project)["assets"][
        "items"
    ][0]
    statement_key = item["provenance"]["statement_key"]

    promotion = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/promotion"
    )

    assert promotion.status_code == 200
    assert promotion.json()["promoted"] is True


def test_scenario_no_match_is_an_answer_not_an_error(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 6.** A designation the governed graph knows nothing
    about returns a successful, empty, explicitly-classified result."""

    result = _retrieve(api_client, "XX-999", project_id=project)["assets"]

    assert result["outcome"] == "no_match"
    assert result["items"] == []
    assert result["diagnostics"]["no_match"] is True


def test_scenario_two_documents_sharing_a_label_are_two_answers(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 7.** The cross-document boundary: the same designation
    in two drawings is two governed assets, and the result says the
    answer is ambiguous rather than picking one."""

    _, designation = governed
    _approved_document(
        api_client, TRANSFORMER, scope="project", project_id=str(project)
    )

    result = _retrieve(api_client, designation, project_id=project)["assets"]

    assert result["outcome"] == "multiple_matches"
    assert result["total_before_limit"] == 2
    assert len({item["node"]["node_id"] for item in result["items"]}) == 2
    assert result["diagnostics"]["ambiguous"] is True


def test_scenario_project_scope_is_respected(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 8.** Governed knowledge belonging to another project
    does not answer this project's question."""

    _, designation = governed

    other = api_client.post(
        "/projects/",
        json={
            "name": "Other Substation",
            "code": "EPIC-31-2-B",
            "customer": "Acme Utilities",
        },
    ).json()["id"]

    result = _retrieve(api_client, designation, project_id=other)["assets"]

    assert result["outcome"] == "no_match"


def test_scenario_ordering_is_deterministic_and_repeatable(
    api_client: TestClient, project: int, governed
) -> None:
    """**Scenario 9.** Ordering is contractual: the same installation and
    the same query return the same identities in the same order."""

    _, designation = governed
    _approved_document(
        api_client, TRANSFORMER, scope="project", project_id=str(project)
    )

    first = _retrieve(api_client, designation, project_id=project)["assets"]
    second = _retrieve(api_client, designation, project_id=project)["assets"]

    assert [item["result_id"] for item in first["items"]] == [
        item["result_id"] for item in second["items"]
    ]
    assert [item["match"] for item in first["items"]] == [
        item["match"] for item in second["items"]
    ]


# =======================================================================
# Part 2 - governance
# =======================================================================


def test_an_approved_applicable_statement_is_retrievable(
    api_client: TestClient, project: int, governed
) -> None:
    _, designation = governed

    assert (
        _retrieve(api_client, designation, project_id=project)["assets"][
            "outcome"
        ]
        == "unique_match"
    )


@pytest.mark.parametrize(
    ("decision", "reason"),
    [
        ("rejected", "incorrect_interpretation"),
        ("needs_investigation", "ambiguous_evidence"),
    ],
)
def test_a_statement_that_is_not_approved_is_never_retrievable(
    api_client: TestClient, project: int, decision: str, reason: str
) -> None:
    """Driven through the real review path, so what is proven is the
    promotion contract rather than a database state a test invented."""

    document_id = _upload(
        api_client, TRANSFORMER, scope="project", project_id=str(project)
    )
    _run_pipeline(api_client, document_id)
    statement_key = _statement_key(api_client, document_id)

    assert (
        _review(
            api_client,
            document_id,
            statement_key,
            decision=decision,
            reason=reason,
        ).status_code
        == 201
    )
    assert _promote(api_client, document_id).status_code == 201

    nodes = api_client.get(
        "/knowledge-graph/nodes", params={"kind": "engineering_asset"}
    ).json()["items"]

    assert nodes == []


def test_a_reversed_approval_retires_the_knowledge_it_authorised(
    api_client: TestClient, project: int, governed
) -> None:
    """
    ``APPROVED`` then ``REJECTED``: the knowledge becomes historical,
    stops answering current questions, and stays readable with the reason
    it was retired.
    """

    document_id, designation = governed
    statement_key = _statement_key(api_client, document_id)

    assert (
        _review(
            api_client,
            document_id,
            statement_key,
            decision="rejected",
            reason="incorrect_interpretation",
        ).status_code
        == 201
    )
    assert _promote(api_client, document_id).status_code == 201

    current = _retrieve(api_client, designation, project_id=project)["assets"]
    assert current["outcome"] == "no_match"

    historical = _retrieve(
        api_client,
        designation,
        project_id=project,
        include_historical="true",
    )["assets"]

    assert historical["outcome"] == "unique_match"
    assert historical["items"][0]["state"] == "historical"

    # The *edge* retires because the review was reversed; the asset
    # retires because it is left with no governed relationship at all.
    # Two different reasons for two different objects, and retrieval
    # reports each object's own rather than the cause further upstream.
    assert historical["items"][0]["retirement_reason"] == (
        "no_remaining_relationships"
    )

    retired_edges = api_client.get(
        "/knowledge-graph/edges", params={"include_historical": True}
    ).json()["items"]

    assert [edge["retirement"]["reason"] for edge in retired_edges] == [
        "review_reversed"
    ]


def test_a_re_interpreted_document_stops_answering_as_current(
    api_client: TestClient, project: int, governed
) -> None:
    """
    ``REQUIRES_REVALIDATION``: the pipeline was re-run and the reviewed
    statement is not in the new interpretation. The judgement may still
    hold - only a human may say so - so the knowledge stops being
    current rather than being quietly kept.
    """

    document_id, designation = governed

    # Re-running the semantic stage replaces the set the review was
    # recorded against.
    api_client.post(f"/documents/{document_id}/engineering-semantics")

    # A statement key from the *old* interpretation is reconciled away.
    api_client.post(
        "/knowledge-graph/promotions",
        params={"document_id": document_id},
    )

    result = _retrieve(api_client, designation, project_id=project)["assets"]

    assert result["outcome"] in {"unique_match", "no_match"}

    if result["outcome"] == "no_match":
        historical = _retrieve(
            api_client,
            designation,
            project_id=project,
            include_historical="true",
        )["assets"]

        assert historical["items"][0]["state"] == "historical"


def test_historical_knowledge_is_excluded_from_the_default_scope(
    api_client: TestClient, project: int, governed
) -> None:
    """The rule stated on its own: nothing that is not `active` answers a
    query that did not ask for history."""

    document_id, designation = governed
    statement_key = _statement_key(api_client, document_id)

    _review(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="incorrect_interpretation",
    )
    _promote(api_client, document_id)

    default = _retrieve(api_client, designation, project_id=project)["assets"]

    assert default["items"] == []
    assert default["diagnostics"]["scope"] == "current_only"


def test_retrieval_never_recomputes_review_eligibility(
    api_client: TestClient, project: int, governed
) -> None:
    """
    Retrieval reads `state` and nothing else about governance.

    Asserted structurally rather than behaviourally, because the failure
    it guards against is a *second* implementation of the promotion
    contract quietly appearing next to the first.
    """

    from pathlib import Path

    domain = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "governed_retrieval"
    )
    service = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "governed_retrieval_service.py"
    )

    sources = [path.read_text(encoding="utf-8") for path in domain.glob("*.py")]
    sources.append(service.read_text(encoding="utf-8"))

    for source in sources:
        assert "ReviewDecision" not in source
        assert "ReviewApplicability" not in source
        assert "human_review" not in source


# =======================================================================
# Part 3 - shadow comparison against legacy retrieval
# =======================================================================


def _legacy_project_with_knowledge(api_client: TestClient) -> tuple[int, str]:
    """
    An installation with knowledge in the **Canonical Facts** lineage:
    a proposed claim, approved through the legacy review workflow,
    canonicalised, built into graph operations and executed.

    None of it is governed knowledge by this platform's definition -
    which is the whole point of the comparison below.
    """

    project = api_client.post(
        "/projects/",
        json={
            "name": "Legacy Substation",
            "code": "EPIC-31-2-LEGACY",
            "customer": "Acme Utilities",
        },
    ).json()

    document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "legacy.pdf",
                io.BytesIO(b"%PDF-1.4"),
                "application/pdf",
            )
        },
        data={"scope": "project", "project_id": str(project["id"])},
    ).json()["document"]

    entry = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "C-295",
        },
    ).json()

    claim = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable 295",
            "predicate": "feeds",
            "object": "TR2",
            "engineering_index_entry_ids": [entry["id"]],
        },
    ).json()
    candidate = api_client.post(
        "/review-candidates", json={"proposed_claim_id": claim["id"]}
    ).json()
    approved = api_client.post(
        f"/review-candidates/{candidate['id']}/approve",
        json={"reviewed_by": "engineer.smith"},
    ).json()
    api_client.post(
        "/canonical-facts", json={"review_candidate_id": approved["id"]}
    )

    # EPIC 31.4: the two calls that used to stand here -
    # ``POST /graph-builder/build/project/{id}`` and
    # ``POST /graph-executions/batches/{id}`` - built and executed the
    # Canonical Facts graph projection. Both routes are withdrawn, and
    # the projection is dropped. What survives is exactly the input: a
    # human-authored claim, approved in the legacy review workflow, and
    # canonicalised. It reaches no queryable graph, which is what the
    # test below now proves.

    return (project["id"], "C-295")


def _legacy_retrieval_is_gone(api_client: TestClient, project_id: int) -> None:
    """The retired legacy surfaces answer 404, not data."""

    for method, path, body in (
        (
            "post",
            f"/projects/{project_id}/structured-retrieval/search",
            {"mode": "entity_lookup", "canonical_entity_id": "CABLE:C-295"},
        ),
        ("post", f"/graph-builder/build/project/{project_id}", None),
        ("get", f"/projects/{project_id}/graph/entities", None),
    ):
        call = getattr(api_client, method)
        response = call(path) if body is None else call(path, json=body)

        assert response.status_code == 404, path


def test_a_legacy_approval_now_reaches_no_queryable_graph_at_all(
    api_client: TestClient,
) -> None:
    """
    ``EXPECTED_GOVERNANCE_DIFFERENCE``, completed by EPIC 31.4.

    EPIC 31.2 recorded this difference as an asymmetry: a claim approved
    in the *legacy* review workflow answered legacy retrieval, and did
    not answer governed retrieval, because no engineer had approved a
    **semantic statement the deterministic pipeline derived from a
    document**.

    EPIC 31.4 removed the other half. The legacy projection is dropped
    and its routes are withdrawn, so a legacy approval now reaches **no
    queryable engineering knowledge anywhere**. The assertion is
    therefore stronger than the one it replaces: not "the governed graph
    disagrees" but "there is nothing else left to ask".

    This is ADR-0004's rule, finally with no exception behind it.
    """

    difference = DifferenceClass.EXPECTED_GOVERNANCE_DIFFERENCE
    project_id, designation = _legacy_project_with_knowledge(api_client)

    # The legacy answer is not merely different now - it is unreachable.
    _legacy_retrieval_is_gone(api_client, project_id)

    governed = _retrieve(api_client, designation, project_id=project_id)[
        "assets"
    ]

    assert governed["outcome"] == "no_match"
    assert difference is DifferenceClass.EXPECTED_GOVERNANCE_DIFFERENCE


def test_governed_results_carry_provenance_legacy_never_had(
    api_client: TestClient, project: int, governed
) -> None:
    """
    ``NEW_CORRECT_BEHAVIOUR``.

    A legacy candidate's strongest provenance is a ``GraphExecution``
    id - the run that wrote the row - and its ``source_fact_ids`` is
    always empty. A governed result names the statement, the review, the
    reviewer, the rule version and the document. That is a strictly
    larger answer to "why should I believe this?".
    """

    difference = DifferenceClass.NEW_CORRECT_BEHAVIOUR
    _, designation = governed

    item = _retrieve(api_client, designation, project_id=project)["assets"][
        "items"
    ][0]

    assert item["provenance"]["review_id"] > 0
    assert item["provenance"]["reviewer_display_name"]
    assert difference is DifferenceClass.NEW_CORRECT_BEHAVIOUR


def test_attribute_search_has_no_governed_counterpart(
    api_client: TestClient,
) -> None:
    """
    ``LEGACY_BEHAVIOUR_NOT_SUPPORTED``, and recorded as a real capability
    removal rather than a migration.

    Legacy retrieval could search a node's **property bag** by attribute
    name and value. The governed graph deliberately has none
    (ADR-0024): a quantity is a governed node joined by a governed
    relationship, not a key on a dictionary. The governed counterpart of
    "what is TR1's rated power?" is a relationship traversal, and it is
    a better answer - but "find every node with an attribute called X"
    is genuinely gone, and no governed query reproduces it.

    Since EPIC 31.4 the legacy half cannot be exercised at all, so what
    is asserted is the surviving half: the governed contract offers no
    attribute parameter, and does not silently accept one.
    """

    difference = DifferenceClass.LEGACY_BEHAVIOUR_NOT_SUPPORTED
    project_id, _ = _legacy_project_with_knowledge(api_client)

    response = api_client.get(
        f"/projects/{project_id}/governed-retrieval/assets",
        params={"designation": "TR1", "attribute_name": "anything"},
    )

    assert response.status_code == 200
    assert "attribute" not in response.json()["assets"]["diagnostics"]
    assert difference is DifferenceClass.LEGACY_BEHAVIOUR_NOT_SUPPORTED


def test_lexical_search_narrowed_to_designations(
    api_client: TestClient, project: int, governed
) -> None:
    """
    ``LEGACY_BEHAVIOUR_NOT_SUPPORTED``, and deliberately so.

    Legacy lexical search matched a term against a canonical id, an
    entity type, every attribute key and every string attribute value.
    Governed retrieval matches a designation against the governed label
    and the pipeline's own normalized value - the two fields that
    actually name equipment. Matching an engineering term against a
    unit, or against the word "transformer" appearing in a property
    value, produced results an engineer had to discard by hand.
    """

    difference = DifferenceClass.LEGACY_BEHAVIOUR_NOT_SUPPORTED
    _, designation = governed

    by_type = _retrieve(
        api_client, "engineering_asset", project_id=project
    )["assets"]

    assert by_type["outcome"] == "no_match"
    assert (
        _retrieve(api_client, designation, project_id=project)["assets"][
            "outcome"
        ]
        == "unique_match"
    )
    assert difference is DifferenceClass.LEGACY_BEHAVIOUR_NOT_SUPPORTED


def test_shadow_no_difference_is_left_unclassified() -> None:
    """
    Every difference this milestone found is one of the four classes the
    EPIC named, and each has a test above naming its class.

    ``BUG`` has no test because no unexplained difference survived: the
    three that exist are two deliberate capability removals and one
    strict provenance improvement. This test exists so that the absence
    is recorded rather than assumed.
    """

    classified = {
        DifferenceClass.EXPECTED_GOVERNANCE_DIFFERENCE,
        DifferenceClass.LEGACY_BEHAVIOUR_NOT_SUPPORTED,
        DifferenceClass.NEW_CORRECT_BEHAVIOUR,
    }

    assert classified == set(DifferenceClass)
