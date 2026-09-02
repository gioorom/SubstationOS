"""
Line-scoped structural location association (EPIC 32.P2).

EPIC 32.P1 built the whole structural-location path - evidence, entity,
fact, statement, review, promotion, graph, retrieval, reasoning - on a
fact rule scoped to **one token**: the ``+E01`` inside ``+E01-QA1``.

No real drawing in this repository writes that form. EPIC 32.E4
measured the whole CP Alfa corpus - ten drawings, 630 pages - and
found **not one** compound token in any of them; every location aspect
stands as its own token beside the designation it belongs to:

    MORSETTIERA -E.AM +GSH003

So the relationship P1 shipped was unreachable from real evidence. This
milestone adds one construction rule for that shape, and these tests are
the argument that it is a governed rule rather than a co-occurrence
engine.

## What the rule is allowed to do

Exactly one designation and exactly one location on one line, written as
different tokens. Nothing else. The negative half of this file is the
substantive half: every ambiguous shape produces **no fact**, and none
of them is resolved by nearest-token, ordering, similarity or a
cartesian product.

## Why the token relation exists

`LINE` and `TOKEN` scope overlap on a line whose only content is a
compound designation, and the overlap is not harmless. Two facts for one
association exceed the semantic catalogue's one-location-per-subject
policy, so the statement is refused as a contradiction - the P1
relationship would **disappear** on exactly the evidence it was built
for. `test_a_compound_line_still_produces_exactly_one_fact` is the guard
against that, and it fails against a line rule written without the
declared token relation.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_entities.entity_models import EntityType
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_evidence.evidence_rules import (
    match_location_aspect,
)
from app.domain.engineering_facts.fact_construction_rules import (
    COMPOUND_REFERENCE_DESIGNATION_RULE,
    SAME_LINE_ASSOCIATION_RULE,
    SAME_LINE_LOCATION_ASSOCIATION_RULE,
    CardinalityPolicy,
    StructuralScope,
    TokenRelation,
)
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    SupportRole,
)
from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.domain.engineering_semantics.semantic_interpreter import (
    interpret_facts,
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
from tests.domain.test_real_designation_evidence import (
    REAL_BARE_PRODUCT_LINES,
    REAL_DOT_PRODUCT_LINES,
    REAL_DOT_PRODUCT_LOCATED_LINES,
    REAL_UNGOVERNED_LOCATION_FORMS,
)


def _entities(*lines: str):
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
        )
    )

    return resolve_entities(
        extract_evidence(segment_canonical_document(source))
    )


def _facts(*lines: str):
    return construct_facts(_entities(*lines))


def _location_facts(*lines: str):
    return [
        fact
        for fact in _facts(*lines).facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    ]


def _located_in(*lines: str):
    return [
        statement
        for statement in interpret_facts(_facts(*lines)).statements
        if statement.statement_type is SemanticStatementType.IS_LOCATED_IN
    ]


# --- The rule, as declared -----------------------------------------------


def test_the_rule_is_line_scoped_and_strictly_one_to_one() -> None:
    """Declared in the catalogue, so the strictness is readable without
    reading the constructor."""

    rule = SAME_LINE_LOCATION_ASSOCIATION_RULE

    assert rule.rule_id == "same_line_location_association"
    assert rule.rule_version == "1.0"
    assert rule.scope is StructuralScope.LINE
    assert rule.cardinality is CardinalityPolicy.ONE_SUBJECT_ONE_OBJECT
    assert rule.token_relation is TokenRelation.DISTINCT_TOKENS
    assert rule.predicate is FactPredicate.HAS_LOCATION_ASPECT
    assert rule.subject_type is EntityType.EQUIPMENT_DESIGNATION
    assert rule.object_type is EntityType.STRUCTURAL_LOCATION


def test_the_rule_declares_no_new_predicate() -> None:
    """P2 adds a way to establish an existing association, not a new
    thing to say."""

    assert {member.name for member in FactPredicate} == {
        "HAS_ASSOCIATED_QUANTITY",
        "HAS_LOCATION_ASPECT",
    }


# --- Real evidence -------------------------------------------------------


def test_every_real_source_line_now_produces_a_location_fact() -> None:
    """
    The point of the milestone, on the lines that motivated it.

    Each of these is verbatim from the CP Alfa corpus - see
    ``test_real_designation_evidence`` for the document codes and
    checksums. Before P2 every one of them produced nothing.
    """

    for line in REAL_BARE_PRODUCT_LINES + REAL_DOT_PRODUCT_LOCATED_LINES:
        facts = _location_facts(line)

        assert len(facts) == 1, line
        assert (
            facts[0].construction_rule_id == "same_line_location_association"
        )


def test_the_hv_line_terminal_blocks_are_a_measured_extraction_gap(
) -> None:
    """
    **EPIC 32.E4 finding, pinned so it cannot be forgotten.**

    The HV-line sheet index writes its terminal blocks in exactly P2's
    shape - ``MORSETTIERA -E1.L +189L`` - one designation and one
    mounting reference as separate tokens on one line. P2 still produces
    nothing, and the reason is upstream of it: the governed location
    rule recognises only letter-leading aspects, so ``+189L`` is never
    observed as evidence at all.

    This is an *extraction* gap, not an association gap, and the
    distinction is the whole point. Widening P2 would not help; widening
    the location rule is a separate milestone with its own false-positive
    problem (the same corpus writes ``+110V`` and ``+24V`` for supply
    rails, and a phone number as ``+390000000``).
    """

    for line in REAL_DOT_PRODUCT_LINES:
        assert _location_facts(line) == [], line

    # And the reason: not one of those mounting references is observed.
    for form in REAL_UNGOVERNED_LOCATION_FORMS:
        assert match_location_aspect(form) is None, form


def test_a_real_source_line_produces_the_governed_statement() -> None:
    statements = _located_in("MORSETTIERA -E.AM +GSH003")

    assert len(statements) == 1
    assert statements[0].statement_type is SemanticStatementType.IS_LOCATED_IN
    assert statements[0].semantic_rule_id == (
        "location_from_compound_reference_designation"
    )
    assert statements[0].semantic_rule_version == "1.0"


def test_the_statement_names_the_designation_and_the_location() -> None:
    """Exact subject and object identity - the fact must not have paired
    the location with the word ``MORSETTIERA`` or with itself."""

    entities = _entities("MORSETTIERA -E.AM +GSH003")
    by_key = {
        entity.entity_key: entity.label for entity in entities.entities
    }
    statement = _located_in("MORSETTIERA -E.AM +GSH003")[0]

    assert by_key[statement.subject_entity_key] == "-E.AM"
    assert by_key[statement.object_entity_key] == "+GSH003"


def test_the_real_locations_stay_unclassified_structural_objects() -> None:
    """``+GSH003`` is a designated location. Not a bay, panel or room -
    P2 assigns no physical semantics it did not have."""

    entities = _entities("MORSETTIERA -E.AM +GSH003")
    locations = entities.of_type(EntityType.STRUCTURAL_LOCATION)

    assert [entity.label for entity in locations] == ["+GSH003"]


# --- Provenance ----------------------------------------------------------


def test_the_fact_cites_both_observations_that_put_the_pair_together(
) -> None:
    fact = _location_facts("MORSETTIERA -E.AM +GSH003")[0]

    assert len(fact.subject_support) == 1
    assert len(fact.object_support) == 1
    assert fact.subject_support[0].observed_text == "-E.AM"
    assert fact.object_support[0].observed_text == "+GSH003"
    assert fact.subject_support[0].role is SupportRole.SUBJECT
    assert fact.object_support[0].role is SupportRole.OBJECT


def test_the_support_locates_both_observations_on_one_line() -> None:
    """
    The rule is only credible if the line it matched on is visible, and
    it is: both observations carry page, paragraph and line, and the two
    agree.
    """

    fact = _location_facts("MORSETTIERA -E.AM +GSH003")[0]
    subject = fact.subject_support[0]
    obj = fact.object_support[0]

    assert subject.location == obj.location
    assert subject.location == (1, 0, 0)


def test_the_support_shows_the_two_observations_were_different_tokens(
) -> None:
    """What separates this rule from the compound one, visible on the
    stored fact rather than only in the catalogue."""

    fact = _location_facts("MORSETTIERA -E.AM +GSH003")[0]
    subject = fact.subject_support[0]
    obj = fact.object_support[0]

    assert (subject.token_start, subject.token_end) != (
        obj.token_start,
        obj.token_end,
    )


def test_the_fact_names_the_rule_and_version_that_built_it() -> None:
    fact = _location_facts("MORSETTIERA -E.AM +GSH003")[0]

    assert fact.construction_rule_id == "same_line_location_association"
    assert fact.construction_rule_version == "1.0"
    assert fact.fact_version == "1.0"


# --- Cardinality: every refusal the milestone requires -------------------


def test_two_designations_and_one_location_produce_no_fact() -> None:
    """
    Which block ``+GSH003`` belongs to is exactly what the line does not
    say. Guessing would put a terminal block in the wrong place.
    """

    result = _facts("MORSETTIERA -E.AM -E.TAL +GSH003")

    assert _location_facts("MORSETTIERA -E.AM -E.TAL +GSH003") == []
    assert any(
        diagnostic.reason is AmbiguityReason.MULTIPLE_SUBJECTS
        for diagnostic in result.diagnostics
    )


def test_one_designation_and_two_locations_produce_no_fact() -> None:
    """The document contradicted itself about where the block is, and
    this rule does not choose a side."""

    assert _location_facts("MORSETTIERA -E.AM +GSH001 +GSH003") == []


def test_one_designation_and_two_locations_is_recorded_as_a_refusal(
) -> None:
    """
    A refusal an engineer cannot see is a refusal nobody can act on.

    This shape was silent when the rule first shipped: the cardinality
    branch it lands in was previously reachable only from the
    token-scoped compound rule, where the shape cannot arise and silence
    is correct. At line scope it can arise, and it is exactly the case a
    reviewer needs to see - a drawing that placed one terminal block in
    two places.
    """

    result = _facts("MORSETTIERA -E.AM +GSH001 +GSH003")

    assert [
        diagnostic.reason for diagnostic in result.diagnostics
    ] == [AmbiguityReason.MULTIPLE_OBJECTS]
    assert result.has_ambiguities is True

    diagnostic = result.diagnostics[0]

    assert len(diagnostic.subject_entity_keys) == 1
    assert len(diagnostic.object_entity_keys) == 2


def test_one_designation_and_many_quantities_is_not_a_refusal() -> None:
    """The new diagnostic belongs to the cardinality policy, not to the
    shape. A data-sheet line listing several ratings is permitted
    explicitly, and must not start reporting itself as ambiguous."""

    result = _facts("TR1 20 kV 630 kVA")

    assert len(result.facts) == 2
    assert result.diagnostics == ()


def test_two_designations_and_two_locations_produce_no_fact() -> None:
    """No cartesian product, and no pairing by order or proximity."""

    assert _location_facts("-E.AM -E.TAL +GSH001 +GSH003") == []


def test_a_designation_and_a_location_on_different_lines_do_not_associate(
) -> None:
    """Same page, same block, adjacent lines. A line is the unit, and
    nothing widens it."""

    assert _location_facts("MORSETTIERA -E.AM", "+GSH003") == []


def test_a_location_with_no_designation_produces_no_fact() -> None:
    assert _location_facts("MORSETTIERA +GSH003") == []


def test_a_designation_with_no_location_produces_no_fact() -> None:
    assert _location_facts("MORSETTIERA -E.AM") == []


def test_the_nearest_location_is_not_chosen_on_an_ambiguous_line() -> None:
    """
    The mutation this file most needs to kill.

    ``-E.AM`` is adjacent to ``+GSH003``; ``-E.TAL`` is four tokens away.
    An implementation that broke the tie by distance, by token order, or
    by taking the first subject would produce a fact here. The rule
    produces none.
    """

    assert _location_facts("-E.AM +GSH003 e anche -E.TAL") == []


def test_an_ambiguous_line_does_not_suppress_a_clean_one() -> None:
    """The rule was satisfied on the second line; the first is still
    refused, and the diagnostic still records it."""

    facts = _location_facts(
        "MORSETTIERA -E.AM -E.TAL +GSH003",
        "MORSETTIERA -E.AM +GSH003",
    )

    assert len(facts) == 1
    assert facts[0].object_support[0].observed_text == "+GSH003"


# --- The overlap with the compound rule ----------------------------------


def test_a_compound_line_still_produces_exactly_one_fact() -> None:
    """
    The regression guard for EPIC 32.P1.

    ``+E01-QA1`` alone is a line carrying exactly one designation and
    exactly one location, so a line rule without the declared token
    relation matches it - and the compound rule already has. Two facts
    for one association exceed the semantic catalogue's
    one-location-per-subject policy, and the statement P1 shipped is
    refused as a self-contradiction.

    So this is not a tidiness test. Without `DISTINCT_TOKENS` the
    assertion below fails at two facts *and* the statement disappears.
    """

    facts = _location_facts("Interruttore +E01-QA1 in cabina")

    assert len(facts) == 1
    assert facts[0].construction_rule_id == "compound_reference_designation"


def test_the_compound_statement_survives_the_new_rule() -> None:
    statements = _located_in("Interruttore +E01-QA1 in cabina")

    assert len(statements) == 1


def test_a_location_written_both_ways_on_one_line_associates_once(
) -> None:
    """
    ``+E01`` standing alone and ``+E01`` inside ``+E01-QA1`` resolve to
    **one** entity carrying both observations. The token relation is
    therefore tested across **all** of an entity's observations, not only
    the first of each.

    The standalone form is written first here deliberately. An
    implementation comparing one observation per side would find
    ``+E01`` at token 1 and ``+E01-QA1`` at token 3, call them distinct,
    and emit a second fact for the association the compound rule has
    already recorded - taking the statement with it. With the compound
    written first the two orderings coincide and the mutation survives,
    which is why the case is pinned in this order.
    """

    line = "Cabina +E01 interruttore +E01-QA1"
    facts = _location_facts(line)

    assert len(facts) == 1
    assert facts[0].construction_rule_id == "compound_reference_designation"
    assert len(_located_in(line)) == 1


def test_a_compound_and_a_separate_pair_on_one_line_produce_one_fact(
) -> None:
    """
    Two designations on the line, so the line rule refuses; the compound
    rule still records what it read from its own token. Conservative in
    the direction the milestone requires.
    """

    facts = _location_facts("+E01-QA1 -QB1 +E02")

    assert len(facts) == 1
    assert facts[0].construction_rule_id == "compound_reference_designation"


def test_a_compound_bound_location_raises_no_ambiguity(
) -> None:
    """
    ``TR1`` and ``+E01-QA1`` are two designations, and the line's only
    location is written **inside** one of them. The line rule may not
    associate that location at all, so it must not announce that it
    could not tell which designation the location belonged to - the
    compound rule determined exactly that, on the same line.

    A rule that tests cardinality before eligibility reports an
    ambiguity here and flips the whole fact set to ambiguous, beside a
    fact that says the association is known.
    """

    result = _facts("Trasformatore TR1 nel quadro +E01-QA1")

    assert len(result.facts) == 1
    assert result.diagnostics == ()
    assert result.has_ambiguities is False


def test_a_free_location_beside_a_compound_is_still_ambiguous() -> None:
    """
    The other side of the same boundary. Here ``+E02`` is written
    independently, so the line rule *could* have associated it - and
    with two designations on the line it cannot tell which. That is a
    real ambiguity and is reported, while the compound pair is still
    recorded from its own token.
    """

    result = _facts("+E01-QA1 -QB1 +E02")

    assert len(result.facts) == 1
    assert [
        diagnostic.reason for diagnostic in result.diagnostics
    ] == [AmbiguityReason.MULTIPLE_SUBJECTS]


# --- Nothing else moved --------------------------------------------------


def test_the_compound_rule_is_unchanged() -> None:
    """P2 adds a rule beside it; it does not widen it."""

    assert COMPOUND_REFERENCE_DESIGNATION_RULE.scope is StructuralScope.TOKEN
    assert COMPOUND_REFERENCE_DESIGNATION_RULE.rule_version == "1.0"
    assert (
        COMPOUND_REFERENCE_DESIGNATION_RULE.cardinality
        is CardinalityPolicy.ONE_SUBJECT_ONE_OBJECT
    )


def test_the_quantity_rule_is_unchanged() -> None:
    assert SAME_LINE_ASSOCIATION_RULE.rule_version == "1.0"
    assert (
        SAME_LINE_ASSOCIATION_RULE.cardinality
        is CardinalityPolicy.ONE_SUBJECT_MANY_OBJECTS
    )
    assert (
        SAME_LINE_ASSOCIATION_RULE.token_relation
        is TokenRelation.UNCONSTRAINED
    )


def test_a_quantity_line_is_unaffected_by_the_location_rule() -> None:
    facts = _facts("Trasformatore T1 - potenza 630 kVA")

    assert [fact.predicate for fact in facts.facts] == [
        FactPredicate.HAS_ASSOCIATED_QUANTITY
    ]


def test_a_designation_is_not_placed_in_a_location_by_a_quantity_rule(
) -> None:
    """The two line-scoped rules read different entity types and must not
    borrow each other's objects."""

    facts = _facts("-E.AM +GSH003 630 kVA")
    predicates = {fact.predicate for fact in facts.facts}

    assert predicates == {
        FactPredicate.HAS_LOCATION_ASPECT,
        FactPredicate.HAS_ASSOCIATED_QUANTITY,
    }


