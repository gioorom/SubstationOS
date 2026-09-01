"""
Reuse across the deterministic derivation chain (EPIC 32.E2.4).

Supersedes the natural-key reuse tests of EPIC 32.E2.1 and 32.E2.2 and
keeps every invariant they established, now asserted against the
stronger model: an artifact is reusable only when it has the same
**deterministic identity**, and that identity is composed from the
identity of the artifact it was derived from plus the versions its own
stage owns.

The consequence these tests exist to prove is directional. A change at
stage N invalidates N and everything below it, and nothing above it -
without any layer naming another layer's version constants.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.domain.engineering_entities.entity_models import EntityType
from app.domain.engineering_facts.fact_predicates import FactPredicate
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)
from app.models.engineering_entities import EngineeringEntitySetRecord
from app.models.engineering_evidence import EngineeringEvidenceSetRecord
from app.models.engineering_facts import EngineeringFactSetRecord
from app.models.engineering_semantics import EngineeringSemanticSetRecord
from tests.services._derived_set_support import (
    LOCATION_LINE,
    construct_facts,
    interpret_semantics,
    prepared,
    resolve,
    run_pipeline,
)

SET_RECORDS = (
    EngineeringEvidenceSetRecord,
    EngineeringEntitySetRecord,
    EngineeringFactSetRecord,
    EngineeringSemanticSetRecord,
)


def _rows(db: Session, record_type, document_id: int) -> list:
    return (
        db.query(record_type)
        .filter(record_type.document_id == document_id)
        .order_by(record_type.id)
        .all()
    )


def _identities(db: Session, document_id: int) -> dict[str, str | None]:
    return {
        record.__name__: _rows(db, record, document_id)[-1].artifact_identity
        for record in SET_RECORDS
        if _rows(db, record, document_id)
    }


# --- A. The same computation is reused at every stage -------------------


def test_an_unchanged_pipeline_reuses_every_artifact(
    db_session: Session,
) -> None:
    """Correctness includes reuse: the repair must not simply disable
    caching."""

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    entities, facts, semantics = run_pipeline(db_session, document.id)

    assert entities.reused is True
    assert facts.reused is True
    assert semantics.reused is True


def test_every_persisted_artifact_carries_its_identity(
    db_session: Session,
) -> None:
    """An artifact that cannot say what computation produced it could
    never prove a later reuse is valid."""

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    for record in SET_RECORDS:
        stored = _rows(db_session, record, document.id)[-1]

        assert stored.artifact_identity, record.__name__
        assert len(stored.artifact_identity) == 64, record.__name__
        assert stored.upstream_identity, record.__name__


def test_each_artifact_names_the_one_above_it(db_session: Session) -> None:
    """The chain is a chain: each artifact's upstream identity is the
    identity of the artifact actually consumed."""

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    rows = [
        _rows(db_session, record, document.id)[-1] for record in SET_RECORDS
    ]

    for upstream, downstream in zip(rows, rows[1:]):
        assert downstream.upstream_identity == upstream.artifact_identity


# --- B-H. Directional invalidation, one axis at a time ------------------


def _bumped(db: Session, document_id: int, **kwargs):
    """Re-run the chain with exactly one stage's own policy raised."""

    return run_pipeline(db, document_id, **kwargs)


