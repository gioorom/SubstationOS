"""
Validation of an assembled evidence set (Milestone 28.1).

Checked *before* anything is stored, because an evidence set is trusted
by every future knowledge-construction milestone. A set that reached
storage with a provenance pointing at a line that does not exist would
surface later as an inexplicable entity rather than as the extractor bug
it actually is.

Pure: it reads the set and the canonical text it claims to describe, and
returns the first violation or ``None``.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.engineering_evidence.evidence_failures import (
    EvidenceFailure,
    EvidenceFailureCode,
)
from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidence,
    EngineeringEvidenceSet,
    EvidenceStatus,
    EvidenceType,
)
from app.domain.engineering_evidence.evidence_rules import RULES_BY_ID
from app.domain.engineering_evidence.evidence_units import find_unit

_QUANTITY_TYPES = frozenset(
    {
        EvidenceType.VOLTAGE_VALUE,
        EvidenceType.CURRENT_VALUE,
        EvidenceType.POWER_VALUE,
        EvidenceType.CABLE_SECTION_VALUE,
    }
)


def validate_evidence_set(
    evidence_set: EngineeringEvidenceSet,
    canonical_text: CanonicalTextDocument,
) -> EvidenceFailure | None:
    """Return the first violation, or ``None`` if the set is sound."""

    if evidence_set.content_checksum != canonical_text.content_checksum:
        return EvidenceFailure(
            code=EvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            message="The evidence set and its canonical text disagree "
            "about which document version was observed.",
        )

    lines = _line_index(canonical_text)

    for item in evidence_set.evidence:
        violation = _validate_item(item, lines)

        if violation is not None:
            return violation

    return None


def _validate_item(
    item: EngineeringEvidence, lines: dict[tuple[int, int, int], int]
) -> EvidenceFailure | None:
    rule = RULES_BY_ID.get(item.rule_id)

    if rule is None or rule.rule_version != item.rule_version:
        return EvidenceFailure(
            code=EvidenceFailureCode.INVALID_EXTRACTION_RULE,
            message=f"Evidence cites rule '{item.rule_id}' version "
            f"'{item.rule_version}', which the catalogue does not "
            "declare.",
        )

    if rule.evidence_type is not item.evidence_type:
        return EvidenceFailure(
            code=EvidenceFailureCode.INVALID_EXTRACTION_RULE,
            message=f"Rule '{item.rule_id}' declares "
            f"'{rule.evidence_type.value}' and produced "
            f"'{item.evidence_type.value}'.",
        )

    provenance = item.provenance
    key = (
        provenance.page_number,
        provenance.paragraph_index,
        provenance.line_index,
    )
    token_count = lines.get(key)

    if token_count is None:
        return EvidenceFailure(
            code=EvidenceFailureCode.INVALID_PROVENANCE,
            message=f"Evidence '{item.observed_text}' cites page "
            f"{provenance.page_number}, paragraph "
            f"{provenance.paragraph_index}, line "
            f"{provenance.line_index}, which the canonical text does "
            "not contain.",
        )

    if (
        provenance.token_start < 0
        or provenance.token_end > token_count
        or provenance.token_start >= provenance.token_end
    ):
        return EvidenceFailure(
            code=EvidenceFailureCode.INVALID_PROVENANCE,
            message=f"Evidence '{item.observed_text}' cites tokens "
            f"[{provenance.token_start}:{provenance.token_end}] of a "
            f"line holding {token_count}.",
        )

    if not provenance.spans:
        return EvidenceFailure(
            code=EvidenceFailureCode.INVALID_PROVENANCE,
            message=f"Evidence '{item.observed_text}' cites no canonical "
            "span; its characters could not be located.",
        )

    for span in provenance.spans:
        if span.character_start < 0 or span.character_end <= span.character_start:
            return EvidenceFailure(
                code=EvidenceFailureCode.INVALID_PROVENANCE,
                message=f"Evidence '{item.observed_text}' cites an empty "
                "or reversed character range.",
            )

    return _validate_value(item)


def _validate_value(
    item: EngineeringEvidence,
) -> EvidenceFailure | None:
    """
    Exactly one typed value, matching the evidence type.

    An ``AMBIGUOUS`` quantity deliberately carries none: the observation
    is real and the number is not settled, and a consumer must never be
    able to read a guess as a measurement.
    """

    if item.evidence_type is EvidenceType.DESIGNATION:
        if item.designation is None or item.quantity is not None:
            return EvidenceFailure(
                code=EvidenceFailureCode.EVIDENCE_VALIDATION_FAILURE,
                message=f"Designation evidence '{item.observed_text}' "
                "does not carry exactly a designation value.",
            )

        return None

    if item.evidence_type not in _QUANTITY_TYPES:
        return EvidenceFailure(
            code=EvidenceFailureCode.EVIDENCE_VALIDATION_FAILURE,
            message=f"Evidence type '{item.evidence_type.value}' has no "
            "declared value shape.",
        )

    if item.designation is not None:
        return EvidenceFailure(
            code=EvidenceFailureCode.EVIDENCE_VALIDATION_FAILURE,
            message=f"Quantity evidence '{item.observed_text}' also "
            "carries a designation value.",
        )

    if item.status is EvidenceStatus.OBSERVED:
        if item.quantity is None:
            return EvidenceFailure(
                code=EvidenceFailureCode.INVALID_ENGINEERING_QUANTITY,
                message=f"Observed quantity '{item.observed_text}' "
                "carries no value.",
            )

        if find_unit(item.quantity.unit) is None:
            return EvidenceFailure(
                code=EvidenceFailureCode.UNSUPPORTED_UNIT,
                message=f"Quantity '{item.observed_text}' cites unit "
                f"'{item.quantity.unit}', which the unit catalogue does "
                "not declare.",
            )

    return None


def _line_index(
    canonical_text: CanonicalTextDocument,
) -> dict[tuple[int, int, int], int]:
    """How many tokens each (page, paragraph, line) actually holds - so
    provenance is checked against the source rather than trusted."""

    return {
        (
            section.page_number,
            paragraph.paragraph_index,
            line.line_index,
        ): len(line.tokens)
        for section in canonical_text.sections
        for paragraph in section.paragraphs
        for line in paragraph.lines
    }
