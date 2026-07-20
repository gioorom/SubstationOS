from app.models.knowledge_graph import (
    EntityType,
    RelationType,
)

from app.services.topology.ontology import (
    EquipmentDefinition,
    EquipmentRole,
    TopologyConnection,
)


TRANSFORMER_BAY_EQUIPMENT: tuple[
    EquipmentDefinition,
    ...
] = (
    EquipmentDefinition(
        role=EquipmentRole.HV_LINE,
        entity_type=EntityType.OTHER,
        display_name="Linea AT",
        aliases=(
            "linea at",
            "line at",
            "linea alta tensione",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.LINE_VOLTAGE_TRANSFORMER,
        entity_type=EntityType.VOLTAGE_TRANSFORMER,
        display_name="TV Linea AT",
        aliases=(
            "tv linea",
            "tv at linea",
            "tv linea at",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.LINE_DISCONNECTOR,
        entity_type=EntityType.DISCONNECTOR,
        display_name="Sezionatore di linea 189 L",
        aliases=(
            "189 l",
            "189l",
            "sezionatore di linea",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.LINE_CURRENT_TRANSFORMER,
        entity_type=EntityType.CURRENT_TRANSFORMER,
        display_name="TA AT Linea",
        aliases=(
            "ta at linea",
            "ta linea at",
            "ta linea",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.LINE_CIRCUIT_BREAKER,
        entity_type=EntityType.CIRCUIT_BREAKER,
        display_name="Interruttore di linea 152 L",
        aliases=(
            "152 l",
            "152l",
            "152 l at",
            "152 linea",
            "interruttore di linea",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.LINE_SIDE_BUS_DISCONNECTOR,
        entity_type=EntityType.DISCONNECTOR,
        display_name="Sezionatore di sbarre 189 SB-L",
        aliases=(
            "189 sb l",
            "189sb l",
            "189sb-l",
            "sezionatore sbarre lato linea",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.TRANSFORMER_SIDE_BUS_DISCONNECTOR,
        entity_type=EntityType.DISCONNECTOR,
        display_name="Sezionatore di sbarre 189 SB-TR",
        aliases=(
            "189 sb tr",
            "189sb tr",
            "189sb-tr",
            "sezionatore sbarre lato tr",
            "sezionatore sbarre lato trasformatore",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.HV_TRANSFORMER_CIRCUIT_BREAKER,
        entity_type=EntityType.CIRCUIT_BREAKER,
        display_name="Interruttore di macchina 152 AT-TR",
        aliases=(
            "152 at tr",
            "152 at-tr",
            "152 tr at",
            "interruttore di macchina at",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.HV_TRANSFORMER_CURRENT_TRANSFORMER,
        entity_type=EntityType.CURRENT_TRANSFORMER,
        display_name="TA AT TR",
        aliases=(
            "ta at tr",
            "ta at trasformatore",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.POWER_TRANSFORMER,
        entity_type=EntityType.TRANSFORMER,
        display_name="Trasformatore AT-MT",
        aliases=(
            "trasformatore at mt",
            "trasformatore at-mt",
            "trasformatore di potenza",
            "power transformer",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.MV_TRANSFORMER_CURRENT_TRANSFORMER,
        entity_type=EntityType.CURRENT_TRANSFORMER,
        display_name="TA MT TR",
        aliases=(
            "ta mt tr",
            "ta mt trasformatore",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.MV_TRANSFORMER_VOLTAGE_TRANSFORMER,
        entity_type=EntityType.VOLTAGE_TRANSFORMER,
        display_name="TV MT TR",
        aliases=(
            "tv mt tr",
            "tv mt trasformatore",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.MV_TRANSFORMER_CIRCUIT_BREAKER,
        entity_type=EntityType.CIRCUIT_BREAKER,
        display_name="Interruttore di macchina 52 MT-TR",
        aliases=(
            "52 mt tr",
            "52 mt-tr",
            "52 tr",
            "interruttore di macchina mt",
        ),
    ),
    EquipmentDefinition(
        role=EquipmentRole.MV_BUSBAR,
        entity_type=EntityType.OTHER,
        display_name="Sbarra MT",
        aliases=(
            "sbarra mt",
            "sbarre mt",
            "sbarra rossa",
            "sbarra blu",
            "sistema di sbarre mt",
        ),
    ),
)


TRANSFORMER_BAY_CONNECTIONS: tuple[
    TopologyConnection,
    ...
] = tuple(
    TopologyConnection(
        source_role=source.role,
        target_role=target.role,
        relation_type=RelationType.CONNECTED_TO,
    )
    for source, target in zip(
        TRANSFORMER_BAY_EQUIPMENT,
        TRANSFORMER_BAY_EQUIPMENT[1:],
    )
)


PROTECTION_EQUIPMENT: tuple[
    EquipmentDefinition,
    ...
] = (
    EquipmentDefinition(
        role=EquipmentRole.LINE_PROTECTION_RELAY,
        entity_type=EntityType.PROTECTION_RELAY,
        display_name="DV7036",
        aliases=(
            "dv7036",
            "protezione distanziometrica dv7036",
        ),
        required=False,
    ),
    EquipmentDefinition(
        role=EquipmentRole.TRANSFORMER_PROTECTION_RELAY,
        entity_type=EntityType.PROTECTION_RELAY,
        display_name="DV7500",
        aliases=(
            "dv7500",
            "protezione tr dv7500",
            "protezione trasformatore dv7500",
        ),
        required=False,
    ),
    EquipmentDefinition(
        role=EquipmentRole.MV_FEEDER_PROTECTION_RELAY,
        entity_type=EntityType.PROTECTION_RELAY,
        display_name="DV901A3",
        aliases=(
            "dv901a3",
            "protezione linea mt dv901a3",
        ),
        required=False,
    ),
)


PROTECTION_CONNECTIONS: tuple[
    TopologyConnection,
    ...
] = (
    TopologyConnection(
        source_role=EquipmentRole.LINE_CIRCUIT_BREAKER,
        target_role=EquipmentRole.LINE_PROTECTION_RELAY,
        relation_type=RelationType.PROTECTED_BY,
    ),
    TopologyConnection(
        source_role=(
            EquipmentRole.HV_TRANSFORMER_CIRCUIT_BREAKER
        ),
        target_role=(
            EquipmentRole.TRANSFORMER_PROTECTION_RELAY
        ),
        relation_type=RelationType.PROTECTED_BY,
    ),
    TopologyConnection(
        source_role=(
            EquipmentRole.MV_TRANSFORMER_CIRCUIT_BREAKER
        ),
        target_role=(
            EquipmentRole.TRANSFORMER_PROTECTION_RELAY
        ),
        relation_type=RelationType.PROTECTED_BY,
    ),
)