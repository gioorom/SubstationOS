"""
The extraction rule catalogue (Milestone 28.1) - the **one**
authoritative list of what this system knows how to observe.

Each rule declares four policies, and every one of them is data rather
than code hidden in the extractor:

| Policy | Answers |
|---|---|
| matching | which token or tokens can start a candidate |
| normalization | how the matched text becomes a typed value |
| validation | whether the result is `OBSERVED`, `AMBIGUOUS` or `REJECTED` |
| versioning | which rule, at which version, produced an item |

**Rule versions are part of every stored evidence item.** When a rule
changes, the items it produced before keep saying which rule produced
them, and a re-extraction under the new version creates a new evidence
set rather than rewriting the old one. That is what makes a conclusion
drawn last year still explainable.

The extractor orchestrates these rules and contains no matching logic of
its own - asserted by architecture test, because an inline `if` in the
extractor would be a rule nobody could find, version or review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_evidence.evidence_patterns import (
    DESIGNATION_IEC_81346_COMPOUND,
    DESIGNATION_PATTERNS,
)

# Punctuation running text attaches to a value. Deliberately does not
# include ``+`` or ``-``: those carry meaning in IEC 81346 designations
# and in signed values, and stripping them would change what was
# observed.
_BOUNDARY_PUNCTUATION = "()[]{}\"'.,;:!?"


class RuleKind(str, Enum):
    """
    How a rule consumes tokens.

    Each kind is a shape of provenance the extractor knows how to record
    exactly, and adding one is a deliberate act for that reason: a kind
    nobody taught the extractor to locate would produce evidence
    pointing at the wrong characters.
    """

    # One token, matched whole: "T1".
    SINGLE_TOKEN = "single_token"
    # A numeric token optionally followed by a unit token: "20 kV", or
    # one token carrying both: "20kV".
    QUANTITY = "quantity"
    # A declared **segment** of one token: the location aspect of a
    # compound IEC 81346 reference designation. Its own kind because the
    # provenance shape differs from the other two - the observation
    # covers part of a token, so the extractor must narrow the character
    # range rather than take the token's own.
    LOCATION_ASPECT = "location_aspect"


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    """
    One rule, identified and versioned.

    ``rule_id`` is a stable contract: once published it appears in stored
    evidence, so renaming it is a migration rather than an edit.
    ``rule_version`` changes whenever the rule's behaviour changes - a
    new pattern, a different validation - and a version bump is what
    causes a document to be re-extracted rather than silently
    reinterpreted.
    """

    rule_id: str
    rule_version: str
    evidence_type: EvidenceType
    kind: RuleKind
    description: str


DESIGNATION_RULE = ExtractionRule(
    rule_id="designation_generic",
    rule_version="1.0",
    evidence_type=EvidenceType.DESIGNATION,
    kind=RuleKind.SINGLE_TOKEN,
    description=(
        "A token whose whole text matches one of the declared "
        "designation shapes: letters-then-digits (T1, QMT01), a numeric "
        "function code (52-Q1), or an IEC 81346 aspect (+E01-QA1). "
        "Records only that designation-like text was observed; says "
        "nothing about what equipment it names."
    ),
)

VOLTAGE_RULE = ExtractionRule(
    rule_id="voltage_value",
    rule_version="1.0",
    evidence_type=EvidenceType.VOLTAGE_VALUE,
    kind=RuleKind.QUANTITY,
    description="A number followed by a declared voltage unit (V, kV).",
)

CURRENT_RULE = ExtractionRule(
    rule_id="current_value",
    rule_version="1.0",
    evidence_type=EvidenceType.CURRENT_VALUE,
    kind=RuleKind.QUANTITY,
    description="A number followed by a declared current unit (A, kA).",
)

POWER_RULE = ExtractionRule(
    rule_id="power_value",
    rule_version="1.0",
    evidence_type=EvidenceType.POWER_VALUE,
    kind=RuleKind.QUANTITY,
    description=(
        "A number followed by a declared apparent-power unit "
        "(VA, kVA, MVA)."
    ),
)

CABLE_SECTION_RULE = ExtractionRule(
    rule_id="cable_section_value",
    rule_version="1.0",
    evidence_type=EvidenceType.CABLE_SECTION_VALUE,
    kind=RuleKind.QUANTITY,
    description=(
        "A number followed by a declared cross-section unit (mm²). "
        "Records the section as written; says nothing about which cable "
        "it belongs to."
    ),
)

LOCATION_ASPECT_RULE = ExtractionRule(
    rule_id="location_aspect_iec_81346",
    rule_version="1.0",
    evidence_type=EvidenceType.LOCATION_ASPECT,
    kind=RuleKind.LOCATION_ASPECT,
    description=(
        "The location-aspect segment of a compound IEC 81346 reference "
        "designation written as one token: the '+E01' of '+E01-QA1'. "
        "Records only that a location aspect was written there - not "
        "that the equipment is located in it, which is a meaning a "
        "semantic rule assigns and an engineer reviews."
    ),
)

# The catalogue, in execution order. Quantity rules are indistinguishable
# from one another at match time - the unit decides which one applies -
# so their order is irrelevant; the designation rule runs first only so
# that a reader of a result sees designations before quantities.
EXTRACTION_RULES: tuple[ExtractionRule, ...] = (
    DESIGNATION_RULE,
    VOLTAGE_RULE,
    CURRENT_RULE,
    POWER_RULE,
    CABLE_SECTION_RULE,
    LOCATION_ASPECT_RULE,
)

RULES_BY_ID: dict[str, ExtractionRule] = {
    rule.rule_id: rule for rule in EXTRACTION_RULES
}

QUANTITY_RULE_BY_TYPE: dict[EvidenceType, ExtractionRule] = {
    rule.evidence_type: rule
    for rule in EXTRACTION_RULES
    if rule.kind is RuleKind.QUANTITY
}


@dataclass(frozen=True, slots=True)
class TrimmedToken:
    """
    A token with its surrounding punctuation removed, and how much was
    removed from each end.

    The offsets matter: they let the extractor narrow a token's character
    provenance to the characters that actually produced the evidence, so
    ``400 V,`` yields evidence whose range covers ``400 V`` and not the
    comma. Without them the trimming would be a small, permanent lie
    about where the observation came from.
    """

    text: str
    left: int
    right: int


def strip_boundary_punctuation(text: str) -> TrimmedToken:
    """
    The one trimming policy in this context, applied to designations,
    numbers and units alike.

    Running text attaches punctuation to engineering values constantly -
    ``(T1),`` and ``400 V,`` and ``20 kV;``. Stripping it is declared
    here rather than done ad hoc at each call site, and it only ever
    removes characters from the **ends**: an internal separator, as in
    ``1,250``, is untouched because it may be part of the number.
    """

    stripped = text.strip(_BOUNDARY_PUNCTUATION)

    if not stripped:
        return TrimmedToken(text="", left=0, right=0)

    return TrimmedToken(
        text=stripped,
        left=len(text) - len(text.lstrip(_BOUNDARY_PUNCTUATION)),
        right=len(text) - len(text.rstrip(_BOUNDARY_PUNCTUATION)),
    )


def matches_designation(text: str) -> bool:
    """
    The designation rule's matching policy.

    Lives here rather than in the extractor so that the whole of what
    "is a designation" means is readable in one file, alongside the
    patterns it uses.
    """

    return any(pattern.match(text) for pattern in DESIGNATION_PATTERNS)


def match_location_aspect(text: str) -> tuple[str, int] | None:
    """
    The location-aspect rule's matching policy.

    Returns the location segment and how many characters follow it, or
    ``None`` when the token is not a compound IEC 81346 reference
    designation carrying a location aspect.

    The trailing length is returned rather than computed by the caller
    because it is what narrows the observation's character provenance
    onto ``+E01`` - and provenance that the extractor derived for itself
    is exactly the kind that quietly becomes approximate.

    ``-QA1-XB2`` returns ``None``. It is a product within a product,
    which is a different engineering statement that no rule here
    interprets.
    """

    match = DESIGNATION_IEC_81346_COMPOUND.match(text)

    if match is None:
        return None

    return match.group("location"), len(match.group("product"))
