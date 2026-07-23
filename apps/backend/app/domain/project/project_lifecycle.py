from __future__ import annotations

from enum import Enum


class ProjectLifecycleState(str, Enum):
    """
    The record lifecycle of a Project, per Architecture Freeze v1.0
    (docs/architecture/project_intelligence_architecture.md).

    This is distinct from ``ProjectStatus`` (app/models/project.py), which
    tracks the real installation's delivery phase (planning, construction,
    energized, ...). The two are orthogonal: a Project record can be
    ``ACTIVE`` while its installation status is ``planning``, and a
    long-finished installation's record can still be ``ACTIVE`` in the
    system.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# The lifecycle is a strict linear chain in both directions:
# DRAFT -> ACTIVE -> ARCHIVED -> DELETED (forward)
# DELETED -> ARCHIVED -> ACTIVE (restore, one step at a time)
#
# Deleted is reachable only from Archived - a project is always archived
# before it is deleted, never deleted directly from Draft or Active.
VALID_TRANSITIONS: dict[
    ProjectLifecycleState, frozenset[ProjectLifecycleState]
] = {
    ProjectLifecycleState.DRAFT: frozenset(
        {ProjectLifecycleState.ACTIVE}
    ),
    ProjectLifecycleState.ACTIVE: frozenset(
        {ProjectLifecycleState.ARCHIVED}
    ),
    ProjectLifecycleState.ARCHIVED: frozenset(
        {
            ProjectLifecycleState.ACTIVE,
            ProjectLifecycleState.DELETED,
        }
    ),
    ProjectLifecycleState.DELETED: frozenset(
        {ProjectLifecycleState.ARCHIVED}
    ),
}

# States in which a Project accepts new or changed content: metadata
# updates, and new document uploads. Archived and Deleted are read-only,
# per Architecture Freeze v1.0's validation rules.
MUTABLE_STATES: frozenset[ProjectLifecycleState] = frozenset(
    {
        ProjectLifecycleState.DRAFT,
        ProjectLifecycleState.ACTIVE,
    }
)


def is_transition_valid(
    current: ProjectLifecycleState,
    target: ProjectLifecycleState,
) -> bool:
    return target in VALID_TRANSITIONS[current]
