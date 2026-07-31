"""
Service tests for Engineering Entity Resolution (Milestone 29.1),
against a real (in-memory) database through the real adapters.

Evidence is produced by the **real extractor** over real canonical text
and stored through Milestone 28.1's own repository, so these prove the
two layers meet correctly - a fake evidence source could agree with the
domain and disagree with what 28.1 actually persists.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_entities.engineering_entity_repository import (
    EngineeringEntityRepository,
)
from app.domain.engineering_entities.entity_failures import (
    EntityResolutionFailureCode,
)
from app.domain.engineering_entities.entity_models import EntityType
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_entities import EngineeringEntitySetRecord
from app.services import engineering_entity_service
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)

SUBSTATION_LINES = (
    "Trasformatore T1 - potenza 630 kVA",
    "Il trasformatore (T1) alimenta il quadro",
    "Interruttore 52-Q1, tensione 20 kV",
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


def _store_evidence(
    db: Session, document_id: int, *lines: str, **overrides
) -> None:
    """Real extraction over real canonical text, stored through the real
    evidence repository."""

    from dataclasses import replace

    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(index, index, text)
                    for index, text in enumerate(
                        lines or SUBSTATION_LINES
                    )
                ],
            ),
        ),
        **overrides,
    )
    evidence = extract_evidence(
        segment_canonical_document(source), project_id=3
    )

    SqlAlchemyEngineeringEvidenceRepository(db).save(
        replace(
            evidence,
            document_id=document_id,
            evidence=tuple(
                item for item in evidence.evidence if item.is_persistable
            ),
        )
    )


def _prepared(db: Session, *lines: str, **overrides) -> DocumentRecord:
    document = _document(db, overrides.pop("filename", "schema.pdf"))
    _store_evidence(db, document.id, *lines, **overrides)

    return document


def _resolve(db: Session, document_id: int, **kwargs):
    return engineering_entity_service.resolve_document_entities(
        SqlAlchemyEngineeringEvidenceRepository(db),
        kwargs.pop(
            "entity_repository", SqlAlchemyEngineeringEntityRepository(db)
        ),
        document_id=document_id,
        **kwargs,
    )


# --- The happy path --------------------------------------------------------------


def test_evidence_resolves_into_entities(db_session: Session) -> None:
    document = _prepared(db_session)

    result = _resolve(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.found_entities is True


def test_repeated_designations_resolve_to_one_entity(
    db_session: Session,
) -> None:
    """``T1`` appears twice in the corpus text - once bare, once
    parenthesised - and is one object."""

    document = _prepared(db_session)

    entity_set = _resolve(db_session, document.id).entity_set
    designations = entity_set.of_type(EntityType.EQUIPMENT_DESIGNATION)

    assert {entity.label for entity in designations} == {"T1", "52-Q1"}
    t1 = next(entity for entity in designations if entity.label == "T1")
    assert t1.evidence_count == 2


def test_quantities_stay_independent_entities(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    entity_set = _resolve(db_session, document.id).entity_set
    quantities = entity_set.of_type(EntityType.ENGINEERING_QUANTITY)

    assert {entity.label for entity in quantities} == {
        "630 kVA",
        "20 kV",
    }
    assert all(entity.evidence_count == 1 for entity in quantities)


def test_the_set_records_the_source_and_the_policies(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    entity_set = _resolve(db_session, document.id).entity_set

    assert entity_set.document_id == document.id
    assert entity_set.project_id == 3
    assert entity_set.extraction_policy_version == "1.0"
    assert entity_set.resolution_policy_version == "1.0"


def test_a_document_with_no_groupable_evidence_is_a_success(
    db_session: Session,
) -> None:
    """Finding nothing is not a failure - a document may contain no
    observations these rules group into anything."""

    document = _prepared(db_session, "Il presente documento descrive.")

    result = _resolve(db_session, document.id)

    assert result.succeeded is True
    assert result.found_entities is False


# --- Provenance is preserved -------------------------------------------------------


def test_each_entity_enumerates_the_evidence_that_created_it(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    entity_set = _resolve(db_session, document.id).entity_set

    for entity in entity_set.entities:
        assert entity.evidence_count >= 1
        assert all(reference.evidence_key for reference in entity.evidence)


def test_the_cited_evidence_keys_exist_in_the_evidence_set(
    db_session: Session,
) -> None:
    """The chain that makes an entity traceable: every key it cites is a
    real observation in its source."""

    document = _prepared(db_session)
    evidence_set = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    available = {item.evidence_key for item in evidence_set.evidence}

    entity_set = _resolve(db_session, document.id).entity_set

    for entity in entity_set.entities:
        assert set(entity.evidence_keys) <= available


def test_entity_locations_match_the_evidence_locations(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    evidence_set = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)
    by_key = {item.evidence_key: item for item in evidence_set.evidence}

    entity_set = _resolve(db_session, document.id).entity_set

    for entity in entity_set.entities:
        for reference in entity.evidence:
            provenance = by_key[reference.evidence_key].provenance

            assert reference.page_number == provenance.page_number
            assert reference.line_index == provenance.line_index
            assert reference.token_start == provenance.token_start


# --- Persistence ---------------------------------------------------------------------


def test_the_entity_set_survives_a_round_trip(db_session: Session) -> None:
    document = _prepared(db_session)

    built = _resolve(db_session, document.id).entity_set
    stored = SqlAlchemyEngineeringEntityRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_decimal_quantities_survive_persistence_exactly(
    db_session: Session,
) -> None:
    document = _prepared(db_session, "Potenza 630 kVA e tensione 20,5 kV")
    _resolve(db_session, document.id)

    stored = engineering_entity_service.get_entity_set(
        SqlAlchemyEngineeringEntityRepository(db_session), document.id
    )
    values = {
        entity.quantity.value
        for entity in stored.of_type(EntityType.ENGINEERING_QUANTITY)
    }

    assert values == {Decimal("630"), Decimal("20.5")}


def test_a_document_never_resolved_has_no_entity_set(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    assert (
        engineering_entity_service.get_entity_set(
            SqlAlchemyEngineeringEntityRepository(db_session), document.id
        )
        is None
    )


# --- Resolution never touches evidence -------------------------------------------------


def test_resolution_never_modifies_the_evidence_it_read(
    db_session: Session,
) -> None:
    """Resolving something must never modify what it was resolved
    from."""

    document = _prepared(db_session)
    repository = SqlAlchemyEngineeringEvidenceRepository(db_session)
    before = repository.find_latest_for_document(document.id)

    _resolve(db_session, document.id)

    assert repository.find_latest_for_document(document.id) == before


def test_resolution_creates_no_graph_node_and_no_index_entry(
    db_session: Session,
) -> None:
    """The tables a future milestone will populate stay empty. This one
    produces a hypothesis; it does not commit to it."""

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

    _resolve(db_session, document.id)

    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0


# --- Idempotency ------------------------------------------------------------------------


def test_re_running_reuses_the_stored_set(db_session: Session) -> None:
    document = _prepared(db_session)

    first = _resolve(db_session, document.id)
    second = _resolve(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.entity_set == first.entity_set


def test_re_running_creates_no_second_row(db_session: Session) -> None:
    document = _prepared(db_session)

    _resolve(db_session, document.id)
    _resolve(db_session, document.id)
    _resolve(db_session, document.id)

    assert (
        db_session.query(EngineeringEntitySetRecord)
        .filter(EngineeringEntitySetRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_new_resolution_policy_resolves_again(
    db_session: Session,
) -> None:
    """The rules changed, so the result is a different set even though
    the evidence is identical - which is why the policy version is part
    of the key."""

    document = _prepared(db_session)
    _resolve(db_session, document.id)

    result = _resolve(
        db_session, document.id, resolution_policy_version="2.0"
    )

    assert result.reused is False
    assert (
        db_session.query(EngineeringEntitySetRecord)
        .filter(EngineeringEntitySetRecord.document_id == document.id)
        .count()
        == 2
    )


def test_the_historical_set_remains_unchanged(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    first = _resolve(db_session, document.id).entity_set

    _resolve(db_session, document.id, resolution_policy_version="2.0")

    historical = SqlAlchemyEngineeringEntityRepository(
        db_session
    ).find_for_source(document.id, first.content_checksum, "1.0")

    assert historical == first


# --- Typed failures -----------------------------------------------------------------------


def test_a_document_without_evidence_is_refused(
    db_session: Session,
) -> None:
    document = _document(db_session)

    result = _resolve(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        EntityResolutionFailureCode.EVIDENCE_SET_MISSING
    )


def test_an_unknown_document_is_refused_the_same_way(
    db_session: Session,
) -> None:
    result = _resolve(db_session, 4321)

    assert result.failure.code is (
        EntityResolutionFailureCode.EVIDENCE_SET_MISSING
    )


def test_an_unsupported_extraction_policy_is_refused(
    db_session: Session,
) -> None:
    """A newer extraction policy may carry evidence types this resolver
    would silently drop, and an entity set missing half its evidence is
    worse than a visible refusal."""

    from app.models.engineering_evidence import EngineeringEvidenceSetRecord

    document = _prepared(db_session)
    stored = (
        db_session.query(EngineeringEvidenceSetRecord)
        .filter(EngineeringEvidenceSetRecord.document_id == document.id)
        .one()
    )
    stored.extraction_policy_version = "99.0"
    db_session.commit()

    result = _resolve(db_session, document.id)

    assert result.failure.code is (
        EntityResolutionFailureCode.UNSUPPORTED_EXTRACTION_POLICY_VERSION
    )
    assert "99.0" in result.failure.message


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(EngineeringEntityRepository):
        def save(self, entity_set):
            raise RuntimeError("the disk is full")

        def find_for_source(
            self, document_id, content_checksum, resolution_policy_version
        ):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _prepared(db_session)

    result = _resolve(
        db_session, document.id, entity_repository=FailingRepository()
    )

    assert result.failure.code is (
        EntityResolutionFailureCode.ENTITY_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    document = _document(db_session)

    result = _resolve(db_session, document.id)

    assert result.failure.message
    assert result.entity_set is None
