from __future__ import annotations

import pytest

from app.domain.project.project_lifecycle import (
    MUTABLE_STATES,
    ProjectLifecycleState,
    is_transition_valid,
)


def test_draft_can_transition_to_active() -> None:
    assert is_transition_valid(
        ProjectLifecycleState.DRAFT,
        ProjectLifecycleState.ACTIVE,
    )


def test_active_can_transition_to_archived() -> None:
    assert is_transition_valid(
        ProjectLifecycleState.ACTIVE,
        ProjectLifecycleState.ARCHIVED,
    )


def test_archived_can_transition_to_deleted() -> None:
    assert is_transition_valid(
        ProjectLifecycleState.ARCHIVED,
        ProjectLifecycleState.DELETED,
    )


def test_archived_can_transition_back_to_active() -> None:
    assert is_transition_valid(
        ProjectLifecycleState.ARCHIVED,
        ProjectLifecycleState.ACTIVE,
    )


def test_deleted_can_transition_back_to_archived() -> None:
    assert is_transition_valid(
        ProjectLifecycleState.DELETED,
        ProjectLifecycleState.ARCHIVED,
    )


def test_draft_cannot_transition_directly_to_archived() -> None:
    assert not is_transition_valid(
        ProjectLifecycleState.DRAFT,
        ProjectLifecycleState.ARCHIVED,
    )


def test_draft_cannot_transition_directly_to_deleted() -> None:
    assert not is_transition_valid(
        ProjectLifecycleState.DRAFT,
        ProjectLifecycleState.DELETED,
    )


def test_active_cannot_transition_directly_to_deleted() -> None:
    """
    A project must always be archived before it is deleted - deletion
    is only reachable one step at a time, never skipped directly from
    Active.
    """

    assert not is_transition_valid(
        ProjectLifecycleState.ACTIVE,
        ProjectLifecycleState.DELETED,
    )


def test_deleted_cannot_transition_directly_to_active() -> None:
    """
    Restoring a deleted project is a two-step, independently auditable
    process (Deleted -> Archived, then Archived -> Active), never a
    single jump.
    """

    assert not is_transition_valid(
        ProjectLifecycleState.DELETED,
        ProjectLifecycleState.ACTIVE,
    )


def test_deleted_has_no_forward_transition() -> None:
    assert not is_transition_valid(
        ProjectLifecycleState.DELETED,
        ProjectLifecycleState.DELETED,
    )


@pytest.mark.parametrize(
    "state",
    [
        ProjectLifecycleState.DRAFT,
        ProjectLifecycleState.ACTIVE,
    ],
)
def test_draft_and_active_are_mutable(
    state: ProjectLifecycleState,
) -> None:
    assert state in MUTABLE_STATES


@pytest.mark.parametrize(
    "state",
    [
        ProjectLifecycleState.ARCHIVED,
        ProjectLifecycleState.DELETED,
    ],
)
def test_archived_and_deleted_are_not_mutable(
    state: ProjectLifecycleState,
) -> None:
    assert state not in MUTABLE_STATES
