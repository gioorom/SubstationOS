"""
Deterministic normalization rules for Canonicalization (ADR-0002's
"canonical, not fuzzy" discipline extended to project knowledge). Every
function here is a pure string transform against a small, explicit,
hand-authored vocabulary - never fuzzy matching, semantic similarity,
embeddings, or AI. An input this module does not recognize is rejected
with a typed exception, never guessed at.

The entity-type and predicate vocabularies below are provisional and
self-contained to this bounded context - they are NOT the Canonical
Domain (``app/domain/ontology/**``) and do not replace it. Aligning
canonical entity types with real ``EquipmentDefinition`` ids and
aliases is a deliberate future integration point (see this module's
governing milestone report), out of scope here because it was
explicitly excluded from this milestone's required reading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.canonicalization.canonicalization_exceptions import (
    UnknownCanonicalEntityTypeError,
    UnknownCanonicalPredicateError,
    UnrecognizedEntityReferenceError,
)
from app.domain.canonicalization.canonicalization_models import (
    CanonicalAttribute,
    CanonicalEntityReference,
    CanonicalPredicate,
    CanonicalValue,
)


@dataclass(frozen=True, slots=True)
class _EntityTypeDefinition:
    type_name: str
    short_code: str
    synonyms: frozenset[str]


_ENTITY_TYPE_REGISTRY: tuple[_EntityTypeDefinition, ...] = (
    _EntityTypeDefinition("CABLE", "C", frozenset({"cable", "c"})),
    _EntityTypeDefinition(
        "TRANSFORMER", "TR", frozenset({"transformer", "tr"})
    ),
    _EntityTypeDefinition("BREAKER", "CB", frozenset({"breaker", "cb"})),
    _EntityTypeDefinition("RELAY", "RELAY", frozenset({"relay"})),
    _EntityTypeDefinition(
        "CABINET", "CAB", frozenset({"cabinet", "frame", "cab"})
    ),
    _EntityTypeDefinition("SWITCH", "SW", frozenset({"switch", "sw"})),
    _EntityTypeDefinition("BUSBAR", "BUS", frozenset({"busbar", "bus"})),
)

_ENTITY_TYPES_BY_SYNONYM: dict[str, _EntityTypeDefinition] = {
    synonym: definition
    for definition in _ENTITY_TYPE_REGISTRY
    for synonym in definition.synonyms
}

_ENTITY_REFERENCE_PATTERN = re.compile(
    r"^(?P<word>[A-Za-z]+)[\s\-]*(?P<number>[0-9]+)$"
)

# The minimum width a normalized identifier's numeric segment is padded
# to (e.g. "TR2" -> "TR-02"). A longer input number is preserved as-is
# (e.g. "295" stays "295"). This is a stated, adjustable convention of
# this normalizer, not a rule derived from the Canonical Domain, which
# defines no numbering-width convention today.
_MINIMUM_NUMBER_WIDTH = 2

_PREDICATE_SYNONYMS: dict[str, str] = {
    "feeds": "FEEDS",
    "supplies": "FEEDS",
    "energizes": "FEEDS",
    "installed_in": "LOCATED_IN",
    "located_in": "LOCATED_IN",
    "protects": "PROTECTS",
    "connects_to": "CONNECTS_TO",
    "contains": "CONTAINS",
}


def _normalize_key(raw: str) -> str:
    return re.sub(r"[\s\-]+", "_", raw.strip().lower())


def normalize_entity_reference(raw: str) -> CanonicalEntityReference:
    """
    Normalizes a raw entity mention (e.g. "Cable 295", "C-295", "C295")
    into a ``CanonicalEntityReference`` (``CABLE:C-295``). Raises
    ``UnrecognizedEntityReferenceError`` if ``raw`` does not have the
    shape "letters, optionally separated, then digits", and
    ``UnknownCanonicalEntityTypeError`` if the letter prefix is not a
    recognized entity type.
    """

    text = raw.strip()

    if not text:
        raise UnrecognizedEntityReferenceError(raw)

    match = _ENTITY_REFERENCE_PATTERN.match(text)

    if match is None:
        raise UnrecognizedEntityReferenceError(raw)

    word = match.group("word")
    definition = _ENTITY_TYPES_BY_SYNONYM.get(word.lower())

    if definition is None:
        raise UnknownCanonicalEntityTypeError(raw, word)

    number = match.group("number").zfill(_MINIMUM_NUMBER_WIDTH)

    return CanonicalEntityReference(
        entity_type=definition.type_name,
        canonical_id=f"{definition.short_code}-{number}",
    )


def normalize_predicate(raw: str) -> CanonicalPredicate:
    """
    Normalizes a raw relationship verb (e.g. "feeds", "supplies",
    "energizes") into its canonical form (``FEEDS``). Raises
    ``UnknownCanonicalPredicateError`` if ``raw`` is not in the
    deterministic predicate-synonym vocabulary.
    """

    canonical = _PREDICATE_SYNONYMS.get(_normalize_key(raw))

    if canonical is None:
        raise UnknownCanonicalPredicateError(raw)

    return CanonicalPredicate(value=canonical)


def normalize_attribute_name(raw: str) -> CanonicalAttribute:
    """
    Normalizes a raw attribute name into ``snake_case``, matching the
    Canonical Domain's own attribute-id convention (``CLAUDE.md`` SS7).
    Format normalization only - no synonym folding, since aligning
    against real ``AttributeDefinition`` ids is future integration work
    (see module docstring).
    """

    return CanonicalAttribute(value=_normalize_key(raw))


def normalize_value(raw: str) -> CanonicalValue:
    """
    Normalizes a raw attribute value: whitespace-trimmed only. No unit
    parsing or conversion is performed - that would require domain
    knowledge this bounded context deliberately does not consult.
    """

    return CanonicalValue(value=raw.strip())
