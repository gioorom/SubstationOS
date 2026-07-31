"""
Service tests for Engineering Fact Construction (Milestone 29.2),
against a real (in-memory) database through the real adapters.

Evidence and entities are produced by the **real** extractor and resolver
and stored through their own repositories, so these prove the three
layers meet correctly.
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
from app.domain.engineering_facts.engineering_fact_repository import (
    EngineeringFactRepository,
)
from app.domain.engineering_facts.fact_failures import (
    FactConstructionFailureCode,
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
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_facts import EngineeringFactSetRecord
from app.services import engineering_fact_service
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)

DATA_SHEET = (
    "Trasformatore TR1 630 kVA",
    "Interruttore 52-Q1 1250 A",
    "TR2 TR3 20 kV",
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
    """Real extraction and resolution, stored through the real
    repositories."""

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
    SqlAlchemyEngineeringEntityRepository(db).save(
        resolve_entities(evidence)
    )


def _prepared(db: Session, *lines: str, **overrides) -> DocumentRecord:
    document = _document(db, overrides.pop("filename", "schema.pdf"))
    _prepare(db, document.id, *lines, **overrides)

    return document


def _construct(db: Session, document_id: int, **kwargs):
    return engineering_fact_service.construct_document_facts(
        SqlAlchemyEngineeringEntityRepository(db),
        SqlAlchemyEngineeringEvidenceRepository(db),
        kwargs.pop(
            "fact_repository", SqlAlchemyEngineeringFactRepository(db)
        ),
        document_id=document_id,
        **kwargs,
    )


# --- The happy path --------------------------------------------------------------


def test_entities_are_associated_into_facts(db_session: Session) -> None:
    document = _prepared(db_session)

    result = _construct(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.found_facts is True


def test_the_declined_line_is_reported_as_an_ambiguity_not_a_failure(
    db_session: Session,
) -> None:
    """``TR2 TR3 20 kV`` produces no fact and one diagnostic. The
    construction still succeeds - the rules working is not a system
    failure."""

    document = _prepared(db_session)

    result = _construct(db_session, document.id)

    assert result.succeeded is True
    assert result.has_ambiguities is True
    assert result.fact_set.fact_count == 2


def test_the_set_records_its_source_and_policies(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    fact_set = _construct(db_session, document.id).fact_set

    assert fact_set.document_id == document.id
    assert fact_set.project_id == 3
    assert fact_set.resolution_policy_version == "1.0"
    assert fact_set.fact_policy_version == "1.0"


def test_a_document_with_nothing_associable_is_a_success(
    db_session: Session,
) -> None:
    """No line holds a designation and a quantity together. Not a
    failure."""

    document = _prepared(db_session, "Trasformatore TR1 in cabina")

    result = _construct(db_session, document.id)

    assert result.succeeded is True
    assert result.found_facts is False
    assert result.has_ambiguities is False


# --- Support and provenance -------------------------------------------------------


def test_every_fact_names_subject_object_and_supporting_evidence(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    fact_set = _construct(db_session, document.id).fact_set

    for fact in fact_set.facts:
        assert fact.subject_entity_key
        assert fact.object_entity_key
        assert fact.subject_support
        assert fact.object_support


def test_fact_support_resolves_against_the_stored_evidence(
    db_session: Session,
) -> None:
    """The chain that makes a fact explainable: every supporting key is a
    real observation in the evidence set."""

    document = _prepared(db_session)
    evidence_set = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    available = {item.evidence_key for item in evidence_set.evidence}

    fact_set = _construct(db_session, document.id).fact_set

    for fact in fact_set.facts:
        assert set(fact.support_keys) <= available


def test_fact_support_resolves_to_the_entities_that_created_it(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    entity_set = SqlAlchemyEngineeringEntityRepository(
        db_session
    ).find_latest_for_document(document.id)
    by_key = {entity.entity_key: entity for entity in entity_set.entities}

    fact_set = _construct(db_session, document.id).fact_set

    for fact in fact_set.facts:
        subject = by_key[fact.subject_entity_key]
        obj = by_key[fact.object_entity_key]

        assert {
            reference.evidence_key
            for reference in fact.subject_support
        } <= set(subject.evidence_keys)
        assert {
            reference.evidence_key for reference in fact.object_support
        } <= set(obj.evidence_keys)


def test_provenance_is_recoverable_through_the_support(
    db_session: Session,
) -> None:
    """From a fact to the characters: support gives an evidence key, and
    the evidence carries the character-level chain."""

    document = _prepared(db_session)
    evidence_set = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    by_key = {item.evidence_key: item for item in evidence_set.evidence}

    fact = _construct(db_session, document.id).fact_set.facts[0]

    for reference in fact.support:
        evidence = by_key[reference.evidence_key]

        assert evidence.provenance.line_index == reference.line_index
        assert evidence.provenance.spans


# --- Construction never touches what it read ----------------------------------------


def test_construction_never_modifies_entities_or_evidence(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    entities = SqlAlchemyEngineeringEntityRepository(db_session)
    evidence = SqlAlchemyEngineeringEvidenceRepository(db_session)
    before_entities = entities.find_latest_for_document(document.id)
    before_evidence = evidence.find_latest_for_document(document.id)

    _construct(db_session, document.id)

    assert entities.find_latest_for_document(document.id) == before_entities
    assert evidence.find_latest_for_document(document.id) == before_evidence


def test_construction_creates_no_graph_node_or_edge(
    db_session: Session,
) -> None:
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

    _construct(db_session, document.id)

    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0


# --- Persistence ---------------------------------------------------------------------


def test_the_fact_set_survives_a_round_trip(db_session: Session) -> None:
    document = _prepared(db_session)

    built = _construct(db_session, document.id).fact_set
    stored = SqlAlchemyEngineeringFactRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_diagnostics_survive_persistence(db_session: Session) -> None:
    """So that a re-used set reports the declined lines too, rather than
    looking like a document with nothing ambiguous in it."""

    document = _prepared(db_session)
    _construct(db_session, document.id)

    stored = engineering_fact_service.get_fact_set(
        SqlAlchemyEngineeringFactRepository(db_session), document.id
    )

    assert len(stored.diagnostics) == 1
    assert len(stored.diagnostics[0].subject_entity_keys) == 2


def test_a_document_never_constructed_has_no_fact_set(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    assert (
        engineering_fact_service.get_fact_set(
            SqlAlchemyEngineeringFactRepository(db_session), document.id
        )
        is None
    )


# --- Idempotency ------------------------------------------------------------------------


def test_re_running_reuses_the_stored_set(db_session: Session) -> None:
    document = _prepared(db_session)

    first = _construct(db_session, document.id)
    second = _construct(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.fact_set == first.fact_set


def test_re_running_creates_no_second_row(db_session: Session) -> None:
    document = _prepared(db_session)

    _construct(db_session, document.id)
    _construct(db_session, document.id)
    _construct(db_session, document.id)

    assert (
        db_session.query(EngineeringFactSetRecord)
        .filter(EngineeringFactSetRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_new_fact_policy_constructs_again(db_session: Session) -> None:
    document = _prepared(db_session)
    _construct(db_session, document.id)

    result = _construct(db_session, document.id, fact_policy_version="2.0")

    assert result.reused is False
    assert (
        db_session.query(EngineeringFactSetRecord)
        .filter(EngineeringFactSetRecord.document_id == document.id)
        .count()
        == 2
    )


def test_the_historical_fact_set_remains_unchanged(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    first = _construct(db_session, document.id).fact_set

    _construct(db_session, document.id, fact_policy_version="2.0")

    historical = SqlAlchemyEngineeringFactRepository(
        db_session
    ).find_for_source(document.id, first.content_checksum, "1.0", "1.0")

    assert historical == first


def test_fact_history_survives_a_newer_entity_set(
    db_session: Session,
) -> None:
    """
    The reason entities are referenced by key rather than by foreign key.

    A re-resolution produces a new entity set; the earlier fact set must
    still be readable, because a fact recorded last year is a statement
    about what was true then.
    """

    document = _prepared(db_session)
    first = _construct(db_session, document.id).fact_set

    entities = SqlAlchemyEngineeringEntityRepository(db_session)
    evidence_set = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    entities.save(
        resolve_entities(evidence_set, resolution_policy_version="2.0")
    )

    historical = SqlAlchemyEngineeringFactRepository(
        db_session
    ).find_for_source(document.id, first.content_checksum, "1.0", "1.0")

    assert historical == first
    assert historical.facts


# --- Typed failures -----------------------------------------------------------------------


def test_a_document_without_entities_is_refused(
    db_session: Session,
) -> None:
    document = _document(db_session)

    result = _construct(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        FactConstructionFailureCode.ENTITY_SET_MISSING
    )


def test_an_unsupported_entity_set_version_is_refused(
    db_session: Session,
) -> None:
    from app.models.engineering_entities import (
        EngineeringEntitySetRecord,
    )

    document = _prepared(db_session)
    stored = (
        db_session.query(EngineeringEntitySetRecord)
        .filter(EngineeringEntitySetRecord.document_id == document.id)
        .one()
    )
    stored.resolution_policy_version = "99.0"
    db_session.commit()

    result = _construct(db_session, document.id)

    assert result.failure.code is (
        FactConstructionFailureCode.UNSUPPORTED_ENTITY_SET_VERSION
    )
    assert "99.0" in result.failure.message


def test_missing_entity_evidence_is_refused(db_session: Session) -> None:
    """Associations would rest on support nobody could check."""

    from app.models.engineering_evidence import (
        EngineeringEvidenceSetRecord,
    )

    document = _prepared(db_session)
    stored = (
        db_session.query(EngineeringEvidenceSetRecord)
        .filter(EngineeringEvidenceSetRecord.document_id == document.id)
        .one()
    )
    db_session.delete(stored)
    db_session.commit()

    result = _construct(db_session, document.id)

    assert result.failure.code is (
        FactConstructionFailureCode.ENTITY_EVIDENCE_MISSING
    )


def test_a_source_identity_mismatch_is_refused(
    db_session: Session,
) -> None:
    """Continuing would associate entities from one revision using
    observations from another."""

    from app.models.engineering_evidence import (
        EngineeringEvidenceSetRecord,
    )

    document = _prepared(db_session)
    stored = (
        db_session.query(EngineeringEvidenceSetRecord)
        .filter(EngineeringEvidenceSetRecord.document_id == document.id)
        .one()
    )
    stored.content_checksum = "d" * 64
    db_session.commit()

    result = _construct(db_session, document.id)

    assert result.failure.code is (
        FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY
    )


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(EngineeringFactRepository):
        def save(self, fact_set):
            raise RuntimeError("the disk is full")

        def find_for_source(
            self,
            document_id,
            content_checksum,
            resolution_policy_version,
            fact_policy_version,
        ):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _prepared(db_session)

    result = _construct(
        db_session, document.id, fact_repository=FailingRepository()
    )

    assert result.failure.code is (
        FactConstructionFailureCode.FACT_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    document = _document(db_session)

    result = _construct(db_session, document.id)

    assert result.failure.message
    assert result.fact_set is None
