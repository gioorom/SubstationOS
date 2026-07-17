import re
from dataclasses import dataclass

from app.models.knowledge_graph import EntityType


@dataclass(slots=True, frozen=True)
class ExtractedEntity:
    entity_type: EntityType
    name: str
    confidence: float = 1.0


ENTITY_PATTERNS: dict[EntityType, list[str]] = {
    EntityType.CIRCUIT_BREAKER: [
        r"\bCB[- ]?\d+\b",
        r"\b52[- ]?\d+\b",
    ],
    EntityType.DISCONNECTOR: [
        r"\bDS[- ]?\d+\b",
        r"\b89[- ]?\d+\b",
    ],
    EntityType.TRANSFORMER: [
        r"\bTR[- ]?\d+\b",
        r"\bT\d+\b",
    ],
    EntityType.CURRENT_TRANSFORMER: [
        r"\bCT[- ]?\d+\b",
    ],
    EntityType.VOLTAGE_TRANSFORMER: [
        r"\bVT[- ]?\d+\b",
    ],
    EntityType.BAY: [
        r"\bBAY[- ]?\d+\b",
        r"\bFEEDER[- ]?\d+\b",
    ],
    EntityType.PANEL: [
        r"\bPANEL[- ]?[A-Z]?\d+\b",
    ],
    EntityType.PROTECTION_RELAY: [
        r"\bREF615\b",
        r"\bREG670\b",
        r"\bREL670\b",
        r"\bRET670\b",
        r"\bSEL[- ]?\d+\b",
    ],
    EntityType.CABLE: [
        r"\bCABLE[- ]?[A-Z0-9]+\b",
    ],
}


COMPILED_PATTERNS: dict[EntityType, list[re.Pattern[str]]] = {
    entity_type: [
        re.compile(pattern, re.IGNORECASE)
        for pattern in patterns
    ]
    for entity_type, patterns in ENTITY_PATTERNS.items()
}


def normalize_entity_name(
    entity_type: EntityType,
    raw_name: str,
) -> str:
    name = " ".join(raw_name.strip().upper().split())

    if entity_type == EntityType.BAY:
        name = re.sub(r"^BAY[- ]?", "BAY ", name)
        return name

    if name.startswith("FEEDER"):
        return re.sub(r"^FEEDER[- ]?", "FEEDER ", name)

    if entity_type == EntityType.PANEL:
        return re.sub(r"^PANEL[- ]?", "PANEL ", name)

    return re.sub(r"[- ]", "", name)


def extract_entities(text: str) -> list[ExtractedEntity]:
    if not text or not text.strip():
        return []

    extracted: dict[
        tuple[EntityType, str],
        ExtractedEntity,
    ] = {}

    for entity_type, patterns in COMPILED_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                normalized_name = normalize_entity_name(
                    entity_type=entity_type,
                    raw_name=match.group(0),
                )

                key = (entity_type, normalized_name)

                extracted[key] = ExtractedEntity(
                    entity_type=entity_type,
                    name=normalized_name,
                    confidence=1.0,
                )

    return sorted(
        extracted.values(),
        key=lambda entity: (
            entity.entity_type.value,
            entity.name,
        ),
    )