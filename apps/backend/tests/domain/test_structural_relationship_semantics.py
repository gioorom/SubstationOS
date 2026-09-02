"""
The structural relationship, layer by layer (EPIC 32.P1).

Pure domain tests over hand-built canonical text - no PDF, no database,
no I/O. The end-to-end governance path is proved in
``tests/api/test_governed_structural_relationship.py``; what these tests
pin down is the part an engineer has to be able to argue with: **exactly
which strings produce a relationship, and which do not**.

The relationship is read from IEC 81346-1, which assigns ``+`` to the
location aspect and ``-`` to the product aspect. So ``+E01-QA1``
designates an object in the context of location ``+E01``, and that
reading - not proximity, not layout - is the whole of the claim.

**EPIC 32.P2 added a second way to establish the same association**, for
the shape real drawings actually use: one designation and one location
written as separate tokens on one line. It is governed by its own rule
with its own strict cardinality, and it is tested in
``test_line_scoped_structural_location``. What the two rules share is
that neither chooses between candidates: the reading is exact or there
is no fact.

The tests below remain P1's - the compound form, and the refusals that
still hold.
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
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from app.domain.engineering_facts.fact_construction_rules import (
    COMPOUND_REFERENCE_DESIGNATION_RULE,
    CardinalityPolicy,
    StructuralScope,
)
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.domain.engineering_semantics.semantic_interpreter import (
    interpret_facts,
)
from app.domain.engineering_semantics.semantic_rules import (
    IS_LOCATED_IN_RULE,
    LOCATION_ASPECT_EVIDENCE_TYPE,
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


def _evidence(*lines: str):
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

    return extract_evidence(segment_canonical_document(source))


def _entities(*lines: str):
    return resolve_entities(_evidence(*lines))


def _facts(*lines: str):
    return construct_facts(_entities(*lines))


def _statements(*lines: str):
    return interpret_facts(_facts(*lines))


def _located_in(*lines: str):
    return [
        statement
        for statement in _statements(*lines).statements
        if statement.statement_type is SemanticStatementType.IS_LOCATED_IN
    ]


# --- Evidence: what is observed, and where -------------------------------


def test_the_location_aspect_of_a_compound_designation_is_observed() -> None:
    result = _evidence("Interruttore +E01-QA1 in cabina")

    location = result.of_type(EvidenceType.LOCATION_ASPECT)

    assert [item.observed_text for item in location] == ["+E01"]
    assert location[0].status is EvidenceStatus.OBSERVED
    assert location[0].designation.normalized == "+E01"


def test_the_whole_compound_designation_is_still_observed() -> None:
    """The location aspect is recorded **beside** the designation, never
    instead of it. Both are written, and both are true."""

    result = _evidence("Interruttore +E01-QA1 in cabina")

    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.DESIGNATION)
    ] == ["+E01-QA1"]


def test_the_location_observation_covers_only_the_location_characters(
) -> None:
    """
    An observation that pointed at the whole token would claim the
    document wrote ``+E01`` where it wrote ``+E01-QA1``. Provenance is
    the reason to trust any of this, so it is checked exactly.
    """

    result = _evidence("Interruttore +E01-QA1 in cabina")

    designation = result.of_type(EvidenceType.DESIGNATION)[0]
    location = result.of_type(EvidenceType.LOCATION_ASPECT)[0]

    assert len(location.provenance.spans) == 1

    location_span = location.provenance.spans[0]
    designation_span = designation.provenance.spans[0]

    # Same start - both begin at the '+' - and a shorter end.
    assert location_span.character_start == designation_span.character_start
    assert location_span.character_end == designation_span.character_start + 4
    assert location_span.character_end < designation_span.character_end


def test_the_two_observations_from_one_token_have_different_keys() -> None:
    """The evidence key covers the rule and the evidence type, so one
    token producing two claims produces two records rather than one that
    overwrites the other."""

    result = _evidence("Interruttore +E01-QA1 in cabina")

    keys = {item.evidence_key for item in result.evidence}

    assert len(keys) == len(result.evidence)


# --- Evidence: what is NOT observed --------------------------------------


def test_a_product_within_a_product_is_not_a_location() -> None:
    """
    ``-QA1-XB2`` names a component of a product. IEC 81346 gives ``-`` to
    the product aspect, so reading the first segment as a place would be
    assigning a meaning the standard gives elsewhere.
    """

    result = _evidence("Modulo -QA1-XB2 montato")

    assert result.of_type(EvidenceType.LOCATION_ASPECT) == ()
    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.DESIGNATION)
    ] == ["-QA1-XB2"]


def test_a_bare_location_aspect_is_observed_as_a_location() -> None:
    """
    **Behaviour changed by EPIC 32.E2, on real evidence.**

    Milestone 32.P1 asserted the opposite: that ``+E01`` alone produced
    no location aspect, because "``+E01`` alone is already recorded as a
    designation" and observing it twice would be two entities for one
    string.

    That reasoning was sound but rested on an assumption the corpus could
    not test - 32.P1's only source line wrote the location *inside* a
    compound token. EPIC 32.E1 then measured 41,739 tokens of real
    an Italian DSO functional diagrams and found the standalone form is
    not the exception but the **rule**: 268 standalone location aspects,
    zero compounds.

    So the premise inverted. Calling ``+GSH002`` an equipment
    designation would have put 268 locations into the graph as assets.
    The duplication 32.P1 feared is avoided instead by precedence - the
    designation rule now declines a standalone location aspect, so the
    token is observed once, as what it is.
    """

    result = _evidence("Cabina +E01")

    location = result.of_type(EvidenceType.LOCATION_ASPECT)

    assert [item.observed_text for item in location] == ["+E01"]
    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_a_plain_designation_produces_no_location_aspect() -> None:
    for line in ("Trasformatore T1", "Interruttore 52-Q1", "Quadro QMT01"):
        assert _evidence(line).of_type(EvidenceType.LOCATION_ASPECT) == ()


# --- Entities ------------------------------------------------------------


def test_a_location_aspect_resolves_to_a_structural_location_entity(
) -> None:
    entities = _entities("Interruttore +E01-QA1 in cabina")

    locations = entities.of_type(EntityType.STRUCTURAL_LOCATION)

    assert [entity.label for entity in locations] == ["+E01"]
    assert locations[0].resolution_rule_id == "location_aspect_grouping"


def test_devices_in_one_location_resolve_to_one_location_entity() -> None:
    """The shared structural parent, and it is shared because the two
    documents' tokens named the same location - not because the devices
    look related."""

    entities = _entities("Quadro +E01-QA1 e +E01-QB1 installati")

    assert len(entities.of_type(EntityType.STRUCTURAL_LOCATION)) == 1
    assert len(entities.of_type(EntityType.EQUIPMENT_DESIGNATION)) == 2


def test_two_locations_stay_two_entities() -> None:
    entities = _entities("Quadri +E01-QA1 e +E02-QA2")

    assert len(entities.of_type(EntityType.STRUCTURAL_LOCATION)) == 2


def test_a_standalone_and_an_embedded_location_aspect_agree() -> None:
    """
    **Behaviour changed by EPIC 32.E2** - see the test above for why.

    ``+E01`` written alone and ``+E01`` written inside ``+E01-QA1`` are
    now both location aspects, which is what they are. They resolve to
    **one** structural location within a document, because the resolver
    groups designation-valued observations by normalised value, status
    and extraction rule version - and both observations now carry the
    same rule.

    That is the honest outcome: the same place, written twice in one
    document, is one place. It remains document-scoped, so the same
    string in another document is still a different governed location.
    """

    entities = _entities("Cabina +E01", "Interruttore +E01-QA1")

    designations = {
        entity.label
        for entity in entities.of_type(EntityType.EQUIPMENT_DESIGNATION)
    }
    locations = {
        entity.label
        for entity in entities.of_type(EntityType.STRUCTURAL_LOCATION)
    }

    assert designations == {"+E01-QA1"}
    assert locations == {"+E01"}
    assert (
        len({entity.entity_key for entity in entities.entities})
        == len(entities.entities)
    )


# --- Facts ---------------------------------------------------------------


def test_a_compound_designation_produces_a_location_aspect_fact() -> None:
    fact_set = _facts("Interruttore +E01-QA1 in cabina")

    facts = [
        fact
        for fact in fact_set.facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    ]

    assert len(facts) == 1
    assert facts[0].construction_rule_id == "compound_reference_designation"
    assert facts[0].construction_rule_version == "1.0"


def test_the_compound_location_rule_is_scoped_to_one_token() -> None:
    """
    The two observations came from the same characters - the strongest
    co-occurrence this pipeline can record, and unchanged by EPIC 32.P2,
    which added a rule beside this one rather than widening it.
    """

    assert COMPOUND_REFERENCE_DESIGNATION_RULE.scope is StructuralScope.TOKEN
    assert (
        COMPOUND_REFERENCE_DESIGNATION_RULE.cardinality
        is CardinalityPolicy.ONE_SUBJECT_ONE_OBJECT
    )


def test_the_location_fact_carries_both_sides_of_its_support() -> None:
    fact = next(
        fact
        for fact in _facts("Interruttore +E01-QA1 in cabina").facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    )

    assert len(fact.subject_support) == 1
    assert len(fact.object_support) == 1
    assert fact.subject_support[0].observed_text == "+E01-QA1"
    assert fact.object_support[0].observed_text == "+E01"


def test_a_designation_on_the_same_line_gets_no_location_fact() -> None:
    """
    The rule that would be easiest to get wrong, and **the reason it
    holds changed in EPIC 32.P2**.

    Under P1 nothing could associate across tokens at all. P2 added a
    line-scoped rule, so the guarantee now rests on that rule's
    cardinality instead: this line carries two designations - ``TR1``
    and ``+E01-QA1`` - and a rule that will not choose between subjects
    produces nothing.

    The outcome is unchanged and still the important one. ``TR1`` is not
    placed in ``+E01`` on the strength of sharing a line with it, and
    ``+E01-QA1`` keeps the containment it was actually written with.
    """

    fact_set = _facts("Trasformatore TR1 nel quadro +E01-QA1")

    located = {
        fact.subject_entity_key
        for fact in fact_set.facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    }
    entities = _entities("Trasformatore TR1 nel quadro +E01-QA1")
    tr1 = next(
        entity for entity in entities.entities if entity.label == "TR1"
    )

    assert tr1.entity_key not in located
    assert len(located) == 1


def test_the_same_line_quantity_rule_is_unaffected() -> None:
    """EPIC 32.P1 adds a rule; it does not change the one that was
    there."""

    fact_set = _facts("Trasformatore T1 - potenza 630 kVA")

    assert [
        fact.predicate for fact in fact_set.facts
    ] == [FactPredicate.HAS_ASSOCIATED_QUANTITY]


# --- Semantics -----------------------------------------------------------


def test_a_location_fact_is_interpreted_as_is_located_in() -> None:
    statements = _located_in("Interruttore +E01-QA1 in cabina")

    assert len(statements) == 1
    assert statements[0].semantic_rule_id == (
        "location_from_compound_reference_designation"
    )
    assert statements[0].semantic_rule_version == "1.0"


def test_the_location_rule_reads_facts_rather_than_evidence() -> None:
    """Declared, so the boundary is visible in the catalogue rather than
    only in the interpreter."""

    assert (
        IS_LOCATED_IN_RULE.supported_predicate
        is FactPredicate.HAS_LOCATION_ASPECT
    )
    assert IS_LOCATED_IN_RULE.required_evidence_types == (
        LOCATION_ASPECT_EVIDENCE_TYPE,
    )


def test_the_declared_location_evidence_type_matches_the_vocabulary(
) -> None:
    """The drift guard for the string the semantic layer restates rather
    than imports."""

    assert LOCATION_ASPECT_EVIDENCE_TYPE == EvidenceType.LOCATION_ASPECT.value


def test_the_rated_power_rule_still_produces_its_statement() -> None:
    statements = _statements("Trasformatore T1 - potenza 630 kVA")

    assert [
        statement.statement_type for statement in statements.statements
    ] == [SemanticStatementType.HAS_RATED_POWER]


def test_both_rules_run_over_one_document() -> None:
    """Two meanings from one line, each from its own rule, neither
    reading the other's output."""

    statements = _statements("Trasformatore +E01-QA1 630 kVA")

    assert {
        statement.statement_type for statement in statements.statements
    } == {
        SemanticStatementType.HAS_RATED_POWER,
        SemanticStatementType.IS_LOCATED_IN,
    }


