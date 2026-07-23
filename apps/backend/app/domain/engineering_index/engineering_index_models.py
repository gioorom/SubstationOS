from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """
    One candidate mention recorded by the Engineering Index, per
    Architecture Freeze v1.0
    (docs/architecture/project_intelligence_architecture.md §5).

    An ``IndexEntry`` is a lead, not a fact: it carries no review state,
    no confidence, and no relationships to other entries (ADR-0002). It
    exists purely for discoverability - search, navigation, and
    completeness checking - and is freely rebuildable. Turning a mention
    into reviewed engineering knowledge is the Review Workflow and
    Project Knowledge Graph's responsibility, not this bounded context's.

    ``id`` is ``None`` for an entry that has not yet been persisted.

    ``locator`` is where, within the document, the mention was found -
    not restricted to PDF pages (``IndexEntryLocator``). ``page`` is
    kept as a read-only, backward-compatible view over ``locator`` for
    the common PDF case.
    """

    id: int | None
    project_id: int
    document_id: int
    kind: EngineeringIndexEntryKind
    identifier: str
    locator: IndexEntryLocator
    label: str | None
    created_at: datetime

    @property
    def page(self) -> int | None:
        return self.locator.page

    @property
    def locator_kind(self) -> IndexEntryLocatorKind:
        return self.locator.kind

    @property
    def locator_value(self) -> str | None:
        return self.locator.value