def test_the_evidence_and_entity_layers_were_not_changed() -> None:
    """
    P2 is a fact-construction milestone. Both sides of the association
    were already independently resolved before it - which is why no new
    evidence type and no new entity type appear anywhere in it.
    """

    entities = _entities("MORSETTIERA -E.AM +GSH003")
    evidence_types = {
        reference.evidence_type
        for entity in entities.entities
        for reference in entity.evidence
    }

    assert evidence_types == {
        EvidenceType.DESIGNATION,
        EvidenceType.LOCATION_ASPECT,
    }
    assert {entity.entity_type for entity in entities.entities} == {
        EntityType.EQUIPMENT_DESIGNATION,
        EntityType.STRUCTURAL_LOCATION,
    }


def test_no_hierarchy_is_derived_from_a_dot_qualified_designation(
) -> None:
    """
    ``-E1.L`` and ``-E1.SB`` are both real CP Alfa forms and share
    the ``-E1`` prefix. P2 relates each to ``+GSH003`` and **nothing**
    to each other, and neither to a synthesised ``-E1``.

    The shared prefix is the whole point of the case, so it must not be
    optimised away: a pair that did not share one would assert nothing
    about prefix synthesis.
    """

    entities = _entities(
        "MORSETTIERA -E1.L +GSH003", "MORSETTIERA -E1.SB +GSH003"
    )
    labels = {entity.label for entity in entities.entities}
    statements = _located_in(
        "MORSETTIERA -E1.L +GSH003", "MORSETTIERA -E1.SB +GSH003"
    )

    assert "-E1" not in labels
    assert len(statements) == 2

    subjects = {statement.subject_entity_key for statement in statements}
    objects = {statement.object_entity_key for statement in statements}

    assert len(subjects) == 2
    assert len(objects) == 1
    assert not subjects & objects


def test_determinism_over_the_whole_chain() -> None:
    assert _located_in("MORSETTIERA -E.AM +GSH003") == _located_in(
        "MORSETTIERA -E.AM +GSH003"
    )
