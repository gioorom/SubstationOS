"""
Spreadsheet Evidence (ADR-0034) - what a workbook was *observed* to
contain.

## What an evidence item is

A single statement of the form:

> "the characters 630 A appeared in worksheet 1 'Equipment', row 2,
> column 2 (B), characters 0-5 of that cell's text, matched by rule
> `current_value` version 1.0."

That is all. It is an **observation about a cell**, not a fact about a
substation.

## A restated family, not a widened one

``EngineeringEvidence`` and ``EvidenceProvenance`` are **not** modified
by this context and are not used by it. Their provenance is page-shaped
and mandatory - page number, paragraph index, line index, a token range,
span references - and a cell has none of those. Recording an item for a
cell through that model would mean writing six invented values into
``NOT NULL`` columns, four of which enter a persisted identity, which
under the evidence model's own rule would make the item an assertion
rather than evidence.

What is **reused rather than restated**: ``EvidenceType``,
``EvidenceStatus``, ``EngineeringQuantity`` and ``DesignationValue``.
These are shared, stable vocabulary containing no PDF concept, and
reusing them read-only is what keeps "there is exactly one designation
pattern in this system" true. This context declares no pattern, no rule
and no unit of its own.

## What an evidence item is emphatically not

- **It is not an entity.** "CBL-001 was observed in cell A2" does not
  say a cable called CBL-001 exists.
- **It carries no relationships.** Two designations observed in the same
  row are two observations that happen to be adjacent - exactly as two
  observations on the same line of a PDF are. Row adjacency is a fact
  about the file; a connection is a judgement, and there is nowhere in
  this model to record one. **No** ``Cable``, ``Circuit``, ``Terminal``,
  ``From``, ``To`` or ``CONNECTS`` concept exists here.
- **It says nothing about a header.** There is no ``column_name``, no
  ``field_name`` and no ``record``. Deciding that row 1 - or row 7,
  after a title block - names the columns is an inference, and this
  context reads nothing that could check one.

Every one of those exclusions is enforced by the shape of these value
objects: there is no field to put them in.

## Provenance is mandatory, and it is cell-shaped

Every item carries its way back to the exact characters of the exact
cell it came from. An observation whose source cannot be located is not
evidence; it is an assertion, and this system does not store assertions.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceStatus,
    EvidenceType,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_exceptions import (
    InvalidSpreadsheetEvidenceError,
)


@dataclass(frozen=True, slots=True)
class CellEvidenceProvenance:
    """
    Where an observation came from, exactly enough to re-read it.

    A caller holding one of these can answer, without searching for text
    anywhere: which worksheet, at which position and under which name,
    which row, which column, and which characters of that cell's text.

    ``character_start``/``character_end`` are offsets into **the cell's
    own text**, half-open, Python slice convention. They are not offsets
    into a worksheet, a row, a concatenation, or anything else: a cell is
    the atomic addressable unit of a workbook, so its own text is the
    only string these offsets could honestly index.

    There is deliberately **no ``page_number``, no ``paragraph``, no
    ``line_index`` and no ``span``**. A worksheet has no page until it is
    printed, and print pagination is a rendering decision that changes
    with the margins; a row is not a line of ink; a cell has coordinates
    rather than a rectangle, and nothing here was ever grouped into a
    span. Every one of those fields would have to be invented, and an
    invented locator is the thing this model exists to refuse.

    ``worksheet_name`` is recorded **as well as** ``worksheet_index``: an
    engineer looking for "Cable Schedule" needs the name, and a later
    revision of the same register can move that worksheet, at which point
    the position alone would silently point somewhere else. Neither
    alone survives a revision honestly.

    ``column_label`` is the workbook's own bijective base-26 label - the
    ``B`` of ``B2`` - so a recorded observation can be pasted straight
    back into the source file and checked.

    ``source_text`` is the matched text, joined by single spaces where an
    observation covered two tokens, so an auditor need not re-read the
    cell to see what was matched.
    """

    worksheet_index: int
    worksheet_name: str
    row_number: int
    column_number: int
    column_label: str
    character_start: int
    character_end: int
    source_text: str

    @property
    def character_length(self) -> int:
        return self.character_end - self.character_start

    @property
    def a1_reference(self) -> str:
        """The cell's address as the workbook itself writes it."""

        return f"{self.column_label}{self.row_number}"


@dataclass(frozen=True, slots=True)
class SpreadsheetEvidence:
    """
    One observation.

    ``quantity`` and ``designation`` are **two typed fields rather than
    one untyped value**, because a voltage and a designation are not the
    same kind of thing and a single ``value: str`` would force every
    consumer to re-parse what the extractor already knew. At most one is
    populated, decided by ``evidence_type``; both would leave every
    consumer free to pick whichever suited it, so construction refuses
    it.

    Neither is populated when the rule matched and the result could not
    be stated unambiguously. That is an ``AMBIGUOUS`` observation carried
    without a normalised value, so no consumer can mistake a guess for a
    measurement.

    ``evidence_key`` is a deterministic identity: the SHA-256 of the
    document, checksum, rule, type and cell coordinates that produced it.
    The same extraction over the same workbook always yields the same
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
    provenance: CellEvidenceProvenance
    quantity: EngineeringQuantity | None = None
    designation: DesignationValue | None = None

    def __post_init__(self) -> None:
        if self.quantity is not None and self.designation is not None:
            raise InvalidSpreadsheetEvidenceError(
                f"Observation '{self.evidence_key}' at "
                f"{self.provenance.a1_reference} carries both a "
                "quantity and a designation; an observation is one kind "
                "of thing."
            )

    @property
    def is_persistable(self) -> bool:
        """``REJECTED`` items are diagnostics, not engineering
        evidence."""

        return self.status is not EvidenceStatus.REJECTED


@dataclass(frozen=True, slots=True)
class SpreadsheetEvidenceSet:
    """
    Everything one extraction observed in one canonical workbook.

    The four provenance fields are what keep a historical set
    explainable: which document, which bytes (``content_checksum``),
    which representation contract the workbook was recorded under, and
    which extraction policy read it. A set whose provenance is unknown
    cannot be trusted by anything downstream.

    Deliberately **no timestamp** - the value is a function of the
    workbook and the policy, and two runs over the same workbook must
    compare equal. When it was built is a fact about the row.
    """

    document_id: int
    project_id: int | None
    content_checksum: str
    representation_version: str
    extraction_policy_version: str
    evidence: tuple[SpreadsheetEvidence, ...] = ()

    #: This artifact's deterministic identity, and the identity of the
    #: artifact it was derived from. ``None`` only for a row stored
    #: before the identity chain existed: unknown is not a value, and an
    #: artifact that cannot say what it was derived from can never prove
    #: a reuse is valid. See ``app/domain/artifact_identity``.
    artifact_identity: str | None = None
    upstream_identity: str | None = None

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def is_empty(self) -> bool:
        return not self.evidence

    def of_type(
        self, evidence_type: EvidenceType
    ) -> tuple[SpreadsheetEvidence, ...]:
        return tuple(
            item
            for item in self.evidence
            if item.evidence_type is evidence_type
        )

    def with_status(
        self, status: EvidenceStatus
    ) -> tuple[SpreadsheetEvidence, ...]:
        return tuple(item for item in self.evidence if item.status is status)