def test_a_resolution_policy_bump_recomputes_entities_facts_and_semantics(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A genuine policy bump, reproduced end to end.

    ``SUPPORTED_RESOLUTION_POLICY_VERSIONS`` is derived from
    ``RESOLUTION_POLICY_VERSION``, so a real change moves both together.
    When it does, the identity chain carries the change all the way
    down: the entity identity changes, which is the fact set's upstream
    identity, which is the semantic set's - and each stage recomputes
    rather than answering from the previous reading.
    """

    from app.domain.engineering_facts import fact_policy

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)
    before = [
        _rows(db_session, record, document.id)[-1].artifact_identity
        for record in SET_RECORDS
    ]

    monkeypatch.setattr(
        fact_policy,
        "SUPPORTED_RESOLUTION_POLICY_VERSIONS",
        frozenset({"2.0"}),
    )

    entities = resolve(
        db_session, document.id, resolution_policy_version="2.0"
    )
    facts = construct_facts(db_session, document.id)
    semantics = interpret_semantics(db_session, document.id)

    assert entities.reused is False
    assert facts.succeeded is True, "the fact stage could not proceed"
    assert facts.reused is False, "F1 answered for E2"
    assert semantics.succeeded is True
    assert semantics.reused is False, "S1 answered for the new facts"

    after = [
        _rows(db_session, record, document.id)[-1].artifact_identity
        for record in SET_RECORDS
    ]

    # Evidence is above the change and keeps its identity; everything
    # from the entities down is a different computation.
    assert after[0] == before[0]
    assert after[1:] != before[1:]

    rows = [
        _rows(db_session, record, document.id)[-1] for record in SET_RECORDS
    ]
    for upstream, downstream in zip(rows, rows[1:]):
        assert downstream.upstream_identity == upstream.artifact_identity


def test_an_entity_set_under_an_undeclared_policy_is_refused(
    db_session: Session,
) -> None:
    """
    A separate, pre-existing gate - not an identity question.

    An entity set resolved under a policy version this build does not
    declare is refused by the fact stage, because a policy it cannot
    read may carry entity types it would silently drop. A visible
    refusal, never a silent reuse.
    """

    from app.domain.engineering_facts.fact_failures import (
        FactConstructionFailureCode,
    )

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    resolve(db_session, document.id, resolution_policy_version="9.9")
    facts = construct_facts(db_session, document.id)

    assert facts.succeeded is False
    assert facts.failure.code is (
        FactConstructionFailureCode.UNSUPPORTED_ENTITY_SET_VERSION
    )


def test_a_fact_policy_bump_recomputes_facts_and_semantics(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A genuine bump again: ``SUPPORTED_FACT_POLICY_VERSIONS`` is derived
    from ``FACT_POLICY_VERSION``, so a real change moves both. Facts
    recompute, Semantics follow through the changed upstream identity,
    and Entities - above the change - are untouched.
    """

    from app.domain.engineering_semantics import semantic_policy

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    monkeypatch.setattr(
        semantic_policy, "SUPPORTED_FACT_POLICY_VERSIONS", frozenset({"9.9"})
    )

    entities, facts, semantics = run_pipeline(
        db_session, document.id, facts={"fact_policy_version": "9.9"}
    )

    assert entities.reused is True, "a fact policy does not touch entities"
    assert facts.succeeded is True
    assert facts.reused is False
    assert semantics.succeeded is True, "semantics could not proceed"
    assert semantics.reused is False, "the old statements answered"

    rows = [
        _rows(db_session, record, document.id)[-1] for record in SET_RECORDS
    ]
    for upstream, downstream in zip(rows, rows[1:]):
        assert downstream.upstream_identity == upstream.artifact_identity


def test_a_stage_invoked_alone_after_a_bump_refuses_rather_than_answers(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Stages are invoked, not cascaded - so order matters, and getting it
    wrong must never produce a quiet answer.

    With a policy raised but the stage that owns it not yet re-run, the
    stage below finds a stored upstream built under a version this build
    no longer declares. It refuses, naming the stage to run. That is the
    documented path to a current chain: run them in order.
    """

    from app.domain.engineering_facts import fact_policy
    from app.domain.engineering_facts.fact_failures import (
        FactConstructionFailureCode,
    )

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    monkeypatch.setattr(
        fact_policy,
        "SUPPORTED_RESOLUTION_POLICY_VERSIONS",
        frozenset({"2.0"}),
    )

    facts = construct_facts(db_session, document.id)

    assert facts.succeeded is False
    assert facts.reused is False, "a stale fact set answered"
    assert facts.failure.code is (
        FactConstructionFailureCode.UNSUPPORTED_ENTITY_SET_VERSION
    )


def test_a_semantic_policy_bump_invalidates_semantics_only(
    db_session: Session,
) -> None:
    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    entities, facts, semantics = _bumped(
        db_session, document.id, semantics={"semantic_policy_version": "9.9"}
    )

    assert entities.reused is True
    assert facts.reused is True, "a semantic policy does not touch facts"
    assert semantics.reused is False


def test_an_entity_contract_bump_invalidates_entities_and_below(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The hole EPIC 32.E2.3 reproduced and could not close under the old
    model: ``ENTITY_MODEL_VERSION`` changes every entity's row key while
    the set-level key stayed identical, so the stale set answered.

    It is now part of the entity stage's own derivation identity, so the
    set identity changes with it - and Facts and Semantics follow
    because their upstream identity changed.
    """

    from app.domain.engineering_entities import entity_resolver
    from app.services import engineering_entity_service

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    monkeypatch.setattr(entity_resolver, "ENTITY_MODEL_VERSION", "2.0")
    monkeypatch.setattr(
        engineering_entity_service, "ENTITY_MODEL_VERSION", "2.0"
    )

    entities, facts, semantics = run_pipeline(db_session, document.id)

    assert entities.succeeded is True
    assert entities.reused is False, "a stale entity contract answered"
    assert facts.succeeded is True
    assert facts.reused is False
    assert semantics.succeeded is True
    assert semantics.reused is False


def test_a_fact_contract_bump_invalidates_facts_and_semantics(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.engineering_facts import fact_constructor
    from app.services import engineering_fact_service

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    monkeypatch.setattr(fact_constructor, "FACT_CONTRACT_VERSION", "2.0")
    monkeypatch.setattr(
        engineering_fact_service, "FACT_CONTRACT_VERSION", "2.0"
    )

    entities, facts, semantics = run_pipeline(db_session, document.id)

    assert entities.reused is True, "a fact contract does not touch entities"
    assert facts.succeeded is True
    assert facts.reused is False
    assert semantics.succeeded is True
    assert semantics.reused is False


def test_a_semantic_contract_bump_invalidates_semantics_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.engineering_semantics import semantic_interpreter
    from app.services import engineering_semantic_service

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    monkeypatch.setattr(
        semantic_interpreter, "SEMANTIC_CONTRACT_VERSION", "2.0"
    )
    monkeypatch.setattr(
        engineering_semantic_service, "SEMANTIC_CONTRACT_VERSION", "2.0"
    )

    entities, facts, semantics = run_pipeline(db_session, document.id)

    assert entities.reused is True
    assert facts.reused is True
    assert semantics.succeeded is True
    assert semantics.reused is False


# --- The EPIC 32.E2 reading still reaches the end -----------------------


def test_the_governed_location_reading_reaches_semantics(
    db_session: Session,
) -> None:
    """
    The scenario the whole sequence began from: the location aspect must
    become a fact and a statement, not vanish behind a stale artifact.
    """

    document = prepared(db_session, LOCATION_LINE)
    _, facts, semantics = run_pipeline(db_session, document.id)

    assert FactPredicate.HAS_LOCATION_ASPECT in {
        fact.predicate for fact in facts.fact_set.facts
    }
    assert SemanticStatementType.IS_LOCATED_IN in {
        statement.statement_type
        for statement in semantics.semantic_set.statements
    }
    assert _latest_entities(db_session, document.id) == ["+E01"]


def _latest_entities(db: Session, document_id: int):
    entity_set = _rows(db, EngineeringEntitySetRecord, document_id)[-1]

    return [
        entity.designation_normalized
        for entity in entity_set.entities
        if entity.entity_type is EntityType.STRUCTURAL_LOCATION
    ]


# --- Legacy provenance is never compatible provenance -------------------


def test_an_artifact_without_identity_is_refused_not_reused(
    db_session: Session,
) -> None:
    """
    A row stored before the identity chain existed cannot say what
    produced it. Deriving from it would create an artifact that could
    never be reused or deduplicated either, so the stage refuses and
    names the remedy instead.
    """

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    evidence = _rows(db_session, EngineeringEvidenceSetRecord, document.id)[-1]
    evidence.artifact_identity = None
    db_session.commit()

    result = resolve(db_session, document.id)

    assert result.succeeded is False
    assert "identity" in result.failure.detail.lower()


def test_refusing_a_legacy_artifact_creates_no_rows(
    db_session: Session,
) -> None:
    """Bounded: repeated calls against unknown provenance must not append
    a row every time."""

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)

    facts = _rows(db_session, EngineeringFactSetRecord, document.id)[-1]
    facts.artifact_identity = None
    db_session.commit()

    before = len(_rows(db_session, EngineeringSemanticSetRecord, document.id))

    for _ in range(5):
        interpret_semantics(db_session, document.id)

    after = len(_rows(db_session, EngineeringSemanticSetRecord, document.id))

    assert after == before


# --- No caller may assert compatibility ---------------------------------


def test_no_caller_can_supply_an_identity(db_session: Session) -> None:
    from inspect import signature

    from app.services import (
        engineering_entity_service,
        engineering_fact_service,
        engineering_semantic_service,
    )

    for function in (
        engineering_entity_service.resolve_document_entities,
        engineering_fact_service.construct_document_facts,
        engineering_semantic_service.interpret_document_facts,
    ):
        parameters = signature(function).parameters

        assert "artifact_identity" not in parameters
        assert "upstream_identity" not in parameters


# --- Corruption is detected, not reused ---------------------------------


def test_an_artifact_carrying_a_foreign_identity_is_not_reused(
    db_session: Session,
) -> None:
    """
    An identity that is well formed but not the one this evidence
    produces describes a different computation. The stage below does not
    recognise it, so nothing it derived can be reused - it recomputes
    against the artifact actually in front of it rather than answering
    from a set built for something else.

    Detecting that the digest *contradicts its own provenance* is a
    stronger check, and only the canonical text stage can perform it -
    it is the one stage holding an upstream whose whole preimage is
    persisted. See ``RECONSTRUCT_UPSTREAM`` in ADR-0032.
    """

    document = prepared(db_session, LOCATION_LINE)
    run_pipeline(db_session, document.id)
    before = len(_rows(db_session, EngineeringEntitySetRecord, document.id))

    evidence = _rows(db_session, EngineeringEvidenceSetRecord, document.id)[-1]
    evidence.artifact_identity = "0" * 64
    db_session.commit()

    result = resolve(db_session, document.id)

    assert result.succeeded is True
    assert result.reused is False, "a set built for other evidence answered"
    assert (
        len(_rows(db_session, EngineeringEntitySetRecord, document.id))
        == before + 1
    )


def test_two_documents_never_share_an_artifact_identity(
    db_session: Session,
) -> None:
    """Identity is scoped by what it was derived from, and two documents
    are two different sources."""

    first = prepared(db_session, LOCATION_LINE)
    second = prepared(db_session, LOCATION_LINE, filename="other.pdf")

    run_pipeline(db_session, first.id)
    run_pipeline(db_session, second.id)

    assert _identities(db_session, first.id) != _identities(
        db_session, second.id
    )