# --- No inference --------------------------------------------------------


def test_two_devices_in_one_location_are_not_related_to_each_other(
) -> None:
    """
    The inference EPIC 32.2 will have to justify, and which this
    milestone must not make for it. Two assets in one place produce two
    containment statements and **nothing** between the assets.
    """

    statements = _statements("Quadro +E01-QA1 e +E01-QB1 installati")

    subjects = {
        statement.subject_entity_key
        for statement in statements.statements
    }
    objects = {
        statement.object_entity_key for statement in statements.statements
    }

    assert len(statements.statements) == 2
    assert len(subjects) == 2
    assert len(objects) == 1
    assert not subjects & objects


def test_no_transitive_statement_is_produced() -> None:
    """
    ``+E01-QA1`` is located in ``+E01``; nothing says ``+E01`` is located
    in anything, and nothing composes two statements into a third. Every
    statement here has a fact behind it.
    """

    statements = _statements("Quadro +E01-QA1 nella cabina +E02-QA9")

    for statement in statements.statements:
        assert len(statement.supporting_fact_keys) == 1


def test_determinism_over_the_whole_chain() -> None:
    """The same text always produces the same statements, keys included -
    which is what lets the schema enforce idempotency."""

    first = _statements("Interruttore +E01-QA1 in cabina")
    second = _statements("Interruttore +E01-QA1 in cabina")

    assert first == second
