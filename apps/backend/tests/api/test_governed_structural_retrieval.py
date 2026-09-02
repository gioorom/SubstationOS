"""
Retrieving and assembling the governed structural relationship
(EPIC 32.P1).

The stages EPIC 32.2 will read from, driven through the real layers: the
real reader against real promoted rows, the real retrieval service, the
real Context Assembly service. Nothing here is a stub.

What has to survive the trip, and is asserted at each end:

```
subject identity -> predicate -> object identity
statement key -> review id -> document id
```

Retrieval **returns** governed relationships. It does not compose them,
does not close them transitively, and does not decide that two assets in
one location have anything to do with each other. That remains EPIC
32.2's problem, and its absence here is deliberate.
"""

from __future__ import annotations

import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    RelationshipQuery,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedResultKind,
    RetrievalScope,
)
from app.infrastructure.governed_retrieval.sqlalchemy_governed_knowledge_reader import (  # noqa: E501
    SqlAlchemyGovernedKnowledgeReader,
)
from app.services import context_builder_service, governed_retrieval_service
from tests._pdf_builder import single_page_pdf

SWITCHGEAR = "Interruttore +E01-QA1 in cabina"
TWO_DEVICES = "Quadro +E01-QA1 e +E01-QB1 installati"

RETRIEVED_AT = datetime(2026, 1, 1, 12, 0, 0)


def _project(api_client: TestClient) -> int:
    return api_client.post(
        "/projects/",
        json={
            "name": "Structural Substation",
            "code": "EPIC-32-P1",
            "customer": "Acme Utilities",
        },
    ).json()["id"]


def _governed_document(
    api_client: TestClient, project_id: int, text: str
) -> int:
    """A document taken all the way to promoted governed knowledge."""

    document_id = api_client.post(
        "/documents/upload",
        files={
            "file": ("schema.pdf", io.BytesIO(single_page_pdf(text)), "application/pdf")
        },
        data={"scope": "project", "project_id": str(project_id)},
    ).json()["document"]["id"]

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

    for statement in api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()["statements"]:
        api_client.post(
            f"/documents/{document_id}/engineering-semantics/"
            f"{statement['statement_key']}/reviews",
            json={
                "decision": "approved",
                "reason": "confirmed_by_source",
                "comment": None,
            },
        )

    api_client.post(
        "/knowledge-graph/promotions", params={"document_id": document_id}
    )

    return document_id


def _retrieve_locations(db_session: Session, project_id: int):
    query = RelationshipQuery(
        scope=RetrievalScope.CURRENT_ONLY,
        limit=20,
        edge_kind=GraphEdgeKind.IS_LOCATED_IN,
        project_id=project_id,
    )

    return governed_retrieval_service.retrieve(
        SqlAlchemyGovernedKnowledgeReader(db_session),
        query,
        now=RETRIEVED_AT,
    )


@pytest.fixture()
def governed(api_client: TestClient) -> int:
    project_id = _project(api_client)
    _governed_document(api_client, project_id, SWITCHGEAR)

    return project_id


# --- Retrieval -----------------------------------------------------------


def test_the_structural_relationship_is_retrievable_by_kind(
    governed: int, db_session: Session
) -> None:
    result = _retrieve_locations(db_session, governed)

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert len(result.items) == 1

    relationship = result.items[0].relationship

    assert result.items[0].kind is GovernedResultKind.RELATIONSHIP
    assert relationship.kind is GraphEdgeKind.IS_LOCATED_IN
    assert relationship.subject.kind is GraphNodeKind.ENGINEERING_ASSET
    assert relationship.subject.label == "+E01-QA1"
    assert relationship.object.kind is GraphNodeKind.STRUCTURAL_LOCATION
    assert relationship.object.label == "+E01"


def test_every_retrieved_relationship_carries_its_provenance(
    governed: int, db_session: Session
) -> None:
    provenance = _retrieve_locations(db_session, governed).items[0].provenance

    assert provenance.statement_key
    assert provenance.review_id > 0
    assert provenance.reviewer_display_name
    assert provenance.document_id > 0
    assert provenance.semantic_rule_id == (
        "location_from_compound_reference_designation"
    )


def test_retrieval_carries_no_score(
    governed: int, db_session: Session
) -> None:
    """AF-RET-003, restated for the new relationship: a governed answer is
    explained by which strategy matched it, never weighted."""

    item = _retrieve_locations(db_session, governed).items[0]

    for forbidden in ("score", "confidence", "weight", "probability"):
        assert not hasattr(item, forbidden)
        assert not hasattr(item.match, forbidden)


def test_retrieval_is_deterministic(
    governed: int, db_session: Session
) -> None:
    first = _retrieve_locations(db_session, governed)
    second = _retrieve_locations(db_session, governed)

    assert [item.result_id for item in first.items] == [
        item.result_id for item in second.items
    ]


