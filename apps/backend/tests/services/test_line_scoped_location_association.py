"""
The line-scoped location association, through the real pipeline
(EPIC 32.P2).

Every stage here runs through its **real service and real adapter**
against a real (in-memory) database. The domain tests in
``tests/domain/test_line_scoped_structural_location`` prove what the rule
decides; these prove that what it decides is what gets persisted, that
the changed catalogue invalidates what it must, and that nothing older is
quietly reused in its place.

The source line is verbatim from a single Italian DSO's HV/MV
functional diagram. It is the shape 32.P1's token-scoped rule could not
read, and the reason this milestone exists.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy.orm import Session

from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)
from app.models.engineering_entities import EngineeringEntitySetRecord
from app.models.engineering_facts import EngineeringFactSetRecord
from tests.services._derived_set_support import (
    construct_facts,
    prepared,
    resolve,
    run_pipeline,
)

# TR, REF-A-S-027_01, p.6 - a
# terminal block and the location it is in, written the way the drawing
# writes it: two separate tokens. CP Alfa 150/20 kV.
REAL_LINE = "MORSETTIERA -E.AM +GSH003"


def _fact_rows(db: Session, document_id: int) -> list:
    return (
        db.query(EngineeringFactSetRecord)
        .filter(EngineeringFactSetRecord.document_id == document_id)
        .order_by(EngineeringFactSetRecord.id)
        .all()
    )


# --- The real line reaches governed meaning ------------------------------


def test_a_real_source_line_produces_a_persisted_location_fact(
    db_session: Session,
) -> None:
    document = prepared(db_session, REAL_LINE)
    _, facts, _ = run_pipeline(db_session, document.id)

    assert facts.succeeded is True

    location = [
        fact
        for fact in facts.fact_set.facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    ]

    assert len(location) == 1
    assert location[0].construction_rule_id == (
        "same_line_location_association"
    )


def test_the_real_line_reaches_the_governed_statement(
    db_session: Session,
) -> None:
    """
    The whole point of the milestone, end to end through real services:
    a relationship that existed in the vocabulary but had no reachable
    real instance now has one.
    """

    document = prepared(db_session, REAL_LINE)
    _, _, semantics = run_pipeline(db_session, document.id)

    assert semantics.succeeded is True
    assert SemanticStatementType.IS_LOCATED_IN in {
        statement.statement_type
        for statement in semantics.semantic_set.statements
    }


def test_the_persisted_fact_keeps_both_sides_of_its_provenance(
    db_session: Session,
) -> None:
    """Stored, not merely computed: the support survives the round trip
    through the adapter."""

    document = prepared(db_session, REAL_LINE)
    _, facts, _ = run_pipeline(db_session, document.id)

    fact = next(
        fact
        for fact in facts.fact_set.facts
        if fact.predicate is FactPredicate.HAS_LOCATION_ASPECT
    )

    assert {support.observed_text for support in fact.subject_support} == {
        "-E.AM"
    }
    assert {support.observed_text for support in fact.object_support} == {
        "+GSH003"
    }
    assert fact.subject_support[0].location == fact.object_support[0].location


# --- The catalogue change invalidates what it must -----------------------


def test_a_fact_set_built_under_the_old_catalogue_is_not_reused(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The reuse-coherency proof, and the one that matters most here.

    A 1.0 fact set is what a document processed before P2 has stored. On
    this line the 1.0 catalogue produced no location fact at all - the
    token rule cannot associate two separate tokens - so if such a set
    could satisfy a request under 1.1 the pipeline would report success
    and serve the document with its location silently missing. That is
    exactly the failure ADR-0032 was written about.

    Note what ``fact_policy_version`` is and is not. It is the **label**
    recorded on the stored set, not a switch that selects a catalogue:
    this build has one catalogue and always runs it. So the set below is
    not a replayed 1.0 computation, it is a set stamped 1.0 - which is
    precisely what an old row is. The guard being tested is that the
    stamp participates in the identity, so the stamped set cannot answer
    for the current one.

    Asserted as what actually happened rather than only ``reused is
    False``: a second set was persisted, its identity differs, its
    lineage still names the unchanged entity set above it, and the
    location fact is present in the current set.
    """

    document = prepared(db_session, REAL_LINE)
    resolve(db_session, document.id)

    stale = construct_facts(
        db_session, document.id, fact_policy_version="1.0"
    )

    assert stale.succeeded is True
    assert stale.fact_set.fact_policy_version == "1.0"

    current = construct_facts(db_session, document.id)

    assert current.succeeded is True
    assert current.reused is False, "a stale catalogue answered"

    rows = _fact_rows(db_session, document.id)
    entity_row = (
        db_session.query(EngineeringEntitySetRecord)
        .filter(EngineeringEntitySetRecord.document_id == document.id)
        .order_by(EngineeringEntitySetRecord.id)
        .all()[-1]
    )

    assert len(rows) == 2, "recomputation must persist a new set"
    assert rows[0].artifact_identity != rows[1].artifact_identity
    assert rows[1].fact_policy_version == "1.1"

    # Facts changed; the entities above them did not. Lineage says so.
    assert rows[0].upstream_identity == entity_row.artifact_identity
    assert rows[1].upstream_identity == entity_row.artifact_identity

    assert FactPredicate.HAS_LOCATION_ASPECT in {
        fact.predicate for fact in current.fact_set.facts
    }


