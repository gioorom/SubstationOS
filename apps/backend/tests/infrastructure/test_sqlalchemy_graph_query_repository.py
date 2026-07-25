from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.infrastructure.graph_query.sqlalchemy_graph_query_repository import (
    SqlAlchemyGraphQueryRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store import (
    SqlAlchemyGraphStore,
)
from app.models.project import Project as ProjectRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project(db_session: Session, code: str = "ALPHA-001") -> int:
    project = ProjectRecord(
        name="Alpha Substation",
        code=code,
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project.id


def _entity(project_id: int, entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=project_id,
        entity_type=entity_type,
        canonical_id=canonical_id,
    )


def _seed_graph(db_session: Session, project_id: int) -> None:
    """Cable C-295 --FEEDS--> Transformer TR-02, plus an orphan Breaker
    CB-01, and rated_voltage on TR-02."""

    store = SqlAlchemyGraphStore(db_session)
    cable = _entity(project_id, "CABLE", "C-295")
    transformer = _entity(project_id, "TRANSFORMER", "TR-02")
    breaker = _entity(project_id, "BREAKER", "CB-01")

    store.upsert_node(graph_entity_id=cable, execution_id=1, now=CREATED_AT)
    store.upsert_node(
        graph_entity_id=transformer, execution_id=1, now=CREATED_AT
    )
    store.upsert_node(graph_entity_id=breaker, execution_id=1, now=CREATED_AT)
    store.merge_node_property(
        graph_entity_id=transformer,
        attribute="rated_voltage",
        value="132kV",
        execution_id=1,
        now=CREATED_AT,
    )
    store.upsert_relationship(
        source_entity_id=cable,
        relationship_type=GraphRelationshipType(value="FEEDS"),
        target_entity_id=transformer,
        execution_id=1,
        now=CREATED_AT,
    )
    db_session.commit()


def test_get_node_returns_a_view(db_session: Session) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    node = repository.get_node(
        project_id, _entity(project_id, "CABLE", "C-295")
    )

    assert node is not None
    assert node.canonical_id == "C-295"


def test_get_node_returns_none_when_absent(db_session: Session) -> None:
    project_id = _persist_project(db_session)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    assert (
        repository.get_node(
            project_id, _entity(project_id, "CABLE", "UNKNOWN")
        )
        is None
    )


def test_list_nodes_returns_every_node(db_session: Session) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    assert len(repository.list_nodes(project_id)) == 3


def test_list_nodes_by_type_filters(db_session: Session) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    nodes = repository.list_nodes_by_type(project_id, "TRANSFORMER")

    assert [n.canonical_id for n in nodes] == ["TR-02"]


def test_list_nodes_with_attribute_filters(db_session: Session) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    nodes = repository.list_nodes_with_attribute(
        project_id, "rated_voltage"
    )

    assert [n.canonical_id for n in nodes] == ["TR-02"]
    assert repository.list_nodes_with_attribute(project_id, "unknown") == []


def test_list_orphan_nodes_finds_the_unconnected_node(
    db_session: Session,
) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    orphans = repository.list_orphan_nodes(project_id)

    assert [n.canonical_id for n in orphans] == ["CB-01"]


def test_list_relationships_returns_every_relationship(
    db_session: Session,
) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    relationships = repository.list_relationships(project_id)

    assert len(relationships) == 1
    assert relationships[0].relationship_type.value == "FEEDS"


def test_outgoing_and_incoming_relationship_reads(
    db_session: Session,
) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    cable = _entity(project_id, "CABLE", "C-295")
    transformer = _entity(project_id, "TRANSFORMER", "TR-02")

    assert len(repository.list_outgoing_relationships(project_id, cable)) == 1
    assert (
        len(repository.list_incoming_relationships(project_id, transformer))
        == 1
    )
    assert repository.list_incoming_relationships(project_id, cable) == []
    assert (
        repository.list_outgoing_relationships(project_id, transformer) == []
    )


def test_count_entities_and_relationships_by_type(
    db_session: Session,
) -> None:
    project_id = _persist_project(db_session)
    _seed_graph(db_session, project_id)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    entity_counts = repository.count_entities_by_type(project_id)
    relationship_counts = repository.count_relationships_by_type(project_id)

    assert entity_counts == {"CABLE": 1, "TRANSFORMER": 1, "BREAKER": 1}
    assert relationship_counts == {"FEEDS": 1}


def test_reads_are_project_scoped(db_session: Session) -> None:
    project_a = _persist_project(db_session, code="ALPHA-001")
    project_b = _persist_project(db_session, code="BETA-001")
    _seed_graph(db_session, project_a)
    repository = SqlAlchemyGraphQueryRepository(db_session)

    assert repository.list_nodes(project_b) == []
    assert repository.list_relationships(project_b) == []
