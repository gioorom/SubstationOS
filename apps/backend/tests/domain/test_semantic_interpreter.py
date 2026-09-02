"""
Tests for the deterministic semantic interpreter (Milestone 30.1).

Driven through the **real** pipeline - segmenter, extractor, resolver,
fact constructor - so a case is described by the text a document contains
rather than by hand-built facts. An interpreter tested against facts
somebody typed would prove nothing about what the rules do to real
documents.

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
from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_semantics.semantic_interpreter import (
    interpret_facts,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
    EngineeringSemanticStatement,
    SemanticAmbiguityReason,
    SemanticStatementStatus,
)
from app.domain.engineering_semantics.semantic_rules import (
    POWER_VALUE_EVIDENCE_TYPE,
    IS_LOCATED_IN_RULE,
    RATED_POWER_RULE,
    SEMANTIC_RULES,
)
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)


def _pipeline(*lines: str, **overrides):
    """Text in, entity set and fact set out - the whole deterministic
    pipeline beneath this layer."""

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
    entity_set = resolve_entities(
        extract_evidence(segment_canonical_document(source))
    )

    return entity_set, construct_facts(entity_set)


def _interpret(*lines: str, **overrides):
    _, fact_set = _pipeline(*lines, **overrides)

    return interpret_facts(fact_set)


def _triples(*lines: str) -> list[tuple[str, str, str]]:
    """Statements rendered readably, for assertions about *which* meaning
    was assigned."""

    entity_set, fact_set = _pipeline(*lines)
    labels = {
        entity.entity_key: entity.label for entity in entity_set.entities
    }

    return [
        (
            labels[statement.subject_entity_key],
            statement.statement_type.value,
            labels[statement.object_entity_key],
        )
        for statement in interpret_facts(fact_set).statements
    ]


# --- The rule ---------------------------------------------------------------------


def test_an_associated_power_becomes_a_rated_power_statement() -> None:
    assert _triples("TR1 630 kVA") == [
        ("TR1", "has_rated_power", "630 kVA")
    ]


def test_the_statement_cites_the_rule_that_produced_it() -> None:
    statement = _interpret("TR1 630 kVA").statements[0]

    assert statement.semantic_rule_id == (
        "rated_power_from_associated_power_quantity"
    )
    assert statement.semantic_rule_version == "1.0"
    assert statement.semantic_contract_version == "1.0"


def test_only_the_power_of_a_mixed_line_is_interpreted() -> None:
    """The voltage association is real and this catalogue assigns it no
    meaning - it is ignored, not refused."""

    assert _triples("TR1 20 kV 630 kVA") == [
        ("TR1", "has_rated_power", "630 kVA")
    ]


# --- Quantities that mean nothing here ----------------------------------------------


def test_an_associated_voltage_produces_no_statement() -> None:
    """
    A voltage beside a designation may be a rated voltage, a test
    voltage, an insulation level, or the voltage of the busbar the
    equipment connects to. The association does not say which, so no
    rule ships for it.
    """

    result = _interpret("TR1 20 kV")

    assert result.statements == ()
    assert result.diagnostics == ()


def test_an_associated_cable_section_produces_no_statement() -> None:
    result = _interpret("TR1 240 mm²")

    assert result.statements == ()


def test_an_associated_current_produces_no_statement() -> None:
    result = _interpret("TR1 1250 A")

    assert result.statements == ()


def test_a_document_with_no_association_produces_no_statement() -> None:
    result = _interpret("Trasformatore TR1 in cabina")

    assert result.is_empty


# --- Ambiguity ------------------------------------------------------------------------


def test_two_associated_powers_produce_no_statement() -> None:
    """
    Which figure is the rating cannot be decided.

    A fact carries entity **keys**, not values, so this layer cannot even
    see whether the two agree - and reaching for them would mean
    depending on entities, which is not its business. Interpreting either
    would be a coin flip on an equipment rating.
    """

    result = _interpret("TR1 630 kVA 800 kVA")

    assert result.statements == ()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason is (
        SemanticAmbiguityReason.MULTIPLE_CANDIDATE_QUANTITIES
    )
    assert len(result.diagnostics[0].candidate_fact_keys) == 2


def test_the_diagnostic_names_no_object_and_no_statement_type(
) -> None:
    """Which quantity carries the meaning is exactly what could not be
    decided."""

    diagnostic = _interpret("TR1 630 kVA 800 kVA").diagnostics[0]

    assert diagnostic.subject_entity_key
    assert not hasattr(diagnostic, "object_entity_key")
    assert not hasattr(diagnostic, "statement_type")
    assert not hasattr(diagnostic, "status")


def test_one_ambiguous_subject_does_not_suppress_another_subject(
) -> None:
    result = _interpret("TR1 630 kVA 800 kVA", "TR2 400 kVA")

    assert len(result.statements) == 1
    assert len(result.diagnostics) == 1


# --- Status is derived --------------------------------------------------------------------


def test_a_statement_over_a_constructed_fact_is_interpreted() -> None:
    statement = _interpret("TR1 630 kVA").statements[0]

    assert statement.status is SemanticStatementStatus.INTERPRETED


def test_a_statement_over_an_ambiguous_fact_is_ambiguous() -> None:
    """
    Interpretation adds meaning, never certainty.

    ``1.250`` could be 1250 or 1.25, so the quantity - and the fact
    resting on it - is ambiguous. The meaning holds: it is still a rated
    power. The figure does not.
    """

    statement = _interpret("TR1 1.250 kVA").statements[0]

    assert statement.status is SemanticStatementStatus.AMBIGUOUS


# --- The support chain ----------------------------------------------------------------------


def test_a_statement_cites_the_fact_that_supports_it() -> None:
    _, fact_set = _pipeline("TR1 630 kVA")
    statement = interpret_facts(fact_set).statements[0]

    assert statement.supporting_fact_keys == (fact_set.facts[0].fact_key,)


def test_the_cited_fact_relates_the_entities_the_statement_names(
) -> None:
    """The link that makes the chain sound: the statement's subject and
    object are the fact's subject and object."""

    _, fact_set = _pipeline("TR1 630 kVA")
    statement = interpret_facts(fact_set).statements[0]
    fact = fact_set.fact(statement.supporting_fact_keys[0])

    assert fact.subject_entity_key == statement.subject_entity_key
    assert fact.object_entity_key == statement.object_entity_key


