from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.knowledge_graph import (
    EntityRelation,
    EntityType,
    ProjectEntity,
    RelationType,
)

from app.services.ai.extractor import extract_entities


def _normalize_name(name: str) -> str:
    """
    Normalizza il nome mantenendo una forma leggibile.
    """

    return " ".join(name.strip().split())


def find_entity(
    db: Session,
    project_id: int,
    name: str,
    entity_type: EntityType | None = None,
) -> ProjectEntity | None:
    """
    Cerca un'entità all'interno di un progetto.
    """

    normalized_name = _normalize_name(name)

    statement = select(ProjectEntity).where(
        ProjectEntity.project_id == project_id,
        ProjectEntity.name == normalized_name,
    )

    if entity_type is not None:
        statement = statement.where(
            ProjectEntity.entity_type == entity_type,
        )

    return db.scalar(statement)


def create_entity(
    db: Session,
    project_id: int,
    entity_type: EntityType,
    name: str,
    description: str | None = None,
    source_document: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> ProjectEntity:
    """
    Crea una nuova entità nel Knowledge Graph.
    """

    normalized_name = _normalize_name(name)

    if not normalized_name:
        raise ValueError(
            "Entity name cannot be empty."
        )

    entity = ProjectEntity(
        project_id=project_id,
        entity_type=entity_type,
        name=normalized_name,
        description=description,
        source_document=source_document,
        attributes=dict(attributes or {}),
    )

    db.add(entity)
    db.commit()
    db.refresh(entity)

    return entity


def get_or_create_entity(
    db: Session,
    project_id: int,
    entity_type: EntityType,
    name: str,
    description: str | None = None,
    source_document: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> tuple[ProjectEntity, bool]:
    """
    Restituisce un'entità esistente oppure ne crea una nuova.

    Se l'entità esiste già, aggiorna eventuali informazioni mancanti.

    Il secondo valore restituito indica se l'entità è stata creata.
    """

    existing_entity = find_entity(
        db=db,
        project_id=project_id,
        name=name,
        entity_type=entity_type,
    )

    if existing_entity is not None:
        updated = False

        if description and not existing_entity.description:
            existing_entity.description = description
            updated = True

        if source_document and not existing_entity.source_document:
            existing_entity.source_document = source_document
            updated = True

        if attributes:
            merged_attributes = {
                **(existing_entity.attributes or {}),
                **attributes,
            }

            if merged_attributes != existing_entity.attributes:
                existing_entity.attributes = merged_attributes
                updated = True

        if updated:
            db.commit()
            db.refresh(existing_entity)

        return existing_entity, False

    entity = create_entity(
        db=db,
        project_id=project_id,
        entity_type=entity_type,
        name=name,
        description=description,
        source_document=source_document,
        attributes=attributes,
    )

    return entity, True


def get_project_entities(
    db: Session,
    project_id: int,
    entity_type: EntityType | None = None,
) -> list[ProjectEntity]:
    """
    Restituisce tutte le entità di un progetto.
    """

    statement = (
        select(ProjectEntity)
        .where(
            ProjectEntity.project_id == project_id,
        )
        .order_by(
            ProjectEntity.entity_type,
            ProjectEntity.name,
        )
    )

    if entity_type is not None:
        statement = statement.where(
            ProjectEntity.entity_type == entity_type,
        )

    return list(db.scalars(statement).all())


def create_relation(
    db: Session,
    source_entity_id: int,
    target_entity_id: int,
    relation_type: RelationType,
) -> EntityRelation:
    """
    Crea una relazione fra due entità.

    Se la relazione esiste già, restituisce quella esistente.
    """

    if source_entity_id == target_entity_id:
        raise ValueError(
            "An entity cannot be related to itself."
        )

    source_entity = db.get(
        ProjectEntity,
        source_entity_id,
    )

    target_entity = db.get(
        ProjectEntity,
        target_entity_id,
    )

    if source_entity is None:
        raise ValueError(
            f"Source entity {source_entity_id} does not exist."
        )

    if target_entity is None:
        raise ValueError(
            f"Target entity {target_entity_id} does not exist."
        )

    if source_entity.project_id != target_entity.project_id:
        raise ValueError(
            "Entities from different projects cannot be related."
        )

    statement = select(EntityRelation).where(
        EntityRelation.source_entity_id == source_entity_id,
        EntityRelation.target_entity_id == target_entity_id,
        EntityRelation.relation_type == relation_type,
    )

    existing_relation = db.scalar(statement)

    if existing_relation is not None:
        return existing_relation

    relation = EntityRelation(
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relation_type=relation_type,
    )

    db.add(relation)
    db.commit()
    db.refresh(relation)

    return relation


def get_related_entities(
    db: Session,
    entity_id: int,
    relation_type: RelationType | None = None,
) -> list[ProjectEntity]:
    """
    Restituisce le entità collegate all'entità indicata.
    """

    entity = db.get(
        ProjectEntity,
        entity_id,
    )

    if entity is None:
        raise ValueError(
            f"Entity {entity_id} does not exist."
        )

    statement = (
        select(ProjectEntity)
        .join(
            EntityRelation,
            or_(
                EntityRelation.target_entity_id
                == ProjectEntity.id,
                EntityRelation.source_entity_id
                == ProjectEntity.id,
            ),
        )
        .where(
            or_(
                EntityRelation.source_entity_id
                == entity_id,
                EntityRelation.target_entity_id
                == entity_id,
            ),
            ProjectEntity.id != entity_id,
        )
        .distinct()
        .order_by(ProjectEntity.name)
    )

    if relation_type is not None:
        statement = statement.where(
            EntityRelation.relation_type
            == relation_type,
        )

    return list(db.scalars(statement).all())


def ingest_document(
    db: Session,
    project_id: int,
    text: str,
    source_document: str | None = None,
) -> list[ProjectEntity]:
    """
    Estrae le entità dal testo, le salva nel Knowledge Graph
    e aggiorna la topologia della sottostazione.
    """

    processed_entities: list[ProjectEntity] = []

    extracted_entities = extract_entities(text)

    for extracted in extracted_entities:
        entity, _ = get_or_create_entity(
            db=db,
            project_id=project_id,
            entity_type=extracted.entity_type,
            name=extracted.name,
            description=extracted.description,
            source_document=source_document,
            attributes=extracted.attributes,
        )

        processed_entities.append(entity)

    from app.services.topology.builder import build_substation_topology

    build_substation_topology(
        db=db,
        project_id=project_id,
    )

    return processed_entities