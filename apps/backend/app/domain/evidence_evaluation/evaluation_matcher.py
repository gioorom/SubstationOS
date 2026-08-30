"""
Matching extracted evidence against a reference corpus (Milestone 28.2).

Pure and deterministic. Given what the extractor produced and what a
human annotated, it decides which items are true positives, which are
false positives and which are false negatives.

## The matching rule

Items are paired by **location** - page, paragraph, line and token range
- and then, within a location, by evidence type. Location is what can
pair them at all: two observations at the same place are candidates to be
the same observation, and two at different places are not, however
similar their text.

The second step exists because one token may carry more than one claim.
``+E01-QA1`` is a designation, and the ``+E01`` inside it is a location
aspect (EPIC 32.P1); both are recorded at that token, and each is judged
against its own annotation. Where a location holds exactly one annotation
and one observation that disagree about type, they stay paired and the
disagreement is reported as such - a rule that recorded a voltage where a
current was annotated should be told that, not told it missed one thing
and invented another.

A pair is a **true positive** only when everything agrees:

| Checked | Why |
|---|---|
| evidence type | a voltage recorded as a current is wrong, not "close" |
| observed text | the characters the document actually shows |
| status | `AMBIGUOUS` and `OBSERVED` are different claims |
| typed value | 20 kV and 20 V differ by three orders of magnitude |
| provenance | under the declared policy - see below |

Anything else is **both** a false positive and a false negative: the
extractor said something that is not so, *and* failed to say something
that is. Reporting it as a single softer outcome would let a rule that
puts values in the wrong place look almost right.

## Provenance is checked, not assumed

An observation with correct text and incorrect provenance is not a
match. A consumer that trusted its location would be reading the wrong
part of the document, and the whole value of this pipeline is that a
claim can be traced to the characters that support it.
"""

from __future__ import annotations

from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidence,
    EvidenceProvenance,
)
from app.domain.evidence_evaluation.corpus_models import (
    ExpectedObservation,
    ReferenceDocument,
)
from app.domain.evidence_evaluation.evaluation_models import (
    DocumentEvaluation,
    EvaluationOutcome,
    EvidenceEvaluationResult,
    MismatchReason,
    ProvenanceMatchPolicy,
)

_Location = tuple[int, int, int, int, int]


def evaluate_document(
    document: ReferenceDocument,
    extracted: tuple[EngineeringEvidence, ...],
    *,
    provenance_policy: ProvenanceMatchPolicy = ProvenanceMatchPolicy.EXACT,
) -> DocumentEvaluation:
    """
    Compare one document's extracted evidence with its annotations.

    Results are ordered deterministically - by location, then by evidence
    type - so two runs produce identical reports and a diff between two
    reports shows only real changes.
    """

    expected_by_location: dict[_Location, list[ExpectedObservation]] = {}
    actual_by_location: dict[_Location, list[EngineeringEvidence]] = {}

    for item in document.expected:
        expected_by_location.setdefault(
            _location_of(item.provenance), []
        ).append(item)

    for item in extracted:
        actual_by_location.setdefault(
            _location_of(item.provenance), []
        ).append(item)

    results: list[EvidenceEvaluationResult] = []

    for location in sorted(
        set(expected_by_location) | set(actual_by_location)
    ):
        for expectation, actual in _pair(
            expected_by_location.get(location, []),
            actual_by_location.get(location, []),
        ):
            results.extend(
                _classify(location, expectation, actual, provenance_policy)
            )

    return DocumentEvaluation(
        document_ref=document.document_ref,
        title=document.title,
        results=tuple(results),
    )


def _pair(
    expectations: list[ExpectedObservation],
    actuals: list[EngineeringEvidence],
) -> list[tuple[ExpectedObservation | None, EngineeringEvidence | None]]:
    """
    Which annotation is being compared with which observation, within one
    location.

    A location usually holds one of each and this is then a single pair.
    It holds two when one token carries two claims - ``+E01-QA1`` is a
    designation, and the ``+E01`` inside it is a location aspect - and
    they must be judged separately: reporting one of them would let a
    rule that produced neither look half right.

    Paired **by evidence type first**, because that is what makes two
    items at one place the same claim. What is left over is paired only
    when exactly one annotation and exactly one observation remain, which
    is the case where the extractor recorded the wrong type at the right
    place - and that disagreement is worth naming, so it stays a pair and
    ``_disagreement`` reports ``EVIDENCE_TYPE``. Anything still unpaired
    after that is unpaired, which it is.

    Ordered by evidence type so two runs over one document produce
    identical reports.
    """

    remaining_expected = list(expectations)
    remaining_actual = list(actuals)
    pairs: list[
        tuple[ExpectedObservation | None, EngineeringEvidence | None]
    ] = []

    for expectation in list(remaining_expected):
        match = next(
            (
                item
                for item in remaining_actual
                if item.evidence_type is expectation.evidence_type
            ),
            None,
        )

        if match is None:
            continue

        remaining_expected.remove(expectation)
        remaining_actual.remove(match)
        pairs.append((expectation, match))

    if len(remaining_expected) == 1 and len(remaining_actual) == 1:
        pairs.append((remaining_expected[0], remaining_actual[0]))
        remaining_expected.clear()
        remaining_actual.clear()

    pairs.extend((expectation, None) for expectation in remaining_expected)
    pairs.extend((None, actual) for actual in remaining_actual)

    return sorted(pairs, key=_pair_order)


