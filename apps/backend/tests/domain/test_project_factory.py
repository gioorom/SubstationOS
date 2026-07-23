from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.project.project_exceptions import (
    InvalidProjectCodeError,
    InvalidProjectNameError,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import UNVERSIONED_CANONICAL_DOMAIN

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def test_create_builds_a_project_in_draft_state() -> None:
    project = ProjectFactory.create(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        created_at=CREATED_AT,
    )

    assert project.id is None
    assert project.lifecycle_state is ProjectLifecycleState.DRAFT
    assert project.created_at == CREATED_AT
    assert project.updated_at == CREATED_AT
    assert project.archived_at is None
    assert project.deleted_at is None


def test_create_defaults_canonical_domain_version_to_unversioned() -> None:
    project = ProjectFactory.create(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        created_at=CREATED_AT,
    )

    assert (
        project.canonical_domain_version == UNVERSIONED_CANONICAL_DOMAIN
    )


def test_create_accepts_an_explicit_canonical_domain_version() -> None:
    project = ProjectFactory.create(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        created_at=CREATED_AT,
        canonical_domain_version="2026.1",
    )

    assert project.canonical_domain_version == "2026.1"


def test_create_rejects_a_blank_name() -> None:
    with pytest.raises(InvalidProjectNameError):
        ProjectFactory.create(
            name="   ",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )


def test_create_rejects_a_blank_code() -> None:
    with pytest.raises(InvalidProjectCodeError):
        ProjectFactory.create(
            name="Alpha Substation",
            code="",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
