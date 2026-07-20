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
        # Interruttori specifici della topologia
        r"\b152\s*AT\s*[-–]?\s*TR\b",
        r"\b152\s*L\b",
        r"\b52\s*MT\s*[-–]?\s*TR\b",
        r"\b52\s*MT\s*(?:LINEA|FEEDER)?\s*\d+\b",

        # Denominazioni generiche
        r"\bCB\s*[-–]?\s*\d+\b",
        r"\b52\s*[-–]?\s*\d+\b",
    ],

    EntityType.DISCONNECTOR: [
        # Sezionatori specifici della topologia
        r"\b189\s*SB\s*[-–]?\s*TR\b",
        r"\b189\s*SB\s*[-–]?\s*L\b",
        r"\b189\s*SS\b",
        r"\b189\s*L\b",

        # Denominazioni generiche
        r"\bDS\s*[-–]?\s*\d+\b",
        r"\b89\s*[-–]?\s*\d+\b",
        r"\b189\s*[-–]?\s*\d+\b",
    ],

    EntityType.TRANSFORMER: [
        r"\bTRASFORMATORE\s+AT\s*[-–/]?\s*MT\b",
        r"\bTRASFORMATORE\s+DI\s+POTENZA\b",
        r"\bPOWER\s+TRANSFORMER\b",
        r"\bTR\s*[-–]?\s*\d+\b",
        r"\bT\d+\b",
    ],

    EntityType.CURRENT_TRANSFORMER: [
        r"\bTA\s+AT\s+LINEA\b",
        r"\bTA\s+AT\s+TR\b",
        r"\bTA\s+MT\s+TR\b",
        r"\bCT\s*[-–]?\s*\d+\b",
    ],

    EntityType.VOLTAGE_TRANSFORMER: [
        r"\bTV\s+LINEA\s+AT\b",
        r"\bTV\s+AT\s+LINEA\b",
        r"\bTV\s+MT\s+TR\b",
        r"\bVT\s*[-–]?\s*\d+\b",
    ],

    EntityType.BAY: [
        r"\bBAY\s*[-–]?\s*\d+\b",
        r"\bFEEDER\s*[-–]?\s*\d+\b",
    ],

    EntityType.PANEL: [
        r"\bPANEL\s*[-–]?\s*[A-Z]?\d+\b",
    ],

    EntityType.PROTECTION_RELAY: [
        # Protezioni della topologia
        r"\bDV7036\b",
        r"\bDV7500\b",
        r"\bDV901A3\b",

        # Protezioni generiche
        r"\bREF615\b",
        r"\bREG670\b",
        r"\bREL670\b",
        r"\bRET670\b",
        r"\bSEL\s*[-–]?\s*\d+\b",
    ],

    EntityType.CABLE: [
        r"\bCABLE\s*[-–]?\s*[A-Z0-9]+\b",
    ],

    EntityType.OTHER: [
        r"\bLINEA\s+AT\b",
        r"\bSARRA\s+MT\b",
        r"\bSBARRA\s+MT\b",
        r"\bSBARRE\s+MT\b",
        r"\bCONGIUNTORE\s+MT\b",
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
    """
    Normalizza il nome senza eliminare le informazioni necessarie
    al riconoscimento topologico.
    """

    name = raw_name.strip().upper()

    name = name.replace("–", "-")
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s*/\s*", "-", name)

    canonical_names = {
        "152L": "152 L",
        "152 L": "152 L",
        "152AT-TR": "152 AT-TR",
        "152 AT-TR": "152 AT-TR",
        "52MT-TR": "52 MT-TR",
        "52 MT-TR": "52 MT-TR",

        "189L": "189 L",
        "189 L": "189 L",
        "189SB-L": "189 SB-L",
        "189 SB-L": "189 SB-L",
        "189SB-TR": "189 SB-TR",
        "189 SB-TR": "189 SB-TR",
        "189SS": "189 SS",
        "189 SS": "189 SS",

        "TA AT LINEA": "TA AT Linea",
        "TA AT TR": "TA AT TR",
        "TA MT TR": "TA MT TR",

        "TV LINEA AT": "TV Linea AT",
        "TV AT LINEA": "TV Linea AT",
        "TV MT TR": "TV MT TR",

        "LINEA AT": "Linea AT",
        "SBARRA MT": "Sbarra MT",
        "SBARRE MT": "Sbarra MT",
        "SARRA MT": "Sbarra MT",

        "TRASFORMATORE AT-MT": "Trasformatore AT-MT",
        "TRASFORMATORE DI POTENZA": "Trasformatore AT-MT",
        "POWER TRANSFORMER": "Trasformatore AT-MT",

        "CONGIUNTORE MT": "Congiuntore MT",
    }

    compact_name = name.replace(" ", "")

    if name in canonical_names:
        return canonical_names[name]

    if compact_name in canonical_names:
        return canonical_names[compact_name]

    if entity_type == EntityType.BAY:
        name = re.sub(
            r"^BAY\s*-?\s*",
            "BAY ",
            name,
        )
        name = re.sub(
            r"^FEEDER\s*-?\s*",
            "FEEDER ",
            name,
        )
        return name

    if entity_type == EntityType.PANEL:
        return re.sub(
            r"^PANEL\s*-?\s*",
            "PANEL ",
            name,
        )

    if entity_type == EntityType.PROTECTION_RELAY:
        return name.replace(" ", "").replace("-", "")

    if re.fullmatch(r"(CB|CT|VT|DS)\s*-?\s*\d+", name):
        return re.sub(r"[\s-]+", "", name)

    if re.fullmatch(r"SEL\s*-?\s*\d+", name):
        return re.sub(r"[\s-]+", "", name)

    if re.fullmatch(r"TR\s*-?\s*\d+", name):
        return re.sub(r"[\s-]+", "", name)

    return name


def extract_entities(text: str) -> list[ExtractedEntity]:
    """
    Estrae tutte le apparecchiature riconosciute dal testo.
    """

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

                key = (
                    entity_type,
                    normalized_name.casefold(),
                )

                extracted[key] = ExtractedEntity(
                    entity_type=entity_type,
                    name=normalized_name,
                    confidence=1.0,
                )

    return sorted(
        extracted.values(),
        key=lambda entity: (
            entity.entity_type.value,
            entity.name.casefold(),
        ),
    )