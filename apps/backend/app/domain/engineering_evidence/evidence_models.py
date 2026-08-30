"""
Engineering Evidence (EPIC 2, Milestone 28.1) - what a document was
*observed* to contain.

## What an evidence item is

A single statement of the form:

> "the characters 20 kV appeared on page 3, paragraph 2, line 1, tokens
> 4-5, matched by rule `voltage_value` version 1.0."

That is all. It is an **observation about a document**, not a fact about
a substation.

## What an evidence item is emphatically not

- **It is not an entity.** "T1 was observed" does not say a transformer
  called T1 exists. Two documents may write the same designation for
  different equipment, and one piece of equipment may appear under
  several designations. Deciding which is entity resolution, and it is a
  later milestone with its own review obligations.
- **It carries no relationships.** A voltage observed on the same line as
  a designation is *two observations that happen to be adjacent*, not a
  property of that equipment. Adjacency is a fact about ink; attribution
  is a judgement. There is nowhere in this model to record one.
- **It says nothing about equipment type.** ``QMT01`` looks like a
  medium-voltage panel to an engineer. This layer records only that the
  designation-like text was seen; classifying it would be inference.

Every one of those exclusions is enforced by the shape of these value
objects - there is no field to put them in - and by an architecture test.

## Provenance is mandatory

Every item carries its way back to the exact characters of the exact
canonical spans it came from. An observation whose source cannot be
located is not evidence; it is an assertion, and this system does not
store assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class EvidenceType(str, Enum):
    """
    The deliberately small catalogue this milestone supports.

    ``MANUFACTURER_NAME`` is **absent on purpose**. Recognising a
    manufacturer requires a list of manufacturers, and this repository
    has none: ``ontology/attributes/manufacturer.yaml`` declares a
    free-text string attribute with no enumerated values. Inventing a
    dictionary of vendor names would be an arbitrary, incomplete
    catalogue masquerading as a deterministic rule - so the type is left
    out until a governed vendor vocabulary exists.
    """

    DESIGNATION = "designation"
    VOLTAGE_VALUE = "voltage_value"
    CURRENT_VALUE = "current_value"
    POWER_VALUE = "power_value"
    CABLE_SECTION_VALUE = "cable_section_value"

    #: The **location aspect** of a compound IEC 81346 reference
    #: designation - the ``+E01`` of ``+E01-QA1``.
    #:
    #: The only member of this catalogue that observes part of a token
    #: rather than the whole of one, and it is not an inference: the
    #: characters ``+E01`` are written in the document, and IEC 81346-1
    #: assigns ``+`` to the location aspect. What is observed is that a
    #: location aspect was **written**; whether the equipment is
    #: therefore located there is a meaning, assigned two layers up by a
    #: reviewed semantic rule.
    LOCATION_ASPECT = "location_aspect"


class EvidenceStatus(str, Enum):
    """
    A small categorical vocabulary, and deliberately not a percentage.

    A numerical confidence would have to be calibrated against something,
    and there is nothing here to calibrate it against: a regular
    expression either matched or it did not. Inventing "0.85" would dress
    a boolean up as a measurement.
    """

    # The rule matched and its validation policy was satisfied.
    OBSERVED = "observed"
    # The rule matched and the result cannot be stated unambiguously -
    # a number whose separator could be either a decimal point or a
    # thousands mark, say. Persisted, because a reviewer can resolve it
    # and because the observation itself is real; carried without a
    # normalised value, so no consumer can mistake it for a settled one.
    AMBIGUOUS = "ambiguous"
    # The rule matched and validation refused the result. Returned as a
    # diagnostic so an engineer can see what the extractor decided
    # against, and **never persisted** as evidence.
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class SpanReference:
    """
    One canonical span, and the characters of it that this evidence used.

    ``character_start``/``character_end`` are offsets into that span's own
    text, half-open, Python slice convention - exactly as Milestone 27.1
    records them on a token.

    Evidence may reference **more than one span**: "20" and "kV" can sit
    in different spans when a style changes mid-line. The references are
    kept as a sequence rather than flattened into a single range, because
    a single range across two spans would describe characters that do not
    exist.
    """

    span_reading_order: int
    character_start: int
    character_end: int

    @property
    def character_length(self) -> int:
        return self.character_end - self.character_start


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    """
    Where an observation came from, exactly enough to re-read it.

    A caller holding one of these can answer, without searching for text
    anywhere: which page, which paragraph, which line, which tokens, and
    which characters of which spans.

    ``source_text`` is the original text of the matched tokens, joined by
    single spaces - the words themselves, so an auditor need not resolve
    the references to see what was read.
    """

    page_number: int
    section_index: int
    paragraph_index: int
    block_reading_order: int
    line_index: int
    token_start: int
    token_end: int
    spans: tuple[SpanReference, ...]
    source_text: str

    @property
    def token_count(self) -> int:
        return self.token_end - self.token_start

    @property
    def crosses_spans(self) -> bool:
        """Whether the observation was assembled from more than one span -
        worth knowing, because it is the case where a naive extractor
        would have produced a bogus character range."""

        return len(self.spans) > 1


@dataclass(frozen=True, slots=True)
class EngineeringQuantity:
    """
    A quantity, held exactly.

    ``Decimal`` throughout, never ``float``: 0.1 is not representable in
    binary floating point, and a rated voltage that reads back as
    20.000000000000004 kV would be a defect an engineer could not
    explain.

    ``base_value``/``base_unit`` are populated only where the conversion
    is exact and declared in the unit catalogue - kV to V, kA to A, kVA
    to VA. Where no such conversion is declared (mm²), they are ``None``:
    this is not a unit-conversion engine, and inventing a base unit for
    everything would mean inventing conversions.
    """

    value: Decimal
    unit: str
    base_value: Decimal | None = None
    base_unit: str | None = None

    @property
    def is_convertible(self) -> bool:
        return self.base_value is not None


@dataclass(frozen=True, slots=True)
class DesignationValue:
    """
    A designation-like string, as observed.

    ``normalized`` is upper-cased and stripped of surrounding
    punctuation, which is lossless for this pattern class and makes two
    spellings of the same designation comparable. The original is always
    on the evidence item beside it.

    There is deliberately no ``equipment_type``, no ``category`` and no
    ``prefix_meaning``: reading ``QMT01`` as a medium-voltage panel is
    exactly the inference this milestone refuses.
    """

    normalized: str


@dataclass(frozen=True, slots=True)
class EngineeringEvidence:
    """
    One observation.

    ``quantity`` and ``designation`` are **two typed fields rather than
    one untyped value**, because a voltage and a designation are not the
    same kind of thing and a single ``value: str`` would force every
    consumer to re-parse what the extractor already knew. Exactly one is
    populated, decided by ``evidence_type`` and enforced at construction.

    ``evidence_key`` is a deterministic identity: the SHA-256 of the
    document, checksum, rule, type and provenance that produced it. The
    same extraction over the same canonical text always yields the same
    key, which is what makes idempotency enforceable in the schema rather
    than merely intended. The database row id and its timestamp are
    **not** on this value object - they are facts about the row, and
    including them would break the equality that proves determinism.
    """

    evidence_key: str
    evidence_type: EvidenceType
    status: EvidenceStatus
    observed_text: str
    rule_id: str
    rule_version: str
    provenance: EvidenceProvenance
    quantity: EngineeringQuantity | None = None
    designation: DesignationValue | None = None

    @property
    def is_persistable(self) -> bool:
        """``REJECTED`` items are diagnostics, not engineering
        evidence."""

        return self.status is not EvidenceStatus.REJECTED


@dataclass(frozen=True, slots=True)
class EngineeringEvidenceSet:
    """
    Everything one extraction observed in one canonical text.

    The four version fields are what keep a historical set explainable:
    which document, which bytes (``content_checksum``), which
    segmentation contract, and which extraction policy. A set whose
    provenance is unknown cannot be trusted by anything downstream, and
    an entity resolved from untrustworthy evidence is worse than no
    entity at all.

    Deliberately **no timestamp** - see ``EngineeringEvidence``.
    """

    document_id: int
    project_id: int | None
    content_checksum: str
    segmentation_version: str
    extraction_policy_version: str
    evidence: tuple[EngineeringEvidence, ...] = ()

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def is_empty(self) -> bool:
        return not self.evidence

    def of_type(
        self, evidence_type: EvidenceType
    ) -> tuple[EngineeringEvidence, ...]:
        return tuple(
            item
            for item in self.evidence
            if item.evidence_type is evidence_type
        )

    def with_status(
        self, status: EvidenceStatus
    ) -> tuple[EngineeringEvidence, ...]:
        return tuple(item for item in self.evidence if item.status is status)