def test_the_chain_reaches_the_evidence_through_the_fact() -> None:
    """
    Statement -> fact -> entity keys and evidence keys.

    The statement owns no provenance; every link is a key into an
    immutable record below it.
    """

    entity_set, fact_set = _pipeline("TR1 630 kVA")
    statement = interpret_facts(fact_set).statements[0]
    fact = fact_set.fact(statement.supporting_fact_keys[0])
    subject = entity_set.entity(fact.subject_entity_key)

    assert fact.support_keys
    assert subject.evidence_keys
    assert set(
        reference.evidence_key for reference in fact.subject_support
    ) <= set(subject.evidence_keys)


def test_a_statement_duplicates_no_fact_payload() -> None:
    """No support references, no locations, no observed text - those live
    on the fact, which stays the single account of why two entities are
    related."""

    names = {
        field.name
        for field in dataclasses.fields(EngineeringSemanticStatement)
    }

    assert names & {
        "support",
        "observed_text",
        "page_number",
        "line_index",
        "predicate",
        "evidence_key",
    } == set()


def test_a_statement_carries_no_value_or_unit() -> None:
    """The figure lives on the quantity entity. A copy here would be a
    second source of truth for a rated value."""

    names = {
        field.name
        for field in dataclasses.fields(EngineeringSemanticStatement)
    }

    assert names & {
        "value",
        "unit",
        "quantity",
        "rated_value",
        "confidence",
    } == set()


# --- The vocabulary stays closed --------------------------------------------------------------


