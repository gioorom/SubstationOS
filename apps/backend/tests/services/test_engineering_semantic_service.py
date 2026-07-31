"""
Service tests for Engineering Semantic Interpretation (Milestone 30.1),
against a real (in-memory) database through the real adapters.

Facts are produced by the real extractor, resolver and constructor and
stored through their own repositories, so these prove the four layers
meet correctly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_facts.fact_constructor import construct_facts
from app.domain.engineering_semantics.engineering_semantic_repository import (
    EngineeringSemanticRepository,
)
from app.domain.engineering_semantics.semantic_failures import (
    SemanticInterpretationFailureCode,
)
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.infrastructure.engineering_facts.sqlalchemy_engineering_fact_repository import (  # noqa: E501
    SqlAlchemyEngineeringFactRepository,
)
from app.infrastructure.engineering_semantics.sqlalchemy_engineering_semantic_repository import (  # noqa: E501
    SqlAlchemyEngineeringSemanticRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_semantics import EngineeringSemanticSetRecord
from app.services import engineering_semantic_service
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)

DATA_SHEET = (
    "Trasformatore TR1 630 kVA",
    "Trasformatore TR2 20 kV",
    "Trasformatore TR3 400 kVA 500 kVA",
)


def _document(db: Session, filename: str = "schema.pdf") -> DocumentRecord:
    document = DocumentRecord(
        filename=filename,
        file_path=f"/storage/{filename}",
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        project_name="Alpha Substation",
        scope=DocumentScope.CANONICAL_LIBRARY,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _prepare(db: Session, document_id: int, *lines: str, **overrides):
    """Real extraction, resolution and construction, stored through the
    real repositories."""

    from dataclasses import replace

    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(index, index, text)
                    for index, text in enumerate(lines or DATA_SHEET)
                ],
            ),
        ),
        **overrides,
    )
    evidence = extract_evidence(
        segment_canonical_document(source), project_id=3
    )
    evidence = replace(
        evidence,
        document_id=document_id,
        evidence=tuple(
            item for item in evidence.evidence if item.is_persistable
        ),
    )
    SqlAlchemyEngineeringEvidenceRepository(db).save(evidence)

    entity_set = resolve_entities(evidence)
    SqlAlchemyEngineeringEntityRepository(db).save(entity_set)
    SqlAlchemyEngineeringFactRepository(db).save(
        construct_facts(entity_set)
    )


def _prepared(db: Session, *lines: str, **overrides) -> DocumentRecord:
    document = _document(db, overrides.pop("filename", "schema.pdf"))
    _prepare(db, document.id, *lines, **overrides)

    return document


def _interpret(db: Session, document_id: int, **kwargs):
    return engineering_semantic_service.interpret_document_facts(
        SqlAlchemyEngineeringFactRepository(db),
        kwargs.pop(
            "semantic_repository",
            SqlAlchemyEngineeringSemanticRepository(db),
        ),
        document_id=document_id,
        **kwargs,
    )


# --- The happy path ------------------------------------------------------------


def test_facts_are_interpreted_into_statements(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    result = _interpret(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.found_semantics is True


def test_only_the_power_association_is_interpreted(
    db_session: Session,
) -> None:
    """``TR1 630 kVA`` becomes a rated power; ``TR2 20 kV`` becomes
    nothing; ``TR3`` has two competing powers and is declined."""

    document = _prepared(db_session)

    semantic_set = _interpret(db_session, document.id).semantic_set

    assert semantic_set.statement_count == 1
    assert len(semantic_set.diagnostics) == 1
    assert (
        semantic_set.statements[0].statement_type
        is SemanticStatementType.HAS_RATED_POWER
    )


def test_the_declined_subject_is_an_ambiguity_not_a_failure(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    result = _interpret(db_session, document.id)

    assert result.succeeded is True
    assert result.has_ambiguities is True
    assert result.failure is None


def test_a_document_with_no_declared_meaning_is_a_success(
    db_session: Session,
) -> None:
    """Its associations are real and none of them has a declared
    meaning. Not a failure."""

    document = _prepared(db_session, "Trasformatore TR1 20 kV")

    result = _interpret(db_session, document.id)

    assert result.succeeded is True
    assert result.found_semantics is False


def test_the_set_records_the_whole_upstream_source(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    semantic_set = _interpret(db_session, document.id).semantic_set

    assert semantic_set.document_id == document.id
    assert semantic_set.project_id == 3
    assert semantic_set.resolution_policy_version == "1.0"
    assert semantic_set.fact_policy_version == "1.0"
    assert semantic_set.semantic_policy_version == "1.0"


# --- The support chain -----------------------------------------------------------


def test_every_statement_cites_a_fact_in_the_source_set(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    fact_set = SqlAlchemyEngineeringFactRepository(
        db_session
    ).find_latest_for_document(document.id)
    available = {fact.fact_key for fact in fact_set.facts}

    semantic_set = _interpret(db_session, document.id).semantic_set

    for statement in semantic_set.statements:
        assert set(statement.supporting_fact_keys) <= available


def test_the_chain_reaches_evidence_through_facts_and_entities(
    db_session: Session,
) -> None:
    """
    Statement -> fact -> entity -> evidence, all by key, all resolvable
    against what is actually stored.
    """

    document = _prepared(db_session)
    facts = SqlAlchemyEngineeringFactRepository(
        db_session
    ).find_latest_for_document(document.id)
    entities = SqlAlchemyEngineeringEntityRepository(
        db_session
    ).find_latest_for_document(document.id)
    evidence = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    evidence_keys = {item.evidence_key for item in evidence.evidence}

    statement = _interpret(db_session, document.id).semantic_set.statements[
        0
    ]
    fact = facts.fact(statement.supporting_fact_keys[0])
    subject = entities.entity(fact.subject_entity_key)
    obj = entities.entity(fact.object_entity_key)

    assert subject is not None and obj is not None
    assert set(subject.evidence_keys) <= evidence_keys
    assert set(obj.evidence_keys) <= evidence_keys
    assert evidence.evidence


# --- Interpretation never touches what it read ------------------------------------


def test_interpretation_never_modifies_the_facts_it_read(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    facts = SqlAlchemyEngineeringFactRepository(db_session)
    before = facts.find_latest_for_document(document.id)

    _interpret(db_session, document.id)

    assert facts.find_latest_for_document(document.id) == before


def test_interpretation_creates_no_graph_node_or_edge(
    db_session: Session,
) -> None:
    """Semantic Interpretation assigns meaning; the Knowledge Graph
    stores interpreted knowledge. Two responsibilities, two
    milestones."""

    from app.models.engineering_index import EngineeringIndexEntry
    # Repointed by EPIC 31.1: `ProjectEntity`/`EntityRelation` were the
    # ungoverned tables that milestone dropped. The property asserted is
    # now stronger - the stage writes no *governed* knowledge, because
    # knowledge enters the graph only through an explicit promotion of a
    # statement an engineer approved.
    from app.models.governed_knowledge_graph import (
        GovernedGraphEdgeRecord,
        GovernedGraphNodeRecord,
    )

    document = _prepared(db_session)

    _interpret(db_session, document.id)

    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0


# --- Persistence -------------------------------------------------------------------


def test_the_semantic_set_survives_a_round_trip(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    built = _interpret(db_session, document.id).semantic_set
    stored = SqlAlchemyEngineeringSemanticRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_diagnostics_survive_persistence(db_session: Session) -> None:
    document = _prepared(db_session)
    _interpret(db_session, document.id)

    stored = engineering_semantic_service.get_semantic_set(
        SqlAlchemyEngineeringSemanticRepository(db_session), document.id
    )

    assert len(stored.diagnostics) == 1
    assert len(stored.diagnostics[0].candidate_fact_keys) == 2


def test_a_document_never_interpreted_has_no_semantic_set(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    assert (
        engineering_semantic_service.get_semantic_set(
            SqlAlchemyEngineeringSemanticRepository(db_session),
            document.id,
        )
        is None
    )


# --- Idempotency -------------------------------------------------------------------------


def test_re_running_reuses_the_stored_set(db_session: Session) -> None:
    document = _prepared(db_session)

    first = _interpret(db_session, document.id)
    second = _interpret(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.semantic_set == first.semantic_set


def test_re_running_creates_no_second_row(db_session: Session) -> None:
    document = _prepared(db_session)

    _interpret(db_session, document.id)
    _interpret(db_session, document.id)
    _interpret(db_session, document.id)

    assert (
        db_session.query(EngineeringSemanticSetRecord)
        .filter(EngineeringSemanticSetRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_new_semantic_policy_interprets_again(
    db_session: Session,
) -> None:
    """The engineering judgement changed, so the result is a different
    set even though the facts are identical - which is why the policy
    version is part of the key."""

    document = _prepared(db_session)
    _interpret(db_session, document.id)

    result = _interpret(
        db_session, document.id, semantic_policy_version="2.0"
    )

    assert result.reused is False
    assert (
        db_session.query(EngineeringSemanticSetRecord)
        .filter(EngineeringSemanticSetRecord.document_id == document.id)
        .count()
        == 2
    )


def test_the_historical_semantic_set_remains_unchanged(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    first = _interpret(db_session, document.id).semantic_set

    _interpret(db_session, document.id, semantic_policy_version="2.0")

    historical = SqlAlchemyEngineeringSemanticRepository(
        db_session
    ).find_for_source(
        document.id, first.content_checksum, "1.0", "1.0", "1.0"
    )

    assert historical == first


# --- Typed failures -----------------------------------------------------------------------


def test_a_document_without_facts_is_refused(db_session: Session) -> None:
    document = _document(db_session)

    result = _interpret(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        SemanticInterpretationFailureCode.FACT_SET_MISSING
    )


def test_an_unsupported_fact_policy_is_refused(
    db_session: Session,
) -> None:
    """A newer construction policy may carry predicates this interpreter
    would silently ignore, and a semantic set missing half its meaning is
    worse than a visible refusal."""

    from app.models.engineering_facts import EngineeringFactSetRecord

    document = _prepared(db_session)
    stored = (
        db_session.query(EngineeringFactSetRecord)
        .filter(EngineeringFactSetRecord.document_id == document.id)
        .one()
    )
    stored.fact_policy_version = "99.0"
    db_session.commit()

    result = _interpret(db_session, document.id)

    assert result.failure.code is (
        SemanticInterpretationFailureCode.UNSUPPORTED_FACT_VERSION
    )
    assert "99.0" in result.failure.message


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(EngineeringSemanticRepository):
        def save(self, semantic_set):
            raise RuntimeError("the disk is full")

        def find_for_source(
            self,
            document_id,
            content_checksum,
            resolution_policy_version,
            fact_policy_version,
            semantic_policy_version,
        ):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _prepared(db_session)

    result = _interpret(
        db_session, document.id, semantic_repository=FailingRepository()
    )

    assert result.failure.code is (
        SemanticInterpretationFailureCode.SEMANTIC_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    document = _document(db_session)

    result = _interpret(db_session, document.id)

    assert result.failure.message
    assert result.semantic_set is None
