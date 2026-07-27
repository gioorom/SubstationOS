"""
The Engineering Session state machine - the same "explicit transition
table plus a pure membership check" convention
``app.domain.project.project_lifecycle`` already established for
``ProjectLifecycleState``.
"""

from __future__ import annotations

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionStatus,
)

# CREATED -> ACTIVE -> {PAUSED, COMPLETED}
# PAUSED -> {ACTIVE, COMPLETED, ARCHIVED}
# COMPLETED -> ARCHIVED
# ARCHIVED is terminal - no transition leaves it.
VALID_TRANSITIONS: dict[
    EngineeringSessionStatus, frozenset[EngineeringSessionStatus]
] = {
    EngineeringSessionStatus.CREATED: frozenset(
        {EngineeringSessionStatus.ACTIVE}
    ),
    EngineeringSessionStatus.ACTIVE: frozenset(
        {
            EngineeringSessionStatus.PAUSED,
            EngineeringSessionStatus.COMPLETED,
        }
    ),
    EngineeringSessionStatus.PAUSED: frozenset(
        {
            EngineeringSessionStatus.ACTIVE,
            EngineeringSessionStatus.COMPLETED,
            EngineeringSessionStatus.ARCHIVED,
        }
    ),
    EngineeringSessionStatus.COMPLETED: frozenset(
        {EngineeringSessionStatus.ARCHIVED}
    ),
    EngineeringSessionStatus.ARCHIVED: frozenset(),
}

# States in which a session accepts new EngineeringResponses and
# configuration updates. COMPLETED and ARCHIVED are read-only, the same
# "terminal states are immutable" discipline
# ``app.domain.project.project_lifecycle.MUTABLE_STATES`` already
# established.
MUTABLE_STATUSES: frozenset[EngineeringSessionStatus] = frozenset(
    {
        EngineeringSessionStatus.CREATED,
        EngineeringSessionStatus.ACTIVE,
        EngineeringSessionStatus.PAUSED,
    }
)


def is_transition_valid(
    current: EngineeringSessionStatus,
    target: EngineeringSessionStatus,
) -> bool:
    return target in VALID_TRANSITIONS[current]