def _pair_order(
    pair: tuple[ExpectedObservation | None, EngineeringEvidence | None],
) -> str:
    """The evidence type of whichever side is present - a total order over
    pairs that does not depend on which side happened to be missing."""

    expectation, actual = pair

    if expectation is not None:
        return expectation.evidence_type.value

    assert actual is not None
    return actual.evidence_type.value


def _classify(
    location: _Location,
    expectation: ExpectedObservation | None,
    actual: EngineeringEvidence | None,
    provenance_policy: ProvenanceMatchPolicy,
) -> list[EvidenceEvaluationResult]:
    if expectation is not None and actual is None:
        return [
            _result(
                EvaluationOutcome.FALSE_NEGATIVE,
                location,
                expectation=expectation,
                reason=MismatchReason.UNPAIRED,
            )
        ]

    if expectation is None and actual is not None:
        return [
            _result(
                EvaluationOutcome.FALSE_POSITIVE,
                location,
                actual=actual,
                reason=MismatchReason.UNPAIRED,
            )
        ]

    reason = _disagreement(expectation, actual, provenance_policy)

    if reason is None:
        return [
            _result(
                EvaluationOutcome.TRUE_POSITIVE,
                location,
                expectation=expectation,
                actual=actual,
            )
        ]

    # Paired by location and disagreeing about what is there: the
    # extractor claimed something untrue *and* missed something true.
    # Two results, because one softer outcome would hide half of it.
    return [
        _result(
            EvaluationOutcome.FALSE_POSITIVE,
            location,
            actual=actual,
            reason=reason,
        ),
        _result(
            EvaluationOutcome.FALSE_NEGATIVE,
            location,
            expectation=expectation,
            reason=reason,
        ),
    ]


def _disagreement(
    expectation: ExpectedObservation,
    actual: EngineeringEvidence,
    provenance_policy: ProvenanceMatchPolicy,
) -> MismatchReason | None:
    """The first thing the two disagree about, or ``None`` if they agree
    on everything."""

    if expectation.evidence_type is not actual.evidence_type:
        return MismatchReason.EVIDENCE_TYPE

    if expectation.observed_text != actual.observed_text:
        return MismatchReason.OBSERVED_TEXT

    if expectation.status is not actual.status:
        return MismatchReason.STATUS

    if expectation.quantity != actual.quantity:
        return MismatchReason.QUANTITY

    if expectation.designation != actual.designation:
        return MismatchReason.DESIGNATION

    if not provenance_matches(
        expectation.provenance, actual.provenance, provenance_policy
    ):
        return MismatchReason.PROVENANCE

    return None


def provenance_matches(
    expected: EvidenceProvenance,
    actual: EvidenceProvenance,
    policy: ProvenanceMatchPolicy,
) -> bool:
    """
    Whether two provenances agree, under a **named** policy.

    ``EXACT`` compares the whole chain including the character ranges of
    every canonical span. ``LOCATION_ONLY`` stops at the token range and
    accepts any character ranges - coarser on purpose, declared on
    purpose, and never the default.
    """

    if _location_of(expected) != _location_of(actual):
        return False

    if expected.block_reading_order != actual.block_reading_order:
        return False

    if expected.section_index != actual.section_index:
        return False

    if policy is ProvenanceMatchPolicy.LOCATION_ONLY:
        return True

    return expected.spans == actual.spans


def _location_of(provenance: EvidenceProvenance) -> _Location:
    return (
        provenance.page_number,
        provenance.paragraph_index,
        provenance.line_index,
        provenance.token_start,
        provenance.token_end,
    )


def _result(
    outcome: EvaluationOutcome,
    location: _Location,
    *,
    expectation: ExpectedObservation | None = None,
    actual: EngineeringEvidence | None = None,
    reason: MismatchReason | None = None,
) -> EvidenceEvaluationResult:
    source = actual if actual is not None else expectation

    return EvidenceEvaluationResult(
        outcome=outcome,
        evidence_type=source.evidence_type,
        observed_text=source.observed_text,
        rule_id=source.rule_id,
        rule_version=source.rule_version,
        location=location,
        expected=expectation,
        actual=actual,
        mismatch_reason=reason,
    )
