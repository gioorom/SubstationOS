"""Shared, non-collected builders for Document Retrieval domain tests
(Milestone 23B.1). Everything here is a plain in-memory value object - no
database, no session, no AI provider."""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_index.document_metadata import DocumentMetadata
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.project.project_document_scope import DocumentScope

NOW = datetime(2026, 1, 1, 5, 0, 0)


def entry(
    *,
    entry_id: int | None = 1,
    project_id: int = 1,
    document_id: int = 10,
    identifier: str = "T2",
    kind: EngineeringIndexEntryKind = EngineeringIndexEntryKind.EQUIPMENT,
    page: int | None = 3,
    locator: IndexEntryLocator | None = None,
    label: str | None = None,
) -> IndexEntry:
    if locator is None:
        locator = (
            IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE, value=str(page)
            )
            if page is not None
            else IndexEntryLocator(kind=IndexEntryLocatorKind.OTHER, value="x")
        )

    return IndexEntry(
        id=entry_id,
        project_id=project_id,
        document_id=document_id,
        kind=kind,
        identifier=identifier,
        locator=locator,
        label=label,
        created_at=NOW,
    )


def metadata(
    *,
    document_id: int = 10,
    project_id: int = 1,
    title: str = "montante-T2-schema-funzionale.pdf",
    document_format: str = "pdf",
    document_category: str = "functional_schematic",
    revision: str = "02",
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=document_id,
        project_id=project_id,
        title=title,
        document_format=document_format,
        document_category=document_category,
        revision=revision,
        scope=DocumentScope.PROJECT,
    )
