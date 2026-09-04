"""
The spreadsheet evidence extractor (ADR-0034) - the pure function that
runs the pinned rule catalogue over a canonical workbook and returns what
was observed.

```
CanonicalWorkbook
   -> for each worksheet, row, cell
       -> read the cell's text
       -> tokenise it on whitespace, in process
           -> ask each rule whether a candidate starts here
   -> SpreadsheetEvidenceSet
```

## Which cell text is read, and why it matters

This is the milestone's sharpest boundary, so it is stated here rather
than left to be discovered:

- **A literal cell** contributes its own recorded text.
- **A formula cell** contributes the text of the value some other
  application **cached** into the file, when one is present. That value
  is a claim by whatever last opened the workbook, and it is the only
  value the file actually states for that cell.
- **A formula cell with no cached result contributes nothing at all.**
  Not an empty observation, not a zero, not the formula expression read
  as if it were a value. A workbook written by a script and never opened
  by a spreadsheet application carries formulas and no cached values, and
  that is the common case rather than the exotic one. ADR-0034 §3
  forbids inventing a value there: this platform does not evaluate
  formulas, because evaluation depends on a calculation chain, a date
  system and an iteration setting, and a value computed here would be
  indistinguishable in the record from a value the engineer's
  spreadsheet computed.

The **formula expression itself is never tokenised.** ``=A2*B2`` states
how a value would be computed; it does not state a value, and matching
designation- or quantity-shaped text inside it would record the
register's arithmetic as if it were the register's content.

## Tokenisation is not a persisted stage

A cell's text is split on whitespace **in process**, under this
context's own policy version (ADR-0034 §8). The PDF family persists
``canonical_text`` as a separate artifact because PDF spans must be
*grouped* into lines, paragraphs and sections - real structural
derivation, over which rules change independently of the parser. A cell
is already the atomic addressable unit; splitting its text is not a
derivation of comparable weight, and persisting it as a further artifact
with its own tables, identity and audit entry would be generality
introduced before any evidence that it is needed.

The boundary logic is restated here rather than imported from
``canonical_text``. ADR-0034 §1 forks the two families at the bytes and
asserts by fitness function that nothing in this lineage imports the PDF
one; a shared import for eight lines of whitespace scanning would be the
first thread joining them back together.

## Three properties this function is built around

1. **It orchestrates; it does not match.** Every matching decision comes
   from ``evidence_rules`` and ``evidence_units`` - the catalogue the PDF
   family already pins, reused read-only, which is what keeps "there is
   exactly one designation pattern in this system" true. This context
   declares no pattern of its own and compiles no regular expression.
2. **Provenance is recorded at match time, never reconstructed.** The
   cell's coordinates and the character offsets inside its own text are
   carried straight from the traversal. Nothing is ever located later by
   searching for text, which is how provenance quietly becomes
   approximate.
3. **A candidate never crosses a cell.** A cell is the whole window a
   rule may look at, so an observation cannot span two columns or two
   rows. That two cells in the same row both carry designation-like text
   is an observation about a grid, not a connection between them.

## What it does not do

No entity is created, no relationship is inferred, no header is
identified, no attribute is attached to anything. A voltage observed
beside a designation yields two independent items; they do not know
about each other, and there is nowhere in the model to say that they do.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalCell,
    CanonicalRow,
    CanonicalWorkbook,
    CanonicalWorksheet,
)
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceStatus,
    EvidenceType,
)
from app.domain.engineering_evidence.evidence_patterns import (
    NUMBER,
    NUMBER_WITH_UNIT,
)
from app.domain.engineering_evidence.evidence_quantities import (
    QuantityParseOutcome,
    parse_quantity,
)
from app.domain.engineering_evidence.evidence_rules import (
    DESIGNATION_RULE,
    LOCATION_ASPECT_RULE,
    QUANTITY_RULE_BY_TYPE,
    ExtractionRule,
    TrimmedToken,
    match_location_aspect,
    matches_designation,
    strip_boundary_punctuation,
)
from app.domain.engineering_evidence.evidence_units import (
    UnitDefinition,
    convert_to_base,
    find_unit,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_identity import (
    spreadsheet_evidence_set_identity,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    CellEvidenceProvenance,
    SpreadsheetEvidence,
    SpreadsheetEvidenceSet,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_policy import (
    SPREADSHEET_EXTRACTION_POLICY_VERSION,
)

# How the deterministic evidence key is composed. Documented here because
# the key is stored, and a stored identity whose formula is unknown
# cannot be reproduced or checked.
#
# Ten slots, the same shape the PDF family uses, with **cell coordinates
# where page coordinates stood**: a worksheet, a row and a column in
# place of a page, a paragraph and a line, and character offsets into the
# cell's own text in place of a token range.
_KEY_FIELDS = (
    "document_id",
    "content_checksum",
    "rule_id",
    "rule_version",
    "evidence_type",
    "worksheet_index",
    "row_number",
    "column_number",
    "character_start",
    "character_end",
)


@dataclass(frozen=True, slots=True)
class _CellToken:
    """
    One whitespace-delimited run of a cell's text, with its half-open
    range into that text.

    Offsets rather than substrings, because the offsets are the
    provenance: a token has to be locatable inside the cell it came from,
    not merely equal to some substring of it.
    """

    text: str
    character_start: int
    character_end: int


def extract_cell_evidence(
    workbook: CanonicalWorkbook,
    *,
    project_id: int | None = None,
    extraction_policy_version: str = SPREADSHEET_EXTRACTION_POLICY_VERSION,
) -> SpreadsheetEvidenceSet:
    """
    Run the rule catalogue over one canonical workbook.

    Pure and deterministic: same workbook in, equal evidence set out. No
    clock, no randomness, no I/O, no ambient state - the worksheets are
    walked in the order the representation records them, which is the
    workbook's own.

    ``REJECTED`` items are **included** in the returned set - they are
    the extractor's diagnostics, and a caller can see what it decided
    against. Persistence drops them; see
    ``SpreadsheetEvidence.is_persistable``.
    """

    evidence: list[SpreadsheetEvidence] = []

    for worksheet in workbook.worksheets:
        for row in worksheet.rows:
            for cell in row.cells:
                evidence.extend(
                    _extract_from_cell(workbook, worksheet, row, cell)
                )

    # The identity chain, carried forward where the derivation happens.
    # The upstream artifact already knows its own identity; this one is
    # composed from it and this stage's own contract, so anything built
    # through the domain knows what it came from.
    upstream = (
        None
        if workbook.artifact_identity is None
        else ArtifactIdentity(
            value=workbook.artifact_identity,
            kind=ArtifactKind.CANONICAL_SPREADSHEET,
            contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
        )
    )
    identity = (
        None
        if upstream is None
        else spreadsheet_evidence_set_identity(
            workbook=upstream,
            extraction_policy_version=extraction_policy_version,
        )
    )

    return SpreadsheetEvidenceSet(
        artifact_identity=None if identity is None else identity.value,
        upstream_identity=workbook.artifact_identity,
        document_id=workbook.document_id,
        project_id=project_id,
        content_checksum=workbook.content_checksum,
        representation_version=workbook.representation_version,
        extraction_policy_version=extraction_policy_version,
        evidence=tuple(evidence),
    )


def observable_text(cell: CanonicalCell) -> str | None:
    """
    The text of the value this cell **states**, or ``None`` when it
    states none.

    A literal states its own text. A formula states the value another
    application cached into the file, and states nothing at all when no
    application ever computed one - which is recorded as ``None`` rather
    than as an empty string, a zero, or the formula expression. Those
    would be lies of different sizes, and the last is the one that would
    put a register's arithmetic into the record as if it were the
    register's content.

    Public because it is the boundary rule of this milestone, and a rule
    a reader has to open a private function to find is a rule nobody
    reviews.
    """

    if cell.literal is not None:
        return cell.literal.text

    if cell.formula is not None and cell.formula.cached_result is not None:
        return cell.formula.cached_result.text

    return None


def _extract_from_cell(
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
) -> list[SpreadsheetEvidence]:
    """
    One cell is the whole window a rule may look at.

    That bound is deliberate: it makes it structurally impossible for an
    observation to span two columns or two rows, which is the provenance
    boundary that would be invalid - and it is what stops row adjacency
    from being recorded as a relationship.
    """

    text = observable_text(cell)

    if text is None:
        return []

    found: list[SpreadsheetEvidence] = []
    tokens = _tokenize(text)
    index = 0

    while index < len(tokens):
        quantity = _match_quantity(
            workbook, worksheet, row, cell, tokens, index
        )

        if quantity is not None:
            item, consumed = quantity
            found.append(item)
            index += consumed
            continue

        designation = _match_designation(
            workbook, worksheet, row, cell, tokens, index
        )

        if designation is not None:
            found.append(designation)

        # Evaluated **independently** of the designation rule, because a
        # token may carry a location aspect either way round - see
        # ``evidence_rules.match_location_aspect``. The two rules produce
        # different evidence keys because the rule and the evidence type
        # are part of the key.
        location = _match_location_aspect(
            workbook, worksheet, row, cell, tokens, index
        )

        if location is not None:
            found.append(location)

        index += 1

    return found


def _tokenize(text: str) -> tuple[_CellToken, ...]:
    """
    The whitespace-delimited runs of one cell's text, each with its
    half-open range into that text.

    Whitespace is ``str.isspace``, which is the Unicode definition -
    non-breaking and thin spaces included, both of which occur routinely
    in a workbook that was pasted into from elsewhere. Splitting on
    anything narrower would join values the cell shows apart.

    Nothing else is done to the text: it is not stripped, case-folded,
    normalised or collapsed. The characters are the register's.
    """

    tokens: list[_CellToken] = []
    start: int | None = None

    for index, character in enumerate(text):
        if character.isspace():
            if start is not None:
                tokens.append(
                    _CellToken(
                        text=text[start:index],
                        character_start=start,
                        character_end=index,
                    )
                )
                start = None
        elif start is None:
            start = index

    if start is not None:
        tokens.append(
            _CellToken(
                text=text[start:],
                character_start=start,
                character_end=len(text),
            )
        )

    return tuple(tokens)


def _match_designation(
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    tokens: tuple[_CellToken, ...],
    index: int,
) -> SpreadsheetEvidence | None:
    """
    The designation rule, applied to one token.

    Matched against the token's **original** text, not a normalised form:
    a designation is an engineering symbol and the original is what the
    register wrote.
    """

    candidate = strip_boundary_punctuation(tokens[index].text)

    if not candidate.text or not matches_designation(candidate.text):
        return None

    return _build(
        workbook=workbook,
        worksheet=worksheet,
        row=row,
        cell=cell,
        tokens=tokens[index : index + 1],
        trims=(candidate,),
        rule=DESIGNATION_RULE,
        status=EvidenceStatus.OBSERVED,
        designation=DesignationValue(normalized=candidate.text.upper()),
    )


def _match_location_aspect(
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    tokens: tuple[_CellToken, ...],
    index: int,
) -> SpreadsheetEvidence | None:
    """
    The location-aspect rule, applied to one token.

    For a **compound** ``+E01-QA1`` the observation covers part of the
    token: the trim's ``right`` offset is widened by the length of the
    product segment, so the recorded character range narrows onto
    ``+E01``. For a **standalone** ``+GSH002`` the whole token is the
    location and the range is the token's own.

    Consumes no token, and makes no assumption about the designation
    rule. It records that a location aspect was *written* there - not
    that any equipment is located in it, which is a meaning a semantic
    rule assigns and an engineer reviews.
    """

    candidate = strip_boundary_punctuation(tokens[index].text)

    if not candidate.text:
        return None

    matched = match_location_aspect(candidate.text)

    if matched is None:
        return None

    location_text, product_length = matched

    return _build(
        workbook=workbook,
        worksheet=worksheet,
        row=row,
        cell=cell,
        tokens=tokens[index : index + 1],
        trims=(
            TrimmedToken(
                text=location_text,
                left=candidate.left,
                right=candidate.right + product_length,
            ),
        ),
        rule=LOCATION_ASPECT_RULE,
        status=EvidenceStatus.OBSERVED,
        designation=DesignationValue(normalized=location_text.upper()),
    )


def _match_quantity(
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    tokens: tuple[_CellToken, ...],
    index: int,
) -> tuple[SpreadsheetEvidence, int] | None:
    """
    The quantity rules, applied at one token position.

    Two shapes are accepted, both declared by ``RuleKind.QUANTITY``: a
    single token carrying number and unit together ("20kV"), or a numeric
    token followed by a unit token ("20" "kV"). Which rule applies is
    decided by the unit catalogue, never by this function.

    Both tokens must be in the **same cell**. A number in column B and a
    unit in column C are two cells, and pairing them would be reading the
    grid as a record - the inference ADR-0034 §6 refuses.

    Returns the item and how many tokens it consumed, so the caller does
    not offer the unit token to the designation rule afterwards.
    """

    first = strip_boundary_punctuation(tokens[index].text)

    if not first.text:
        return None

    combined = NUMBER_WITH_UNIT.match(first.text)

    if combined is not None:
        definition = find_unit(combined.group("unit"))

        if definition is not None:
            return (
                _quantity_evidence(
                    workbook,
                    worksheet,
                    row,
                    cell,
                    tokens[index : index + 1],
                    (first,),
                    combined.group("number"),
                    definition,
                ),
                1,
            )

    if not NUMBER.match(first.text) or index + 1 >= len(tokens):
        return None

    second = strip_boundary_punctuation(tokens[index + 1].text)
    definition = find_unit(second.text) if second.text else None

    if definition is None:
        # A number not followed by a declared unit. Nothing is inferred
        # from a neighbouring cell, a column position, or a
        # header-shaped row above - an undeclared unit is not a unit.
        return None

    return (
        _quantity_evidence(
            workbook,
            worksheet,
            row,
            cell,
            tokens[index : index + 2],
            (first, second),
            first.text,
            definition,
        ),
        2,
    )


def _quantity_evidence(
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    matched: tuple[_CellToken, ...],
    trims: tuple[TrimmedToken, ...],
    number_text: str,
    definition: UnitDefinition,
) -> SpreadsheetEvidence:
    """Applies the rule's normalization and validation policies to a
    matched quantity."""

    rule = QUANTITY_RULE_BY_TYPE[definition.evidence_type]
    value, outcome = parse_quantity(number_text)

    if outcome is QuantityParseOutcome.EXACT:
        return _build(
            workbook=workbook,
            worksheet=worksheet,
            row=row,
            cell=cell,
            tokens=matched,
            trims=trims,
            rule=rule,
            status=EvidenceStatus.OBSERVED,
            quantity=_quantity(value, definition),
        )

    if outcome is QuantityParseOutcome.AMBIGUOUS_SEPARATOR:
        # Carried **without** a normalised value. The observation is
        # real; the number is not settled, and a consumer must not be
        # able to read a guess as a measurement.
        return _build(
            workbook=workbook,
            worksheet=worksheet,
            row=row,
            cell=cell,
            tokens=matched,
            trims=trims,
            rule=rule,
            status=EvidenceStatus.AMBIGUOUS,
        )

    return _build(
        workbook=workbook,
        worksheet=worksheet,
        row=row,
        cell=cell,
        tokens=matched,
        trims=trims,
        rule=rule,
        status=EvidenceStatus.REJECTED,
    )


def _quantity(
    value: Decimal, definition: UnitDefinition
) -> EngineeringQuantity:
    converted = convert_to_base(value, definition)

    return EngineeringQuantity(
        value=value,
        unit=definition.canonical_symbol,
        base_value=converted[0] if converted is not None else None,
        base_unit=converted[1] if converted is not None else None,
    )


def _build(
    *,
    workbook: CanonicalWorkbook,
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    tokens: tuple[_CellToken, ...],
    trims: tuple[TrimmedToken, ...],
    rule: ExtractionRule,
    status: EvidenceStatus,
    quantity: EngineeringQuantity | None = None,
    designation: DesignationValue | None = None,
) -> SpreadsheetEvidence:
    provenance = _provenance(worksheet, row, cell, tokens, trims)

    return SpreadsheetEvidence(
        evidence_key=_evidence_key(
            workbook, rule, provenance, rule.evidence_type
        ),
        evidence_type=rule.evidence_type,
        status=status,
        observed_text=provenance.source_text,
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        provenance=provenance,
        quantity=quantity,
        designation=designation,
    )


def _provenance(
    worksheet: CanonicalWorksheet,
    row: CanonicalRow,
    cell: CanonicalCell,
    tokens: tuple[_CellToken, ...],
    trims: tuple[TrimmedToken, ...],
) -> CellEvidenceProvenance:
    """
    Built from what the traversal already knows, never derived.

    Each token's character range is narrowed by whatever punctuation the
    trimming policy removed, so the range covers exactly the characters
    that produced the evidence - ``400 V,`` points at ``400 V``.

    A single half-open range is correct here, where the PDF family needs
    a sequence of span references: every token of a candidate comes from
    the **same cell's** text, so one range describes characters that
    genuinely exist in one string.
    """

    first, last = tokens[0], tokens[-1]

    return CellEvidenceProvenance(
        worksheet_index=worksheet.worksheet_index,
        worksheet_name=worksheet.name,
        row_number=row.row_number,
        column_number=cell.column_number,
        column_label=cell.column_label,
        character_start=first.character_start + trims[0].left,
        character_end=last.character_end - trims[-1].right,
        source_text=" ".join(trim.text for trim in trims),
    )


def _evidence_key(
    workbook: CanonicalWorkbook,
    rule: ExtractionRule,
    provenance: CellEvidenceProvenance,
    evidence_type: EvidenceType,
) -> str:
    """
    A deterministic identity for one observation.

    SHA-256 over the fields named in ``_KEY_FIELDS``, joined by ``|``.
    Deterministic by construction, so the same extraction over the same
    workbook always produces the same keys - which is what lets the
    schema enforce idempotency rather than merely hoping for it.
    """

    material = "|".join(
        (
            str(workbook.document_id),
            workbook.content_checksum,
            rule.rule_id,
            rule.rule_version,
            evidence_type.value,
            str(provenance.worksheet_index),
            str(provenance.row_number),
            str(provenance.column_number),
            str(provenance.character_start),
            str(provenance.character_end),
        )
    )

    return hashlib.sha256(material.encode("utf-8")).hexdigest()
