"""
Tests for the deterministic fact constructor (Milestone 29.2).

Driven through the **real** pipeline - segmenter, extractor, resolver -
so a case is described by the text a document contains rather than by
hand-built entities. A constructor tested against entities somebody typed
would prove nothing about what the rules do to real documents.

The realistic cases the milestone names are pinned in
``test_realistic_cases`` at the end of this file, each with the reason
its outcome is what it is.
"""

from __future__ import annotations

import dataclasses

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    EngineeringFact,
    EngineeringFactSet,
    FactStatus,
    SupportRole,
)
from app.domain.engineering_facts.fact_predicates import FactPredicate
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)


def _entities(*lines: str, **overrides):
    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(index, index, text)
                    for index, text in enumerate(lines)
                ],
            ),
        ),
        **overrides,
    )

    return resolve_entities(extract_evidence(segment_canonical_document(source)))


def _facts(*lines: str, **overrides):
    return construct_facts(_entities(*lines, **overrides))


def _labels(entity_set, fact_set) -> list[tuple[str, str, str]]:
    """Facts rendered as readable triples, for assertions that are about
    *which* association was made."""

    by_key = {entity.entity_key: entity.label for entity in entity_set.entities}

    return [
        (
            by_key[fact.subject_entity_key],
            fact.predicate.value,
            by_key[fact.object_entity_key],
        )
        for fact in fact_set.facts
    ]


def _triples(*lines: str) -> list[tuple[str, str, str]]:
    entity_set = _entities(*lines)

    return _labels(entity_set, construct_facts(entity_set))


# --- The rule -------------------------------------------------------------------


def test_a_designation_and_a_quantity_on_one_line_associate() -> None:
    assert _triples("TR1 630 kVA") == [
        ("TR1", "has_associated_quantity", "630 kVA")
    ]


def test_observations_on_different_lines_do_not_associate() -> None:
    """Same page, same block, different lines. The rule is same-line, and
    nothing widens it."""

    assert _triples("TR1", "630 kVA") == []


def test_observations_in_different_paragraphs_do_not_associate() -> None:
    """A paragraph rule is deliberately not implemented - see
    ``fact_construction_rules``."""

    source = representation(
        page(
            1,
            text_block(0, span(0, 0, "TR1")),
            text_block(1, span(0, 0, "630 kVA")),
        )
    )
    entity_set = resolve_entities(
        extract_evidence(segment_canonical_document(source))
    )

    assert construct_facts(entity_set).facts == ()


def test_observations_on_different_pages_do_not_associate() -> None:
    source = representation(
        page(1, text_block(0, span(0, 0, "TR1"))),
        page(2, text_block(0, span(0, 0, "630 kVA"))),
    )
    entity_set = resolve_entities(
        extract_evidence(segment_canonical_document(source))
    )

    assert construct_facts(entity_set).facts == ()


def test_a_quantity_is_not_attached_by_nearest_distance() -> None:
    """
    The quantity on the designation's own line associates; the one two
    lines away does not, however few tokens separate them.

    There is no distance score anywhere - proximity is not a rule.
    """

    assert _triples(
        "TR1 630 kVA",
        "",
        "20 kV",
    ) == [("TR1", "has_associated_quantity", "630 kVA")]


# --- Cardinality ------------------------------------------------------------------


def test_one_designation_and_several_quantities_associate_with_each(
) -> None:
    """Permitted **explicitly** by the declared cardinality policy: a
    data-sheet line listing a designation and several ratings is a real
    shape, and associating them says only that they appeared together."""

    assert _triples("TR1 20 kV 630 kVA") == [
        ("TR1", "has_associated_quantity", "20 kV"),
        ("TR1", "has_associated_quantity", "630 kVA"),
    ]


def test_two_designations_and_one_quantity_produce_no_fact() -> None:
    """
    The cartesian case the milestone forbids.

    ``TR1 TR2 630 kVA`` must not become two facts: the line does not say
    which transformer the rating belongs to, and a guess would put a
    rating on the wrong equipment.
    """

    result = _facts("TR1 TR2 630 kVA")

    assert result.facts == ()
    assert len(result.diagnostics) == 1
    assert (
        result.diagnostics[0].reason is AmbiguityReason.MULTIPLE_SUBJECTS
    )


def test_the_ambiguity_diagnostic_names_the_candidates_not_a_pairing(
) -> None:
    """It records what was on the line, without asserting which is
    which - that is precisely what could not be determined."""

    entity_set = _entities("TR1 TR2 630 kVA")
    diagnostic = construct_facts(entity_set).diagnostics[0]

    assert len(diagnostic.subject_entity_keys) == 2
    assert len(diagnostic.object_entity_keys) == 1
    assert not hasattr(diagnostic, "subject_entity_key")
    assert not hasattr(diagnostic, "status")


def test_an_ambiguous_line_does_not_suppress_an_unambiguous_one() -> None:
    """The rule was satisfied on the clean line; the diagnostic still
    records where it was not."""

    result = _facts("TR1 630 kVA", "TR1 TR2 20 kV")

    assert len(result.facts) == 1
    assert len(result.diagnostics) == 1


