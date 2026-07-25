from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    GraphNodeNotFoundError,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store import (
    SqlAlchemyGraphStore,
)
from app.models.project import Project as ProjectRecord
from app.models.project_knowledge_graph import ProjectGraphNodeRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project(db_session: Session) -> ProjectRecord:
    project = ProjectRecord(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project


def _entity(project_id: int, canonical_id: str = "C-295") -> GraphEntityId:
    return GraphEntityId(
        project_id=project_id,
        entity_type="CABLE",
        canonical_id=canonical_id,
    )


def test_upsert_node_creates_a_new_node(db_session: Session) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)

    node = store.upsert_node(
        graph_entity_id=_entity(project.id),
        execution_id=1,
        now=CREATED_AT,
    )
    db_session.commit()

    assert node.id is not None
    assert node.properties.as_dict() == {}
    assert node.created_by_execution_id == 1


def test_upsert_node_is_idempotent_and_creates_no_duplicate(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)
    entity_id = _entity(project.id)

    first = store.upsert_node(
        graph_entity_id=entity_id,
        execution_id=1,
        now=CREATED_AT,
    )
    second = store.upsert_node(
        graph_entity_id=entity_id,
        execution_id=2,
        now=CREATED_AT,
    )
    db_session.commit()

    assert first.id == second.id
    # Left semantically unchanged: still no execution-2 provenance on
    # create - the second call found it already present.
    assert second.created_by_execution_id == 1

    count = (
        db_session.query(ProjectGraphNodeRecord)
        .filter(ProjectGraphNodeRecord.project_id == project.id)
        .count()
    )
    assert count == 1


def test_merge_node_property_preserves_unrelated_attributes(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)
    entity_id = _entity(project.id)
    store.upsert_node(graph_entity_id=entity_id, execution_id=1, now=CREATED_AT)

    store.merge_node_property(
        graph_entity_id=entity_id,
        attribute="rated_voltage",
        value="132kV",
        execution_id=2,
        now=CREATED_AT,
    )
    node = store.merge_node_property(
        graph_entity_id=entity_id,
        attribute="rated_current",
        value="630A",
        execution_id=3,
        now=CREATED_AT,
    )
    db_session.commit()

    assert node.properties.as_dict() == {
        "rated_voltage": "132kV",
        "rated_current": "630A",
    }
    assert node.updated_by_execution_id == 3


def test_merge_node_property_raises_for_an_absent_node(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)

    with pytest.raises(GraphNodeNotFoundError):
        store.merge_node_property(
            graph_entity_id=_entity(project.id),
            attribute="rated_voltage",
            value="132kV",
            execution_id=1,
            now=CREATED_AT,
        )


def test_upsert_relationship_requires_both_endpoints(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)
    store.upsert_node(
        graph_entity_id=_entity(project.id, "C-295"),
        execution_id=1,
        now=CREATED_AT,
    )

    with pytest.raises(GraphNodeNotFoundError):
        store.upsert_relationship(
            source_entity_id=_entity(project.id, "C-295"),
            relationship_type=GraphRelationshipType(value="FEEDS"),
            target_entity_id=GraphEntityId(
                project_id=project.id,
                entity_type="TRANSFORMER",
                canonical_id="TR-02",
            ),
            execution_id=1,
            now=CREATED_AT,
        )


def test_upsert_relationship_is_idempotent(db_session: Session) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)
    source = _entity(project.id, "C-295")
    target = GraphEntityId(
        project_id=project.id,
        entity_type="TRANSFORMER",
        canonical_id="TR-02",
    )
    store.upsert_node(graph_entity_id=source, execution_id=1, now=CREATED_AT)
    store.upsert_node(graph_entity_id=target, execution_id=1, now=CREATED_AT)
    relationship_type = GraphRelationshipType(value="FEEDS")

    first = store.upsert_relationship(
        source_entity_id=source,
        relationship_type=relationship_type,
        target_entity_id=target,
        execution_id=1,
        now=CREATED_AT,
    )
    second = store.upsert_relationship(
        source_entity_id=source,
        relationship_type=relationship_type,
        target_entity_id=target,
        execution_id=2,
        now=CREATED_AT,
    )
    db_session.commit()

    assert first.id == second.id

    relationships = store.list_relationships(project.id)
    assert len(relationships) == 1


def test_outgoing_and_incoming_relationship_reads(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    store = SqlAlchemyGraphStore(db_session)
    cable = _entity(project.id, "C-295")
    transformer = GraphEntityId(
        project_id=project.id,
        entity_type="TRANSFORMER",
        canonical_id="TR-02",
    )
    store.upsert_node(graph_entity_id=cable, execution_id=1, now=CREATED_AT)
    store.upsert_node(
        graph_entity_id=transformer, execution_id=1, now=CREATED_AT
    )
    store.upsert_relationship(
        source_entity_id=cable,
        relationship_type=GraphRelationshipType(value="FEEDS"),
        target_entity_id=transformer,
        execution_id=1,
        now=CREATED_AT,
    )
    db_session.commit()

    outgoing = store.list_outgoing_relationships(project.id, cable)
    incoming = store.list_incoming_relationships(project.id, transformer)

    assert len(outgoing) == 1
    assert outgoing[0].target_entity_id.value == transformer.value
    assert len(incoming) == 1
    assert incoming[0].source_entity_id.value == cable.value
    assert store.list_outgoing_relationships(project.id, transformer) == []
    assert store.list_incoming_relationships(project.id, cable) == []


def test_database_enforces_node_natural_key_uniqueness(
    db_session: Session,
) -> None:
    project = _persist_project(db_session)
    db_session.add(
        ProjectGraphNodeRecord(
            project_id=project.id,
            entity_type="CABLE",
            canonical_id="C-295",
            properties={},
            created_by_execution_id=None,
            updated_by_execution_id=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
    )
    db_session.commit()

    db_session.add(
        ProjectGraphNodeRecord(
            project_id=project.id,
            entity_type="CABLE",
            canonical_id="C-295",
            properties={},
            created_by_execution_id=None,
            updated_by_execution_id=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
