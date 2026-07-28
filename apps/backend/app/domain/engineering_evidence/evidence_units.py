"""
The unit catalogue (Milestone 28.1) - the **one** place a unit is
defined for evidence extraction.

Deliberately tiny. This is not a unit-conversion engine and must never
become one: it declares the handful of units the supported evidence types
actually use, the textual variants those units are written in, and the
two or three conversions that are exact.

For each unit:

- **canonical symbol** - the one spelling stored;
- **accepted variants** - what a document might actually write;
- **compatible evidence type** - so a current rule cannot match a
  voltage;
- **scale**, only where the conversion is exact and declared here.

## What is deliberately absent

- **No inferred units.** A bare ``630`` next to the word "potenza" is not
  a power value. Nothing here looks at neighbouring text to guess a
  missing unit, because that guess would be indistinguishable from a
  measurement once stored.
- **No lossy conversion.** kV to V is exact (a factor of 1000 on a
  ``Decimal``). Nothing converts mm² to anything, because there is
  nothing exact to convert it to.
- **No case-insensitive matching.** ``mV``, ``kV`` and ``MV`` are three
  different quantities, and folding case here would silently turn a
  millivolt into a megavolt. Variants are matched exactly as written.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.engineering_evidence.evidence_models import EvidenceType


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """
    One unit this system recognises.

    ``scale_to_base`` is the exact factor from this unit to
    ``base_symbol``. ``None`` means no conversion is declared - the
    quantity is stored in the unit it was written in, and no base value
    is invented.
    """

    canonical_symbol: str
    evidence_type: EvidenceType
    variants: tuple[str, ...]
    base_symbol: str | None = None
    scale_to_base: Decimal | None = None

    @property
    def is_convertible(self) -> bool:
        return self.scale_to_base is not None


# The catalogue. Variants are matched **exactly** - no case folding.
#
# The superscript and the ASCII spellings of a cable section are both
# listed, and both map to the canonical ``mm²``. This is the one place
# where two spellings are treated as the same unit, and it is safe
# because it is declared here rather than inferred: the evidence item
# still records the original text, so `240 mm²` and `240 mm2` remain
# distinguishable to anyone who reads it.
UNIT_DEFINITIONS: tuple[UnitDefinition, ...] = (
    UnitDefinition(
        canonical_symbol="V",
        evidence_type=EvidenceType.VOLTAGE_VALUE,
        variants=("V", "v", "Volt", "volt", "VOLT"),
    ),
    UnitDefinition(
        canonical_symbol="kV",
        evidence_type=EvidenceType.VOLTAGE_VALUE,
        variants=("kV", "KV", "kv"),
        base_symbol="V",
        scale_to_base=Decimal("1000"),
    ),
    UnitDefinition(
        canonical_symbol="A",
        evidence_type=EvidenceType.CURRENT_VALUE,
        variants=("A", "Ampere", "ampere", "AMPERE"),
    ),
    UnitDefinition(
        canonical_symbol="kA",
        evidence_type=EvidenceType.CURRENT_VALUE,
        variants=("kA", "KA", "ka"),
        base_symbol="A",
        scale_to_base=Decimal("1000"),
    ),
    UnitDefinition(
        canonical_symbol="VA",
        evidence_type=EvidenceType.POWER_VALUE,
        variants=("VA", "va"),
    ),
    UnitDefinition(
        canonical_symbol="kVA",
        evidence_type=EvidenceType.POWER_VALUE,
        variants=("kVA", "KVA", "kva"),
        base_symbol="VA",
        scale_to_base=Decimal("1000"),
    ),
    UnitDefinition(
        canonical_symbol="MVA",
        evidence_type=EvidenceType.POWER_VALUE,
        variants=("MVA", "Mva", "mva"),
        base_symbol="VA",
        scale_to_base=Decimal("1000000"),
    ),
    UnitDefinition(
        canonical_symbol="mm²",
        evidence_type=EvidenceType.CABLE_SECTION_VALUE,
        variants=("mm²", "mm2", "MM²", "MM2"),
    ),
)

# Built once at import, from the catalogue above - never a second table
# somebody has to remember to update.
_VARIANT_INDEX: dict[str, UnitDefinition] = {
    variant: definition
    for definition in UNIT_DEFINITIONS
    for variant in definition.variants
}


def find_unit(text: str) -> UnitDefinition | None:
    """
    The unit this text denotes, or ``None`` if it denotes none.

    Exact match against the declared variants. A token this catalogue
    does not know is not a unit - it is not "probably" a unit, and no
    fuzzy match is attempted.
    """

    return _VARIANT_INDEX.get(text)


def units_for(evidence_type: EvidenceType) -> tuple[UnitDefinition, ...]:
    return tuple(
        definition
        for definition in UNIT_DEFINITIONS
        if definition.evidence_type is evidence_type
    )


def convert_to_base(
    value: Decimal, definition: UnitDefinition
) -> tuple[Decimal, str] | None:
    """
    The value in the declared base unit, when the catalogue declares an
    exact conversion.

    ``None`` where it does not. A caller must not fall back to "assume
    the same number" - a cable section in mm² has no base unit here, and
    pretending otherwise would put a fabricated figure in the record.
    """

    if not definition.is_convertible:
        return None

    return value * definition.scale_to_base, definition.base_symbol
