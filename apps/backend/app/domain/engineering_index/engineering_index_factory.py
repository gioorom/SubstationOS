from __future__ import annotations

from datetime import datetime

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_validator import (
    EngineeringIndexValidator,
)


class EngineeringIndexEntryFactory:
    """
    Builds a new ``IndexEntry``, enforcing invariants at construction
    time (CLAUDE.md §4.2).
    """

    @staticmethod
    def create(
        *,
        project_id: int,
        document_id: int,
        kind: EngineeringIndexEntryKind,
        identifier: str,
        created_at: datetime,
        page: int | None = None,
        locator: IndexEntryLocator | None = None,
        label: str | None = None,
    ) -> IndexEntry:
        """
        ``locator`` is the general source-location reference (page,
        sheet, cell range, drawing layout, region, ...). ``page`` is
        kept as a convenience for the common PDF case and is ignored
        when ``locator`` is also given.
        """

        EngineeringIndexValidator.validate_kind(kind)
        EngineeringIndexValidator.validate_identifier(identifier)

        if locator is None:
            EngineeringIndexValidator.validate_page(page)
            locator = IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE,
                value=str(page) if page is not None else None,
            )
        else:
            EngineeringIndexValidator.validate_locator(locator)

        return IndexEntry(
            id=None,
            project_id=project_id,
            document_id=document_id,
            kind=kind,
            identifier=identifier,
            locator=locator,
            label=label,
            created_at=created_at,
        )
