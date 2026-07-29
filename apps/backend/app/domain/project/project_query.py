"""
The governed query vocabulary for the project registry.

Same discipline as ``app.domain.document_registry.document_query``: every
filter and sort field is a closed enum member or a typed value object,
and no column name ever travels from a caller into a query.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_status import ProjectStatus
from app.domain.shared_kernel.pagination import (
    PageRequest,
    SortDirection,
)


class ProjectSortField(str, Enum):
    """The fields a project list may be ordered by."""

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    NAME = "name"
    CODE = "code"


DEFAULT_PROJECT_SORT = ProjectSortField.CREATED_AT
DEFAULT_PROJECT_DIRECTION = SortDirection.DESCENDING


@dataclass(frozen=True, slots=True)
class ProjectSearchTerm:
    """
    A free-text search over a **documented, closed** set of fields:
    ``name``, ``code``, ``customer`` and ``location``.

    Matching follows the same rule as the document registry's -
    case-insensitive, partial, trimmed at the ends, internal whitespace
    preserved - because two search boxes in one product that behave
    differently is a defect, whatever each of them does.

    ``description`` is deliberately excluded. It is long free prose, and
    including it would make a search for "CP-01" match every project
    whose description mentions one.
    """

    value: str

    @classmethod
    def of(cls, raw: str | None) -> "ProjectSearchTerm | None":
        if raw is None:
            return None

        trimmed = raw.strip()

        return cls(trimmed) if trimmed else None


@dataclass(frozen=True, slots=True)
class ProjectQuery:
    """
    One governed request for a page of the project registry.

    ``lifecycle_state`` and ``status`` are separate filters on purpose:
    "show me archived projects" and "show me energized projects" are
    different questions, and a caller may legitimately ask both at once.

    ``include_deleted`` is not a lifecycle filter, it is a **visibility**
    decision: soft-deleted projects are hidden from every list unless
    asked for explicitly, and asking for ``lifecycle_state=deleted``
    without it returns nothing rather than silently overriding the
    default.
    """

    page: PageRequest
    status: ProjectStatus | None = None
    lifecycle_state: ProjectLifecycleState | None = None
    search: ProjectSearchTerm | None = None
    include_deleted: bool = False
    sort_by: ProjectSortField = DEFAULT_PROJECT_SORT
    direction: SortDirection = DEFAULT_PROJECT_DIRECTION
