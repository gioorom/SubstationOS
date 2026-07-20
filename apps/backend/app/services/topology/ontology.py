from dataclasses import dataclass
from enum import Enum

from app.models.knowledge_graph import (
    EntityType,
    RelationType,
)


class EquipmentRole(str, Enum):
    """Ruolo funzionale di un elemento nella topologia elettrica."""

    HV_LINE = "hv_line"
    LINE_VOLTAGE_TRANSFORMER = "line_voltage_transformer"
    LINE_DISCONNECTOR = "line_disconnector"
    LINE_CURRENT_TRANSFORMER = "line_current_transformer"
    LINE_CIRCUIT_BREAKER = "line_circuit_breaker"

    LINE_SIDE_BUS_DISCONNECTOR = (
        "line_side_bus_disconnector"
    )
    TRANSFORMER_SIDE_BUS_DISCONNECTOR = (
        "transformer_side_bus_disconnector"
    )

    HV_TRANSFORMER_CIRCUIT_BREAKER = (
        "hv_transformer_circuit_breaker"
    )
    HV_TRANSFORMER_CURRENT_TRANSFORMER = (
        "hv_transformer_current_transformer"
    )

    POWER_TRANSFORMER = "power_transformer"

    MV_TRANSFORMER_CURRENT_TRANSFORMER = (
        "mv_transformer_current_transformer"
    )
    MV_TRANSFORMER_VOLTAGE_TRANSFORMER = (
        "mv_transformer_voltage_transformer"
    )
    MV_TRANSFORMER_CIRCUIT_BREAKER = (
        "mv_transformer_circuit_breaker"
    )

    MV_BUSBAR = "mv_busbar"
    MV_FEEDER_CIRCUIT_BREAKER = (
        "mv_feeder_circuit_breaker"
    )
    MV_OUTGOING_LINE = "mv_outgoing_line"

    HV_BUS_SECTION_DISCONNECTOR = (
        "hv_bus_section_disconnector"
    )
    MV_BUS_COUPLER = "mv_bus_coupler"

    LINE_PROTECTION_RELAY = "line_protection_relay"
    TRANSFORMER_PROTECTION_RELAY = (
        "transformer_protection_relay"
    )
    MV_FEEDER_PROTECTION_RELAY = (
        "mv_feeder_protection_relay"
    )


@dataclass(frozen=True)
class EquipmentDefinition:
    """
    Definisce un elemento atteso nella topologia.

    aliases contiene le forme testuali che possono essere
    trovate nei documenti tecnici.
    """

    role: EquipmentRole
    entity_type: EntityType
    display_name: str
    aliases: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class TopologyConnection:
    """Connessione logica attesa fra due ruoli."""

    source_role: EquipmentRole
    target_role: EquipmentRole
    relation_type: RelationType


def normalize_equipment_name(value: str) -> str:
    """
    Normalizza una denominazione per confronti robusti.

    Esempi:
    - "152 AT-TR" -> "152 at tr"
    - "189SB-L"   -> "189sb l"
    """

    normalized = value.strip().lower()

    for character in ("-", "_", "/", "\\", ".", ",", "(", ")"):
        normalized = normalized.replace(character, " ")

    return " ".join(normalized.split())


def matches_alias(
    entity_name: str,
    aliases: tuple[str, ...],
) -> bool:
    """Verifica se il nome di un’entità corrisponde a un alias."""

    normalized_name = normalize_equipment_name(entity_name)

    return any(
        normalize_equipment_name(alias) in normalized_name
        for alias in aliases
    )