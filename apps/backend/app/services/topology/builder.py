from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_graph import (
    EntityRelation,
    ProjectEntity,
)

from app.services.topology.ontology import (
    EquipmentDefinition,
    EquipmentRole,
    TopologyConnection,
    matches_alias,
)

from app.services.topology.transformer_bay import (
    PROTECTION_CONNECTIONS,
    PROTECTION_EQUIPMENT,
    TRANSFORMER_BAY_CONNECTIONS,
    TRANSFORMER_BAY_EQUIPMENT,
)


def get_project_entities(
    db: Session,
    project_id: int,
) -> list[ProjectEntity]:
    """
    Recupera tutte le entità appartenenti al progetto.

    Il builder usa tutte le entità del progetto, non soltanto quelle
    estratte dall'ultimo documento caricato.
    """

    statement = (
        select(ProjectEntity)
        .where(ProjectEntity.project_id == project_id)
        .order_by(
            ProjectEntity.entity_type,
            ProjectEntity.name,
        )
    )

    return list(db.scalars(statement).all())


def get_equipment_definitions() -> tuple[
    EquipmentDefinition,
    ...,
]:
    """
    Restituisce tutte le definizioni conosciute dal template.

    Comprende:
    - apparecchiature dello stallo trasformatore;
    - relè di protezione.
    """

    return (
        *TRANSFORMER_BAY_EQUIPMENT,
        *PROTECTION_EQUIPMENT,
    )


def recognize_entity_role(
    entity: ProjectEntity,
    definitions: Iterable[EquipmentDefinition],
) -> EquipmentRole | None:
    """
    Cerca di riconoscere il ruolo elettrico di un'entità.

    Esempio:

        entity.name = "Interruttore 152 AT-TR"

    diventa:

        EquipmentRole.HV_TRANSFORMER_CIRCUIT_BREAKER
    """

    for definition in definitions:
        # Evita di confrontare apparecchiature appartenenti
        # a tipi diversi.
        if entity.entity_type != definition.entity_type:
            continue

        if matches_alias(
            entity_name=entity.name,
            aliases=definition.aliases,
        ):
            return definition.role

    return None


def build_role_map(
    entities: Iterable[ProjectEntity],
) -> dict[EquipmentRole, ProjectEntity]:
    """
    Costruisce una mappa tra ruolo elettrico ed entità del database.

    Esempio:

        {
            EquipmentRole.LINE_CIRCUIT_BREAKER: <152 L>,
            EquipmentRole.POWER_TRANSFORMER: <TR1>,
            EquipmentRole.TRANSFORMER_PROTECTION_RELAY: <DV7500>,
        }

    Questa prima versione assegna una sola entità a ogni ruolo.
    """

    definitions = get_equipment_definitions()

    role_map: dict[
        EquipmentRole,
        ProjectEntity,
    ] = {}

    for entity in entities:
        role = recognize_entity_role(
            entity=entity,
            definitions=definitions,
        )

        if role is None:
            continue

        # Mantiene la prima entità riconosciuta per quel ruolo.
        # In seguito passeremo a una lista per gestire più stalli.
        role_map.setdefault(role, entity)

    return role_map


def create_topology_relation(
    db: Session,
    source: ProjectEntity,
    target: ProjectEntity,
    connection: TopologyConnection,
) -> EntityRelation:
    """
    Crea una relazione topologica evitando duplicati.
    """

    if source.id == target.id:
        raise ValueError(
            "An entity cannot be related to itself."
        )

    if source.project_id != target.project_id:
        raise ValueError(
            "Entities from different projects cannot be related."
        )

    statement = select(EntityRelation).where(
        EntityRelation.source_entity_id == source.id,
        EntityRelation.target_entity_id == target.id,
        EntityRelation.relation_type == connection.relation_type,
    )

    existing_relation = db.scalar(statement)

    if existing_relation is not None:
        return existing_relation

    relation = EntityRelation(
        project_id=source.project_id,
        source_entity_id=source.id,
        target_entity_id=target.id,
        relation_type=connection.relation_type,
    )

    db.add(relation)
    db.flush()

    return relation


def apply_connections(
    db: Session,
    role_map: dict[EquipmentRole, ProjectEntity],
    connections: Iterable[TopologyConnection],
) -> list[EntityRelation]:
    """
    Applica una serie di connessioni previste dal template.

    Una relazione viene creata soltanto quando sono state trovate
    entrambe le apparecchiature.
    """

    relations: list[EntityRelation] = []

    for connection in connections:
        source = role_map.get(connection.source_role)
        target = role_map.get(connection.target_role)

        # Se uno dei due elementi non è presente nei documenti,
        # la connessione non viene creata.
        if source is None or target is None:
            continue

        relation = create_topology_relation(
            db=db,
            source=source,
            target=target,
            connection=connection,
        )

        relations.append(relation)

    return relations


def build_substation_topology(
    db: Session,
    project_id: int,
) -> list[EntityRelation]:
    """
    Costruisce la topologia elettrica del progetto.

    Fasi:
    1. carica tutte le entità del progetto;
    2. riconosce il ruolo elettrico di ogni entità;
    3. crea le connessioni dello stallo trasformatore;
    4. crea le associazioni con i relè di protezione;
    5. salva tutto con una sola commit.
    """

    entities = get_project_entities(
        db=db,
        project_id=project_id,
    )

    if not entities:
        return []

    role_map = build_role_map(entities)

    relations: list[EntityRelation] = []

    relations.extend(
        apply_connections(
            db=db,
            role_map=role_map,
            connections=TRANSFORMER_BAY_CONNECTIONS,
        )
    )

    relations.extend(
        apply_connections(
            db=db,
            role_map=role_map,
            connections=PROTECTION_CONNECTIONS,
        )
    )

    db.commit()

    for relation in relations:
        db.refresh(relation)

    return relations