def test_an_unchanged_run_still_reuses(db_session: Session) -> None:
    """The bump must not have made every run recompute for ever."""

    document = prepared(db_session, REAL_LINE)
    run_pipeline(db_session, document.id)

    _, facts, semantics = run_pipeline(db_session, document.id)

    assert facts.reused is True
    assert semantics.reused is True


def test_the_new_rule_is_inside_the_effective_catalogue_identity(
) -> None:
    """
    The rule must be part of what the fact policy version identifies -
    otherwise a future change to it could alter persisted output under
    an unchanged identity.

    Recomputed here the same way the architecture pin does it, so this
    fails if the rule is ever dropped from the catalogue while the pin
    is edited to match.
    """

    from app.domain.engineering_facts.fact_construction_rules import (
        CONSTRUCTION_RULES,
    )
    from app.domain.engineering_facts.fact_policy import FACT_POLICY_VERSION

    rule_ids = [rule.rule_id for rule in CONSTRUCTION_RULES]

    assert "same_line_location_association" in rule_ids
    assert FACT_POLICY_VERSION == "1.1"

    without = hashlib.sha256(
        "|".join(
            f"{rule.rule_id}@{rule.rule_version}"
            for rule in CONSTRUCTION_RULES
            if rule.rule_id != "same_line_location_association"
        ).encode("utf-8")
    ).hexdigest()
    with_rule = hashlib.sha256(
        "|".join(
            f"{rule.rule_id}@{rule.rule_version}"
            for rule in CONSTRUCTION_RULES
        ).encode("utf-8")
    ).hexdigest()

    assert without != with_rule


def test_the_identity_moves_with_the_policy_and_nothing_else(
    db_session: Session,
) -> None:
    """
    A fact set's identity names its upstream and its own two versions.
    The same entities under two catalogues must differ; under the same
    catalogue they must not.
    """

    from app.domain.artifact_identity.artifact_identity_models import (
        ArtifactIdentity,
        ArtifactKind,
    )
    from app.domain.artifact_identity.artifact_identity_policy import (
        ARTIFACT_IDENTITY_CONTRACT_VERSION,
    )
    from app.domain.engineering_facts.fact_identity import fact_set_identity

    document = prepared(db_session, REAL_LINE)
    entities = resolve(db_session, document.id)

    upstream = ArtifactIdentity(
        value=entities.entity_set.artifact_identity,
        kind=ArtifactKind.ENTITY_SET,
        contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
    )

    def identity(policy: str) -> str:
        return fact_set_identity(
            entity_set=upstream,
            fact_policy_version=policy,
            fact_contract_version="1.0",
        ).value

    assert identity("1.0") != identity("1.1")
    assert identity("1.1") == identity("1.1")
