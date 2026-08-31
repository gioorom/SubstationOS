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
    DESIGNATION_IEC_81346_LOCATION,
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
    rule_version="2.0",
    evidence_type=EvidenceType.DESIGNATION,
    kind=RuleKind.SINGLE_TOKEN,
    description=(
        "A token whose whole text matches one of the declared "
        "designation shapes: letters-then-digits (T1, QMT01), a numeric "
        "function code (52-Q1), an IEC 81346 aspect (+E01-QA1), a "
        "product aspect (-E, -E1, -X), or a dot-qualified product "
        "aspect (-E1.L, -E.AM). Excludes standalone location aspects, "
        "which the location rule observes. Records only that "
        "designation-like text was observed; says nothing about what "
        "equipment it names, and nothing about the internal structure "
        "of a dot-qualified form."
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
    rule_version="2.0",
    evidence_type=EvidenceType.LOCATION_ASPECT,
    kind=RuleKind.LOCATION_ASPECT,
    description=(
        "An IEC 81346 location aspect, in either form the real source "
        "set writes: the '+E01' segment of a compound '+E01-QA1', or a "
        "standalone location token such as '+GSH002', '+DQ1910', "
        "'+TELAIO' or '+CELLA'. Records only that a location aspect was "
        "written there - not that any equipment is located in it, which "
        "is a meaning a semantic rule assigns and an engineer reviews, "
        "and not what kind of place it is."
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

    One exclusion, applied after the shape matches: **a standalone
    location aspect is not a designation**. ``+GSH002`` matches the IEC
    shape, but the ``+`` says it names a *place*. Recording it as
    equipment would put 268 locations into the graph as assets. The
    location rule observes it instead.

    A **compound** ``+E01-QA1`` is still a designation: it names a
    product, in a location, and only the leading segment is the place.

    ## What this policy knowingly gets wrong

    ``SF6`` is sulphur hexafluoride, and it matches
    ``DESIGNATION_LETTERS_THEN_DIGITS``. It is observed as a designation,
    16 times across the real document set, and that is a **known false
    positive** rather than an oversight.

    Two mechanisms were built and removed:

    - **A token catalogue** (``if text in ("SF6",)``) encodes "SF6 is
      never an engineering designation" as universal truth. It is not:
      nothing stops a real installation designating an object ``SF6``,
      and the catalogue would make it permanently invisible. A present
      false positive is visible and disputable; that future false
      negative would be neither.
    - **A source-context rule** rejecting the token after ``ALLARMI`` or
      ``PRESSIONE``. Its entire evidence base is two words, on four
      lines, in two documents, in one language - and it would miss
      ``GAS SF6``, a bare ``SF6`` table cell, and any non-Italian
      phrasing. That is a heuristic with a version number, which is the
      artefact this catalogue of rules exists to avoid.

    No grammar can separate the token: it is shaped exactly like the real
    designations ``MI1``, ``MO2`` and ``Q8`` in the same drawings.

    The honest fix is upstream and is **not** an extractor concern: a
    governed substance vocabulary, reviewed like every other domain
    catalogue in ``app/domain/ontology``, which this rule could then
    consult as source-authoritative classification rather than as a
    hand-curated list. Until that exists the false positive stands, is
    measured by the reference corpus, and is recorded in
    ``engineering_evidence.md``.
    """

    if not any(pattern.match(text) for pattern in DESIGNATION_PATTERNS):
        return False

    return not DESIGNATION_IEC_81346_LOCATION.match(text)


def match_location_aspect(text: str) -> tuple[str, int] | None:
    """
    The location-aspect rule's matching policy.

    Returns the location segment and how many characters follow it, or
    ``None`` when the token carries no location aspect.

    Two shapes, because the real source set writes both. A compound
    ``+E01-QA1`` yields ``("+E01", 4)`` - the location, and the length of
    the product segment that follows it. A standalone ``+GSH002`` yields
    ``("+GSH002", 0)``: the whole token is the location and nothing
    trails it.

    The standalone form is by far the commoner one in real documents -
    268 occurrences against zero compounds - which is why EPIC 32.E2
    added it. Milestone 32.P1 saw only the compound form, in one
    annotated corpus line.

    The trailing length is returned rather than computed by the caller
    because it is what narrows the observation's character provenance
    onto ``+E01`` - and provenance that the extractor derived for itself
    is exactly the kind that quietly becomes approximate.

    ``-QA1-XB2`` returns ``None``. It is a product within a product,
    which is a different engineering statement that no rule here
    interprets - and which EPIC 32.E1 found occurs zero times in 1,050
    pages of real source.
    """

    match = DESIGNATION_IEC_81346_COMPOUND.match(text)

    if match is not None:
        return match.group("location"), len(match.group("product"))

    if DESIGNATION_IEC_81346_LOCATION.match(text):
        # A standalone location aspect: the whole token is the location,
        # so nothing trails it and the character range is the token's own.
        return text, 0

    return None