def test_a_line_with_no_quantity_produces_nothing() -> None:
    assert _facts("TR1 e TR2 in cabina").facts == ()
    assert _facts("TR1 e TR2 in cabina").diagnostics == ()


def test_a_line_with_no_designation_produces_nothing() -> None:
    assert _facts("Potenza 630 kVA nominale").facts == ()


# --- The predicate stays narrow ------------------------------------------------------


def test_the_predicate_is_always_has_associated_quantity() -> None:
    result = _facts("TR1 20 kV 630 kVA 1250 A")

    assert {fact.predicate for fact in result.facts} == {
        FactPredicate.HAS_ASSOCIATED_QUANTITY
    }


def test_no_semantic_predicate_exists_in_the_vocabulary() -> None:
    """
    ``HAS_RATED_POWER`` would claim the quantity is the equipment's rated
    power. Nothing in this pipeline establishes that.

    ``HAS_LOCATION_ASPECT`` (EPIC 32.P1) is structural for the same
    reason: it says the document wrote ``+E01`` inside ``+E01-QA1``, not
    that the equipment is located there. The semantic reading is
    ``IS_LOCATED_IN``, and it lives one layer up behind a reviewed rule -
    which is why ``BELONGS_TO`` remains forbidden here.
    """

    declared = {member.name for member in FactPredicate}

    assert declared == {
        "HAS_ASSOCIATED_QUANTITY",
        "HAS_LOCATION_ASPECT",
    }
    for forbidden in (
        "HAS_RATED_POWER",
        "HAS_VOLTAGE",
        "HAS_CURRENT",
        "HAS_POWER",
        "HAS_CABLE_SECTION",
        "CONNECTED_TO",
        "PROTECTS",
        "FEEDS",
        "BELONGS_TO",
        "IS_A",
    ):
        assert forbidden not in declared


def test_the_quantity_kind_is_not_promoted_into_the_predicate() -> None:
    """A voltage and a power produce the *same* predicate. The evidence
    type stays reachable through the support, where a later milestone can
    use it under a rule of its own."""

    result = _facts("TR1 20 kV 630 kVA")
    predicates = {fact.predicate for fact in result.facts}
    supported_types = {
        reference.evidence_type.value
        for fact in result.facts
        for reference in fact.object_support
    }

    assert len(predicates) == 1
    assert supported_types == {"voltage_value", "power_value"}


def test_a_fact_carries_no_role_or_property_field() -> None:
    names = {field.name for field in dataclasses.fields(EngineeringFact)}

    assert names & {
        "role",
        "property_name",
        "property",
        "rated_value",
        "unit",
        "equipment_type",
        "connected_to",
    } == set()


# --- Support and provenance ------------------------------------------------------------


def test_a_fact_enumerates_subject_object_and_supporting_evidence(
) -> None:
    entity_set = _entities("TR1 630 kVA")
    fact = construct_facts(entity_set).facts[0]

    assert fact.subject_entity_key
    assert fact.object_entity_key
    assert len(fact.subject_support) == 1
    assert len(fact.object_support) == 1
    assert {reference.role for reference in fact.support} == {
        SupportRole.SUBJECT,
        SupportRole.OBJECT,
    }


def test_support_resolves_to_the_evidence_the_entities_cite() -> None:
    """Support is reachable through immutable evidence references - never
    reconstructed later by searching text."""

    entity_set = _entities("TR1 630 kVA")
    fact = construct_facts(entity_set).facts[0]
    entity_keys = {
        key
        for entity in entity_set.entities
        for key in entity.evidence_keys
    }

    assert set(fact.support_keys) <= entity_keys


def test_support_records_the_line_the_rule_matched_on() -> None:
    """Without it, a same-line association could not be re-checked - and
    an unverifiable rule is an assertion."""

    fact = _facts("Dati", "TR1 630 kVA").facts[0]

    assert fact.supporting_lines == ((1, 0, 1),)
    assert all(
        reference.line_index == 1 for reference in fact.support
    )


def test_the_same_text_on_two_lines_is_two_facts_not_one() -> None:
    """
    ``630 kVA`` written on two lines is **two quantity entities** -
    Milestone 29.1 never merges quantity observations, because two
    identical ratings may belong to two pieces of equipment. So there are
    two distinct pairs and two facts, each supported from its own line.

    Grouping them here would silently undo that decision one layer up.
    """

    result = _facts("TR1 630 kVA", "TR1 630 kVA")
    objects = {fact.object_entity_key for fact in result.facts}

    assert len(result.facts) == 2
    assert len(objects) == 2
    assert [fact.supporting_lines for fact in result.facts] == [
        ((1, 0, 0),),
        ((1, 0, 1),),
    ]


