"""
Shared fixtures for the Engineering Entity Resolution service tests.

Evidence is produced by the **real extractor** over real canonical text
and stored through Milestone 28.1's own repository, so tests built on
these helpers prove the two layers meet correctly - a fake evidence
source could agree with the domain and disagree with what 28.1 actually
persists.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
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


def document(db: Session, filename: str = "schema.pdf") -> DocumentRecord:
    record = DocumentRecord(
        filename=filename,
        file_path=f"/storage/{filename}",
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        project_name="Alpha Substation",
        scope=DocumentScope.CANONICAL_LIBRARY,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def store_evidence(
    db: Session, document_id: int, *lines: str, **overrides
) -> None:
    """Real extraction over real canonical text, stored through the real
    evidence repository."""

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
        **{"document_id": document_id, **overrides},
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


def prepared(db: Session, *lines: str, **overrides) -> DocumentRecord:
    record = document(db, overrides.pop("filename", "schema.pdf"))
    store_evidence(db, record.id, *lines, **overrides)

    return record


def resolve(db: Session, document_id: int, **kwargs):
    return engineering_entity_service.resolve_document_entities(
        SqlAlchemyEngineeringEvidenceRepository(db),
        kwargs.pop(
            "entity_repository", SqlAlchemyEngineeringEntityRepository(db)
        ),
        document_id=document_id,
        **kwargs,
    )
