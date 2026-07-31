"""
Service tests for Engineering Evidence Extraction (Milestone 28.1),
against a real (in-memory) database through the real SQLAlchemy adapters.

The canonical text is stored through Milestone 27.1's own repository, so
these prove the two layers meet correctly - a fake source could agree
with the domain and disagree with what 27.1 actually persists.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_evidence.engineering_evidence_repository import (
    EngineeringEvidenceRepository,
)
from app.domain.engineering_evidence.evidence_failures import (
    EvidenceFailureCode,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.engineering_evidence import EngineeringEvidenceSetRecord
from app.services import engineering_evidence_service
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)

SUBSTATION_LINES = (
    "Trasformatore T1 20 kV / 400 V, 630 kVA",
    "Cavo 240 mm² - interruttore 52-Q1 1250 A",
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


def _store_canonical_text(
    db: Session, document_id: int, *lines: str, **overrides
) -> None:
    from dataclasses import replace

    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(index, index, text)
                    for index, text in enumerate(lines or SUBSTATION_LINES)
                ],
            ),
        ),
        **overrides,
    )
    segmentation = segment_canonical_document(source)

    SqlAlchemyCanonicalTextRepository(db).save(
        replace(segmentation, document_id=document_id)
    )


def _prepared(db: Session, *lines: str, **overrides) -> DocumentRecord:
    document = _document(db, overrides.pop("filename", "schema.pdf"))
    _store_canonical_text(db, document.id, *lines, **overrides)

    return document


def _extract(db: Session, document_id: int, **kwargs):
    return engineering_evidence_service.extract_document_evidence(
        SqlAlchemyCanonicalTextRepository(db),
        kwargs.pop(
            "evidence_repository",
            SqlAlchemyEngineeringEvidenceRepository(db),
        ),
        document_id=document_id,
        **kwargs,
    )


# --- The happy path -----------------------------------------------------------


def test_canonical_text_is_extracted_into_evidence(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    result = _extract(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.found_evidence is True
    assert result.evidence_set.evidence_count == 7


def test_the_set_records_its_canonical_source_and_policy(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    evidence_set = _extract(
        db_session, document.id, project_id=9
    ).evidence_set

    assert evidence_set.document_id == document.id
    assert evidence_set.project_id == 9
    assert evidence_set.segmentation_version == "1.0"
    assert evidence_set.extraction_policy_version == "1.0"


def test_a_document_with_nothing_recognisable_is_a_success(
    db_session: Session,
) -> None:
    """Finding nothing is not a failure - a document may simply contain
    nothing these rules recognise."""

    document = _prepared(db_session, "Il presente documento descrive.")

    result = _extract(db_session, document.id)

    assert result.succeeded is True
    assert result.found_evidence is False
    assert result.evidence_set.is_empty


# --- Persistence round-trip -----------------------------------------------------


def test_the_evidence_survives_a_round_trip_through_the_database(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    built = _extract(db_session, document.id).evidence_set
    stored = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_decimal_values_survive_persistence_exactly(
    db_session: Session,
) -> None:
    """``Numeric``, never ``Float``: a rated voltage that read back as
    20.500000000000001 kV would be a defect nobody could explain."""

    document = _prepared(db_session, "Tensione 20,5 kV e potenza 630 kVA")
    _extract(db_session, document.id)

    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )
    voltage = stored.of_type(EvidenceType.VOLTAGE_VALUE)[0]
    power = stored.of_type(EvidenceType.POWER_VALUE)[0]

    assert voltage.quantity.value == Decimal("20.5")
    assert isinstance(voltage.quantity.value, Decimal)
    assert power.quantity.base_value == Decimal("630000")


def test_provenance_survives_persistence(db_session: Session) -> None:
    document = _prepared(db_session)
    _extract(db_session, document.id)

    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )
    item = stored.of_type(EvidenceType.CABLE_SECTION_VALUE)[0]

    assert item.observed_text == "240 mm²"
    assert item.provenance.page_number == 1
    assert item.provenance.line_index == 1
    assert item.provenance.spans
    assert item.provenance.spans[0].character_end > 0


def test_the_rule_id_and_version_are_persisted(
    db_session: Session,
) -> None:
    document = _prepared(db_session)
    _extract(db_session, document.id)

    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )

    for item in stored.evidence:
        assert item.rule_id
        assert item.rule_version == "1.0"


def test_symbols_survive_persistence(db_session: Session) -> None:
    document = _prepared(db_session, "Cavo 240 mm² e sezione 150 mm2")
    _extract(db_session, document.id)

    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )
    observed = [
        item.observed_text
        for item in stored.of_type(EvidenceType.CABLE_SECTION_VALUE)
    ]

    assert observed == ["240 mm²", "150 mm2"]


def test_a_document_never_extracted_has_no_evidence(
    db_session: Session,
) -> None:
    document = _prepared(db_session)

    assert (
        engineering_evidence_service.get_evidence_set(
            SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
        )
        is None
    )


# --- Rejected candidates never reach storage --------------------------------------


def test_rejected_candidates_are_diagnostics_not_evidence(
    db_session: Session,
) -> None:
    document = _prepared(db_session, "Potenza 1.250 kVA")

    result = _extract(db_session, document.id)
    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )

    assert stored.with_status(EvidenceStatus.REJECTED) == ()
    assert len(stored.with_status(EvidenceStatus.AMBIGUOUS)) == 1
    assert result.rejected_count == 0


def test_an_ambiguous_item_is_stored_without_a_value(
    db_session: Session,
) -> None:
    """Persisted because a reviewer can settle it, and carried without a
    number so no consumer can read a guess as a measurement."""

    document = _prepared(db_session, "Potenza 1.250 kVA")
    _extract(db_session, document.id)

    stored = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db_session), document.id
    )
    item = stored.with_status(EvidenceStatus.AMBIGUOUS)[0]

    assert item.observed_text == "1.250 kVA"
    assert item.quantity is None


# --- Idempotency --------------------------------------------------------------------


def test_re_running_reuses_the_stored_set(db_session: Session) -> None:
    document = _prepared(db_session)

    first = _extract(db_session, document.id)
    second = _extract(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.evidence_set == first.evidence_set


def test_re_running_creates_no_second_row(db_session: Session) -> None:
    document = _prepared(db_session)

    _extract(db_session, document.id)
    _extract(db_session, document.id)
    _extract(db_session, document.id)

    assert (
        db_session.query(EngineeringEvidenceSetRecord)
        .filter(EngineeringEvidenceSetRecord.document_id == document.id)
        .count()
        == 1
    )


def test_a_changed_canonical_source_produces_a_distinct_set(
    db_session: Session,
) -> None:
    document = _prepared(db_session, "Tensione 20 kV")
    first = _extract(db_session, document.id).evidence_set

    _store_canonical_text(
        db_session,
        document.id,
        "Tensione 132 kV",
        content_checksum="d" * 64,
    )
    second = _extract(db_session, document.id)

    assert second.reused is False
    assert second.evidence_set.content_checksum != first.content_checksum
    assert (
        second.evidence_set.of_type(EvidenceType.VOLTAGE_VALUE)[0]
        .quantity.value
        == Decimal("132")
    )


def test_the_historical_set_remains_unchanged(
    db_session: Session,
) -> None:
    """A conclusion drawn from last year's revision must stay
    explainable, so the old set is kept beside the new one."""

    document = _prepared(db_session, "Tensione 20 kV")
    first = _extract(db_session, document.id).evidence_set

    _store_canonical_text(
        db_session,
        document.id,
        "Tensione 132 kV",
        content_checksum="d" * 64,
    )
    _extract(db_session, document.id)

    historical = SqlAlchemyEngineeringEvidenceRepository(
        db_session
    ).find_for_source(document.id, first.content_checksum, "1.0")

    assert historical == first
    assert (
        historical.of_type(EvidenceType.VOLTAGE_VALUE)[0].quantity.value
        == Decimal("20")
    )


def test_a_new_policy_version_extracts_again(db_session: Session) -> None:
    """The rules changed, so the result is a different set even though
    the canonical source is identical - which is why the policy version
    is part of the key."""

    document = _prepared(db_session)
    _extract(db_session, document.id)

    result = _extract(
        db_session, document.id, extraction_policy_version="2.0"
    )

    assert result.reused is False
    assert (
        db_session.query(EngineeringEvidenceSetRecord)
        .filter(EngineeringEvidenceSetRecord.document_id == document.id)
        .count()
        == 2
    )


# --- Typed failures -------------------------------------------------------------------


def test_a_document_without_canonical_text_is_refused(
    db_session: Session,
) -> None:
    document = _document(db_session)

    result = _extract(db_session, document.id)

    assert result.succeeded is False
    assert result.failure.code is (
        EvidenceFailureCode.CANONICAL_TEXT_MISSING
    )


def test_an_unknown_document_is_refused_the_same_way(
    db_session: Session,
) -> None:
    result = _extract(db_session, 4321)

    assert result.failure.code is (
        EvidenceFailureCode.CANONICAL_TEXT_MISSING
    )


def test_an_unsupported_segmentation_version_is_refused(
    db_session: Session,
) -> None:
    """A newer segmentation may group tokens differently, and provenance
    recorded against the wrong grouping would point at the wrong
    characters."""

    from app.models.canonical_text import CanonicalTextDocumentRecord

    document = _prepared(db_session)
    stored = (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .one()
    )
    stored.segmentation_version = "99.0"
    db_session.commit()

    result = _extract(db_session, document.id)

    assert result.failure.code is (
        EvidenceFailureCode.UNSUPPORTED_CANONICAL_TEXT_VERSION
    )
    assert "99.0" in result.failure.message


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session,
) -> None:
    class FailingRepository(EngineeringEvidenceRepository):
        def save(self, evidence_set):
            raise RuntimeError("the disk is full")

        def find_for_source(
            self, document_id, content_checksum, extraction_policy_version
        ):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _prepared(db_session)

    result = _extract(
        db_session, document.id, evidence_repository=FailingRepository()
    )

    assert result.failure.code is (
        EvidenceFailureCode.EVIDENCE_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(db_session: Session) -> None:
    document = _document(db_session)

    result = _extract(db_session, document.id)

    assert result.failure.message
    assert result.evidence_set is None


# --- No entity or relationship is created -----------------------------------------


def test_extraction_writes_no_graph_and_no_index(
    db_session: Session,
) -> None:
    """The tables a future milestone will populate stay empty. This one
    observes; it does not conclude."""

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

    _extract(db_session, document.id)

    assert db_session.query(GovernedGraphNodeRecord).count() == 0
    assert db_session.query(GovernedGraphEdgeRecord).count() == 0
    assert db_session.query(EngineeringIndexEntry).count() == 0


def test_extraction_reads_only_canonical_text(
    db_session: Session,
) -> None:
    """The strongest available proof that no document is reopened: the
    document's ``file_path`` points at a file that never existed, and
    extraction succeeds regardless."""

    document = _prepared(db_session)
    document.file_path = "/nowhere/never_written.pdf"
    db_session.commit()

    result = _extract(db_session, document.id)

    assert result.succeeded
    assert result.evidence_set.evidence_count == 7
