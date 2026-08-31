"""
The evidence extractor (Milestone 28.1) - the pure function that runs the
rule catalogue over a canonical text and returns what was observed.

```
CanonicalTextDocument
   -> for each section (page), paragraph, line
       -> for each token position
           -> ask each rule whether a candidate starts here
   -> EngineeringEvidenceSet
```

## Three properties this function is built around

1. **It orchestrates; it does not match.** Every matching decision comes
   from ``evidence_rules`` and ``evidence_units``. There is no inline
   pattern here, and an architecture test asserts it - an ``if`` in this
   file that recognised something would be a rule nobody could find,
   version or review.
2. **Provenance is recorded at match time, never reconstructed.** The
   token positions and the character offsets inside their spans are
   carried straight from the canonical text. Nothing is ever located
   later by searching for text, which is how provenance quietly becomes
   approximate.
3. **A candidate never crosses a line.** Rules see one line's tokens at a
   time, so an observation cannot span a paragraph or a page. It *may*
   span two canonical spans within a line - "20" and "kV" in different
   styles - and then it records both span references rather than a
   single range describing characters that do not exist.

## What it does not do

No entity is created, no relationship is inferred, no attribute is
attached to anything. A voltage observed beside a designation yields two
independent items; they do not know about each other, and there is
nowhere in the model to say that they do.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
    CanonicalTextLine,
    CanonicalTextParagraph,
    CanonicalTextSection,
    CanonicalTextToken,
)
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringEvidence,
    EngineeringEvidenceSet,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
    SpanReference,
)
from app.domain.engineering_evidence.evidence_patterns import (
    NUMBER,
    NUMBER_WITH_UNIT,
)
from app.domain.engineering_evidence.evidence_policy import (
    EXTRACTION_POLICY_VERSION,
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

# How the deterministic evidence key is composed. Documented here because
# the key is stored, and a stored identity whose formula is unknown
# cannot be reproduced or checked.
_KEY_FIELDS = (
    "document_id",
    "content_checksum",
    "rule_id",
    "rule_version",
    "evidence_type",
    "page_number",
    "paragraph_index",
    "line_index",
    "token_start",
    "token_end",
)


def extract_evidence(
    canonical_text: CanonicalTextDocument,
    *,
    project_id: int | None = None,
    extraction_policy_version: str = EXTRACTION_POLICY_VERSION,
) -> EngineeringEvidenceSet:
    """
    Run the rule catalogue over one canonical text.

    Pure and deterministic: same canonical text in, equal evidence set
    out. ``REJECTED`` items are **included** in the returned set - they
    are the extractor's diagnostics, and a caller can see what it decided
    against. Persistence drops them; see
    ``EngineeringEvidence.is_persistable``.
    """

    evidence: list[EngineeringEvidence] = []

    for section in canonical_text.sections:
        for paragraph in section.paragraphs:
            for line in paragraph.lines:
                evidence.extend(
                    _extract_from_line(
                        canonical_text, section, paragraph, line
                    )
                )

    return EngineeringEvidenceSet(
        document_id=canonical_text.document_id,
        project_id=project_id,
        content_checksum=canonical_text.content_checksum,
        segmentation_version=canonical_text.segmentation_version,
        extraction_policy_version=extraction_policy_version,
        evidence=tuple(evidence),
    )


def _extract_from_line(
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
) -> list[EngineeringEvidence]:
    """
    One line is the whole window a rule may look at.

    That bound is deliberate: it makes it structurally impossible for an
    observation to span a paragraph or a page, which is the provenance
    boundary that would be invalid.
    """

    found: list[EngineeringEvidence] = []
    tokens = line.tokens
    index = 0

    while index < len(tokens):
        quantity = _match_quantity(
            canonical_text, section, paragraph, line, tokens, index
        )

        if quantity is not None:
            item, consumed = quantity
            found.append(item)
            index += consumed
            continue

        designation = _match_designation(
            canonical_text, section, paragraph, line, tokens, index
        )

        if designation is not None:
            found.append(designation)

        # Evaluated **independently** of the designation rule, because a
        # token may carry a location aspect either way round:
        #
        # - ``+E01-QA1`` is a designation that was written, and ``+E01``
        #   is a location aspect written inside it. Both are true, and
        #   the evidence keys differ because the rule and the evidence
        #   type are part of the key.
        # - ``+GSH002`` is a location aspect and nothing else. The
        #   designation rule declines it (EPIC 32.E2), so this branch is
        #   the only one that observes it.
        location = _match_location_aspect(
            canonical_text, section, paragraph, line, tokens, index
        )

        if location is not None:
            found.append(location)

        index += 1

    return found


def _match_designation(
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    tokens: tuple[CanonicalTextToken, ...],
    index: int,
) -> EngineeringEvidence | None:
    """
    The designation rule, applied to one token.

    Matched against the token's **original** text, not its normalised
    form: a designation is an engineering symbol and the original is what
    the document wrote.
    """

    token = tokens[index]
    candidate = strip_boundary_punctuation(token.text)

    if not candidate.text or not matches_designation(candidate.text):
        return None

    return _build(
        canonical_text=canonical_text,
        section=section,
        paragraph=paragraph,
        line=line,
        tokens=tokens[index : index + 1],
        trims=(candidate,),
        token_start=index,
        rule=DESIGNATION_RULE,
        status=EvidenceStatus.OBSERVED,
        designation=DesignationValue(normalized=candidate.text.upper()),
    )


def _match_location_aspect(
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    tokens: tuple[CanonicalTextToken, ...],
    index: int,
) -> EngineeringEvidence | None:
    """
    The location-aspect rule, applied to one token.

    Two shapes, and the care is in recording each one's characters
    exactly.

    For a **compound** ``+E01-QA1`` the observation covers part of the
    token: the trim's ``right`` offset is widened by the length of the
    product segment, so ``_provenance`` narrows the character range onto
    ``+E01`` and the item's ``source_text`` is ``+E01``. An auditor who
    follows this evidence back to the document lands on the four
    characters that produced it, not on the whole token.

    For a **standalone** ``+GSH002`` - the commoner form in real
    documents - the whole token is the location, and the range is the
    token's own.

    Consumes no token, and makes no assumption about the designation
    rule: for the compound form the caller has already recorded a
    designation, and for the standalone form it has recorded nothing,
    because a location aspect is not equipment.
    """

    token = tokens[index]
    candidate = strip_boundary_punctuation(token.text)

    if not candidate.text:
        return None

    matched = match_location_aspect(candidate.text)

    if matched is None:
        return None

    location_text, product_length = matched

    return _build(
        canonical_text=canonical_text,
        section=section,
        paragraph=paragraph,
        line=line,
        tokens=tokens[index : index + 1],
        trims=(
            TrimmedToken(
                text=location_text,
                left=candidate.left,
                right=candidate.right + product_length,
            ),
        ),
        token_start=index,
        rule=LOCATION_ASPECT_RULE,
        status=EvidenceStatus.OBSERVED,
        designation=DesignationValue(normalized=location_text.upper()),
    )


def _match_quantity(
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    tokens: tuple[CanonicalTextToken, ...],
    index: int,
) -> tuple[EngineeringEvidence, int] | None:
    """
    The quantity rules, applied at one token position.

    Two shapes are accepted, both declared by ``RuleKind.QUANTITY``:
    a single token carrying number and unit together ("20kV"), or a
    numeric token followed by a unit token ("20" "kV"). Which rule
    applies is decided by the unit catalogue, never by this function.

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
                    canonical_text,
                    section,
                    paragraph,
                    line,
                    tokens[index : index + 1],
                    (first,),
                    index,
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
        # from surrounding words - an undeclared unit is not a unit.
        return None

    return (
        _quantity_evidence(
            canonical_text,
            section,
            paragraph,
            line,
            tokens[index : index + 2],
            (first, second),
            index,
            first.text,
            definition,
        ),
        2,
    )