def test_two_devices_in_one_location_retrieve_as_two_relationships(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Two relationships sharing an object - **not** one relationship, and
    not a third relationship between the two devices. Retrieval returns
    what was promoted and composes nothing.
    """

    project_id = _project(api_client)
    _governed_document(api_client, project_id, TWO_DEVICES)

    result = _retrieve_locations(db_session, project_id)

    assert len(result.items) == 2

    subjects = {
        item.relationship.subject.node_id for item in result.items
    }
    objects = {item.relationship.object.node_id for item in result.items}

    assert len(subjects) == 2
    assert len(objects) == 1
    assert not subjects & objects


def test_a_project_sees_only_its_own_structural_relationships(
    api_client: TestClient, db_session: Session
) -> None:
    """Project scoping is unchanged by the new relationship kind."""

    first = _project(api_client)
    _governed_document(api_client, first, SWITCHGEAR)

    second = api_client.post(
        "/projects/",
        json={
            "name": "Other Substation",
            "code": "EPIC-32-P1-B",
            "customer": "Acme Utilities",
        },
    ).json()["id"]

    assert _retrieve_locations(db_session, second).items == ()
    assert len(_retrieve_locations(db_session, first).items) == 1


# --- Context Assembly ----------------------------------------------------


def test_the_structural_relationship_reaches_the_context_package(
    governed: int, db_session: Session
) -> None:
    result = _retrieve_locations(db_session, governed)

    package = context_builder_service.build_context_package(
        project_id=governed,
        results=(result,),
        now=RETRIEVED_AT,
    ).package

    assert len(package.selected_relationships) == 1

    selected = package.selected_relationships[0]
    relationship = selected.result.relationship

    # Subject, predicate and object all reconstructable.
    assert relationship.subject.label == "+E01-QA1"
    assert relationship.kind is GraphEdgeKind.IS_LOCATED_IN
    assert relationship.object.label == "+E01"

    # And the governed chain behind them.
    assert selected.result.provenance.statement_key
    assert selected.result.provenance.review_id > 0
    assert selected.result.provenance.document_id > 0


def test_context_assembly_infers_no_relationship(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Two assets in one location reach the context as two containment
    items. Context Assembly selects; it does not conclude.
    """

    project_id = _project(api_client)
    _governed_document(api_client, project_id, TWO_DEVICES)

    package = context_builder_service.build_context_package(
        project_id=project_id,
        results=(_retrieve_locations(db_session, project_id),),
        now=RETRIEVED_AT,
    ).package

    kinds = {
        item.result.relationship.kind
        for item in package.selected_relationships
    }

    assert len(package.selected_relationships) == 2
    assert kinds == {GraphEdgeKind.IS_LOCATED_IN}


def test_context_assembly_is_deterministic(
    governed: int, db_session: Session
) -> None:
    result = _retrieve_locations(db_session, governed)

    first = context_builder_service.build_context_package(
        project_id=governed, results=(result,), now=RETRIEVED_AT
    ).package
    second = context_builder_service.build_context_package(
        project_id=governed, results=(result,), now=RETRIEVED_AT
    ).package

    assert first == second


# --- The line-scoped shape reaches retrieval unchanged (EPIC 32.P2) ------
#
# The claim EPIC 32.P2 has to earn downstream: retrieval and context
# assembly required **no** change to consume relationships established by
# the new construction rule. They read governed knowledge, and governed
# knowledge does not record which structural rule produced the fact
# beneath the statement - which is exactly why neither layer can develop
# an opinion about it.
#
# Verbatim from a committed an Italian DSO HV/MV functional diagram
# (LINEE AT, sha256 835469be…).
REAL_TERMINAL_BLOCK = "MORSETTIERA -E.AM +GSH002"


@pytest.fixture()
def governed_real_line(api_client: TestClient) -> int:
    project_id = _project(api_client)
    _governed_document(api_client, project_id, REAL_TERMINAL_BLOCK)

    return project_id


def test_a_line_scoped_relationship_is_retrievable_by_kind(
    governed_real_line: int, db_session: Session
) -> None:
    """The same query, the same edge kind. Retrieval does not know the
    difference and must not be able to."""

    result = _retrieve_locations(db_session, governed_real_line)

    assert result.outcome is GovernedMatchOutcome.UNIQUE_MATCH
    assert len(result.items) == 1

    relationship = result.items[0].relationship

    assert relationship.kind is GraphEdgeKind.IS_LOCATED_IN
    assert relationship.subject.kind is GraphNodeKind.ENGINEERING_ASSET
    assert relationship.subject.label == "-E.AM"
    assert relationship.object.kind is GraphNodeKind.STRUCTURAL_LOCATION
    assert relationship.object.label == "+GSH002"


def test_a_line_scoped_relationship_reaches_the_context_package(
    governed_real_line: int, db_session: Session
) -> None:
    package = context_builder_service.build_context_package(
        project_id=governed_real_line,
        results=(_retrieve_locations(db_session, governed_real_line),),
        now=RETRIEVED_AT,
    ).package

    assert len(package.selected_relationships) == 1

    selected = package.selected_relationships[0]

    assert selected.result.relationship.object.label == "+GSH002"
    assert selected.result.provenance.statement_key
    assert selected.result.provenance.review_id > 0


def test_retrieval_carries_no_trace_of_the_construction_rule(
    governed_real_line: int, db_session: Session
) -> None:
    """
    The boundary that keeps EPIC 32.P2 out of the answering path.

    A retrieved relationship names the semantic rule an engineer
    reviewed. It does not name the fact-construction rule, so no
    consumer can special-case line-derived knowledge - and a future one
    that wanted to would have to change the governed model to do it.
    """

    provenance = _retrieve_locations(
        db_session, governed_real_line
    ).items[0].provenance

    assert provenance.semantic_rule_id == (
        "location_from_compound_reference_designation"
    )
    assert not hasattr(provenance, "construction_rule_id")
    assert not hasattr(provenance, "structural_scope")