def test_only_has_rated_power_is_declared() -> None:
    declared = {member.name for member in SemanticStatementType}

    assert declared == {"HAS_RATED_POWER", "IS_LOCATED_IN"}
    for forbidden in (
        "HAS_NOMINAL_VOLTAGE",
        "HAS_NOMINAL_CURRENT",
        "HAS_CABLE_SECTION",
        "CONNECTED_TO",
        "PROTECTS",
        "SUPPLIES",
        "IS_TRANSFORMER",
        "IS_BREAKER",
        "BELONGS_TO",
        "IS_PRIMARY_EQUIPMENT",
    ):
        assert forbidden not in declared


def test_the_catalogue_holds_exactly_the_declared_rules() -> None:
    """One rule per meaning this platform can assign, and no other. The
    catalogue is the whole of what the interpreter runs, so a rule that
    is not here does not exist."""

    assert list(SEMANTIC_RULES) == [RATED_POWER_RULE, IS_LOCATED_IN_RULE]


def test_the_declared_evidence_type_matches_the_evidence_vocabulary(
) -> None:
    """
    The drift guard for the one string this layer restates.

    ``EvidenceType`` lives in a context the semantic layer is not
    permitted to import, so the rule names the required type as a
    literal. This test - which may import it - proves the two agree, so
    a rename upstream cannot silently stop the rule matching.
    """

    assert POWER_VALUE_EVIDENCE_TYPE == EvidenceType.POWER_VALUE.value
    assert RATED_POWER_RULE.required_evidence_types == (
        EvidenceType.POWER_VALUE.value,
    )


# --- Deterministic identity ----------------------------------------------------------------------


def test_the_same_facts_produce_an_equal_semantic_set() -> None:
    _, fact_set = _pipeline("TR1 630 kVA", "TR2 400 kVA")

    assert interpret_facts(fact_set) == interpret_facts(fact_set)


def test_a_different_source_produces_different_statement_keys() -> None:
    first = _interpret("TR1 630 kVA")
    second = _interpret("TR1 630 kVA", content_checksum="d" * 64)

    assert (
        first.statements[0].statement_key
        != second.statements[0].statement_key
    )


def test_a_policy_version_change_produces_a_distinct_semantic_set(
) -> None:
    _, fact_set = _pipeline("TR1 630 kVA")

    baseline = interpret_facts(fact_set)
    candidate = interpret_facts(fact_set, semantic_policy_version="2.0")

    assert candidate != baseline
    assert candidate.semantic_policy_version == "2.0"


def test_the_set_records_the_whole_upstream_source_identity() -> None:
    result = _interpret("TR1 630 kVA")

    assert result.resolution_policy_version == "1.0"
    # 1.1 since EPIC 32.P2; the semantic catalogue itself did not change,
    # which is why only the fact policy moved in this chain.
    assert result.fact_policy_version == "1.1"
    assert result.semantic_policy_version == "1.0"
    assert result.content_checksum


def test_the_set_carries_no_timestamp() -> None:
    names = {
        field.name for field in dataclasses.fields(EngineeringSemanticSet)
    }

    assert names & {"created_at", "interpreted_at", "timestamp"} == set()


# --- The realistic cases, each with its reason ------------------------------------------------------


def test_realistic_cases() -> None:
    """
    Every case the milestone names, with the outcome and the reason.

    | Association | Statement | Why |
    |---|---|---|
    | `TR1` → `630 kVA` | `HAS_RATED_POWER` | the object is a power observation, and it is the only one - the declared rule maps exactly this |
    | `TR1` → `20 kV` | **none** | a voltage may be rated, test, insulation or busbar voltage; the association does not say which, so no rule ships |
    | `TR1` → `240 mm²` | **none** | a cable section is not a property of the designation the association names, and no rule declares a meaning for it |

    The catalogue was **not** widened to give every association a
    meaning. Two of these deliberately produce none.
    """

    assert _triples("TR1 630 kVA") == [
        ("TR1", "has_rated_power", "630 kVA")
    ]
    assert _triples("TR1 20 kV") == []
    assert _triples("TR1 240 mm²") == []