def test_a_designation_written_twice_on_one_line_is_one_subject(
) -> None:
    """
    ``Trasformatore TR1, sigla TR1, 630 kVA`` names one transformer
    twice, not two transformers.

    Counting observations rather than entities would report the line as
    ambiguous and decline a perfectly determinate association - so the
    rule counts distinct subjects, and both observations become support
    for the one fact.
    """

    result = _facts("Trasformatore TR1, sigla TR1, 630 kVA")

    assert len(result.facts) == 1
    assert result.diagnostics == ()
    assert len(result.facts[0].subject_support) == 2
    assert len(result.facts[0].object_support) == 1


# --- Status is derived -------------------------------------------------------------------


def test_a_fact_over_resolved_entities_is_constructed() -> None:
    assert _facts("TR1 630 kVA").facts[0].status is FactStatus.CONSTRUCTED


def test_a_fact_over_an_ambiguous_quantity_is_ambiguous() -> None:
    """
    The association is real - they are on one line - and the *value* is
    not settled. ``1.250`` could be 1250 or 1.25, so the quantity entity
    is ambiguous and the fact inherits it. Grouping never adds certainty
    the evidence did not carry.
    """

    fact = _facts("TR1 1.250 kVA").facts[0]

    assert fact.status is FactStatus.AMBIGUOUS


# --- Deterministic identity ------------------------------------------------------------------


def test_the_same_entities_produce_an_equal_fact_set() -> None:
    entity_set = _entities("TR1 630 kVA", "TR2 20 kV")

    assert construct_facts(entity_set) == construct_facts(entity_set)


def test_a_different_source_produces_different_fact_keys() -> None:
    first = _facts("TR1 630 kVA")
    second = _facts("TR1 630 kVA", content_checksum="d" * 64)

    assert first.facts[0].fact_key != second.facts[0].fact_key


def test_a_policy_version_change_produces_a_distinct_fact_set() -> None:
    entity_set = _entities("TR1 630 kVA")

    baseline = construct_facts(entity_set)
    candidate = construct_facts(entity_set, fact_policy_version="2.0")

    assert candidate != baseline
    assert candidate.fact_policy_version == "2.0"


def test_the_set_records_the_catalogue_and_source_that_produced_it(
) -> None:
    result = _facts("TR1 630 kVA")
    fact = result.facts[0]

    assert result.resolution_policy_version == "1.0"
    assert result.fact_policy_version == "1.0"
    assert fact.construction_rule_id == "same_line_association"
    assert fact.construction_rule_version == "1.0"
    assert fact.fact_version == "1.0"


def test_the_set_carries_no_timestamp() -> None:
    names = {
        field.name for field in dataclasses.fields(EngineeringFactSet)
    }

    assert names & {"created_at", "constructed_at", "timestamp"} == set()


# --- The realistic cases, each with its reason ---------------------------------------------------


def test_realistic_cases() -> None:
    """
    Every case the milestone names, with the outcome and the reason.

    | Document text | Facts | Why |
    |---|---|---|
    | ``TR1 630 kVA`` | 1 | one designation, one quantity, one line |
    | ``TR1 20 kV 630 kVA`` | 2 | one designation, two quantities - declared one-to-many policy |
    | ``TR1 TR2 630 kVA`` | 0 | two designations: which one the rating belongs to is not stated |
    | ``TR1`` / ``630 kVA`` | 0 | different lines; the rule is same-line |
    | ``TR1 — 630 kVA`` | 1 | the dash is just another token; punctuation carries no meaning here |
    | ``TR1 \\| 630 kVA`` | 1 | as above - a pipe is not a separator this layer interprets |
    | ``TR1 630 kVA 20/0.4 kV`` | 1 | ``20/0.4`` is not a number the extractor reads, so there is no second quantity to associate |

    The rules were **not** broadened to make every example produce
    output. Two of them deliberately produce none.
    """

    assert _triples("TR1 630 kVA") == [
        ("TR1", "has_associated_quantity", "630 kVA")
    ]
    assert _triples("TR1 20 kV 630 kVA") == [
        ("TR1", "has_associated_quantity", "20 kV"),
        ("TR1", "has_associated_quantity", "630 kVA"),
    ]
    assert _triples("TR1 TR2 630 kVA") == []
    assert _triples("TR1", "630 kVA") == []
    assert _triples("TR1 — 630 kVA") == [
        ("TR1", "has_associated_quantity", "630 kVA")
    ]
    assert _triples("TR1 | 630 kVA") == [
        ("TR1", "has_associated_quantity", "630 kVA")
    ]
    assert _triples("TR1 630 kVA 20/0.4 kV") == [
        ("TR1", "has_associated_quantity", "630 kVA")
    ]


def test_the_dual_ratio_voltage_is_not_silently_dropped_into_a_fact(
) -> None:
    """
    ``20/0.4 kV`` produces no quantity at all - the extractor does not
    read a ratio as a number - so no fact mentions it. That is a
    documented gap in extraction, not an association this layer declined.
    """

    entity_set = _entities("TR1 630 kVA 20/0.4 kV")
    quantities = [
        entity.label
        for entity in entity_set.entities
        if entity.quantity is not None
    ]

    assert quantities == ["630 kVA"]