def _quantity_evidence(
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    matched: tuple[CanonicalTextToken, ...],
    trims: tuple[TrimmedToken, ...],
    token_start: int,
    number_text: str,
    definition: UnitDefinition,
) -> EngineeringEvidence:
    """Applies the rule's normalization and validation policies to a
    matched quantity."""

    rule = QUANTITY_RULE_BY_TYPE[definition.evidence_type]
    value, outcome = parse_quantity(number_text)

    if outcome is QuantityParseOutcome.EXACT:
        return _build(
            canonical_text=canonical_text,
            section=section,
            paragraph=paragraph,
            line=line,
            tokens=matched,
            trims=trims,
            token_start=token_start,
            rule=rule,
            status=EvidenceStatus.OBSERVED,
            quantity=_quantity(value, definition),
        )

    if outcome is QuantityParseOutcome.AMBIGUOUS_SEPARATOR:
        # Carried **without** a normalised value. The observation is
        # real; the number is not settled, and a consumer must not be
        # able to read a guess as a measurement.
        return _build(
            canonical_text=canonical_text,
            section=section,
            paragraph=paragraph,
            line=line,
            tokens=matched,
            trims=trims,
            token_start=token_start,
            rule=rule,
            status=EvidenceStatus.AMBIGUOUS,
        )

    return _build(
        canonical_text=canonical_text,
        section=section,
        paragraph=paragraph,
        line=line,
        tokens=matched,
        trims=trims,
        token_start=token_start,
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
    canonical_text: CanonicalTextDocument,
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    tokens: tuple[CanonicalTextToken, ...],
    trims: tuple[TrimmedToken, ...],
    token_start: int,
    rule: ExtractionRule,
    status: EvidenceStatus,
    quantity: EngineeringQuantity | None = None,
    designation: DesignationValue | None = None,
) -> EngineeringEvidence:
    provenance = _provenance(
        section, paragraph, line, tokens, trims, token_start
    )

    return EngineeringEvidence(
        evidence_key=_evidence_key(
            canonical_text, rule, provenance, rule.evidence_type
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
    section: CanonicalTextSection,
    paragraph: CanonicalTextParagraph,
    line: CanonicalTextLine,
    tokens: tuple[CanonicalTextToken, ...],
    trims: tuple[TrimmedToken, ...],
    token_start: int,
) -> EvidenceProvenance:
    """
    Built from what the canonical text already recorded, never derived.

    Each token's character range is narrowed by whatever punctuation the
    trimming policy removed, so the range covers exactly the characters
    that produced the evidence - ``400 V,`` points at ``400 V``.

    Span references are **merged per span**: two tokens in the same span
    become one reference covering both, while two tokens in different
    spans stay two references. A single range spanning both would
    describe characters that do not exist in either span.
    """

    references: list[SpanReference] = []

    for token, trim in zip(tokens, trims, strict=True):
        origin = token.provenance
        start = origin.character_start + trim.left
        end = origin.character_end - trim.right

        if (
            references
            and references[-1].span_reading_order == origin.span_reading_order
        ):
            previous = references[-1]
            references[-1] = SpanReference(
                span_reading_order=previous.span_reading_order,
                character_start=previous.character_start,
                character_end=end,
            )
            continue

        references.append(
            SpanReference(
                span_reading_order=origin.span_reading_order,
                character_start=start,
                character_end=end,
            )
        )

    return EvidenceProvenance(
        page_number=section.page_number,
        section_index=section.section_index,
        paragraph_index=paragraph.paragraph_index,
        block_reading_order=paragraph.block_reading_order,
        line_index=line.line_index,
        token_start=token_start,
        token_end=token_start + len(tokens),
        spans=tuple(references),
        source_text=" ".join(trim.text for trim in trims),
    )


def _evidence_key(
    canonical_text: CanonicalTextDocument,
    rule: ExtractionRule,
    provenance: EvidenceProvenance,
    evidence_type: EvidenceType,
) -> str:
    """
    A deterministic identity for one observation.

    SHA-256 over the fields named in ``_KEY_FIELDS``, joined by ``|``.
    Deterministic by construction, so the same extraction over the same
    canonical text always produces the same keys - which is what lets the
    schema enforce idempotency rather than merely hoping for it.
    """

    material = "|".join(
        (
            str(canonical_text.document_id),
            canonical_text.content_checksum,
            rule.rule_id,
            rule.rule_version,
            evidence_type.value,
            str(provenance.page_number),
            str(provenance.paragraph_index),
            str(provenance.line_index),
            str(provenance.token_start),
            str(provenance.token_end),
        )
    )

    return hashlib.sha256(material.encode("utf-8")).hexdigest()
