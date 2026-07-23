from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.project.project_exceptions import (
    InvalidProjectTransitionError,
)
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import (
    UNVERSIONED_CANONICAL_DOMAIN,
    Project,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _draft_project(**overrides: object) -> Project:
    fields: dict[str, object] = {
        "id": 1,
        "name": "Alpha Substation",
        "code": "ALPHA-001",
        "customer": "Acme Utilities",
        "epc": None,
        "country": None,
        "location": None,
        "description": None,
        "lifecycle_state": ProjectLifecycleState.DRAFT,
        "canonical_domain_version": UNVERSIONED_CANONICAL_DOMAIN,
        "created_by": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    fields.update(overrides)

    return Project(**fields)  # type: ignore[arg-type]


def test_traceability_reference_is_the_project_code() -> None:
    project = _draft_project(code="ALPHA-001")

    assert project.traceability_reference == "ALPHA-001"


def test_draft_project_is_mutable() -> None:
    assert _draft_project().is_mutable()


def test_activate_moves_draft_to_active_and_updates_timestamp() -> None:
    project = _draft_project()
    now = datetime(2026, 1, 2, 9, 0, 0)

    activated = project.activate(now=now)

    assert activated.lifecycle_state is ProjectLifecycleState.ACTIVE
    assert activated.updated_at == now
    # The original instance is untouched - Project is immutable.
    assert project.lifecycle_state is ProjectLifecycleState.DRAFT


def test_archive_sets_archived_at_and_becomes_immutable() -> None:
    project = _draft_project().activate(now=CREATED_AT)
    now = datetime(2026, 1, 3, 9, 0, 0)

    archived = project.archive(now=now)

    assert archived.lifecycle_state is ProjectLifecycleState.ARCHIVED
    assert archived.archived_at == now
    assert not archived.is_mutable()


def test_restore_from_archived_returns_to_active_and_clears_archived_at() -> (
    None
):
    project = (
        _draft_project()
        .activate(now=CREATED_AT)
        .archive(now=CREATED_AT)
    )
    now = datetime(2026, 1, 4, 9, 0, 0)

    restored = project.restore(now=now)

    assert restored.lifecycle_state is ProjectLifecycleState.ACTIVE
    assert restored.archived_at is None
    assert restored.is_mutable()


def test_mark_deleted_requires_archived_state_and_sets_deleted_at() -> None:
    project = (
        _draft_project()
        .activate(now=CREATED_AT)
        .archive(now=CREATED_AT)
    )
    now = datetime(2026, 1, 5, 9, 0, 0)

    deleted = project.mark_deleted(now=now)

    assert deleted.lifecycle_state is ProjectLifecycleState.DELETED
    assert deleted.deleted_at == now
    assert not deleted.is_mutable()


def test_restore_from_deleted_returns_to_archived_and_clears_deleted_at() -> (
    None
):
    project = (
        _draft_project()
        .activate(now=CREATED_AT)
        .archive(now=CREATED_AT)
        .mark_deleted(now=CREATED_AT)
    )
    now = datetime(2026, 1, 6, 9, 0, 0)

    restored = project.restore(now=now)

    assert restored.lifecycle_state is ProjectLifecycleState.ARCHIVED
    assert restored.deleted_at is None


def test_activating_an_already_active_project_raises() -> None:
    project = _draft_project().activate(now=CREATED_AT)

    with pytest.raises(InvalidProjectTransitionError):
        project.activate(now=CREATED_AT)


def test_deleting_a_draft_project_directly_raises() -> None:
    with pytest.raises(InvalidProjectTransitionError):
        _draft_project().mark_deleted(now=CREATED_AT)


def test_deleting_an_active_project_directly_raises() -> None:
    project = _draft_project().activate(now=CREATED_AT)

    with pytest.raises(InvalidProjectTransitionError):
        project.mark_deleted(now=CREATED_AT)


def test_restoring_an_active_project_raises() -> None:
    project = _draft_project().activate(now=CREATED_AT)

    with pytest.raises(InvalidProjectTransitionError):
        project.restore(now=CREATED_AT)


def test_with_metadata_updates_only_given_fields() -> None:
    project = _draft_project(
        name="Alpha Substation",
        customer="Acme Utilities",
        location="Milan",
    )
    now = datetime(2026, 1, 7, 9, 0, 0)

    updated = project.with_metadata(
        now=now,
        location="Turin",
    )

    assert updated.name == "Alpha Substation"
    assert updated.customer == "Acme Utilities"
    assert updated.location == "Turin"
    assert updated.updated_at == now


def test_with_metadata_does_not_accept_code_changes() -> None:
    """
    ``with_metadata`` has no ``code`` parameter at all - a project's
    code is immutable once created (CLAUDE.md §16).
    """

    assert "code" not in Project.with_metadata.__annotations__
