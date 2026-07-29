from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.project.project_exceptions import (
    DuplicateProjectCodeError,
    InvalidProjectTransitionError,
    ProjectNotFoundError,
    ProjectNotMutableError,
)
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.services import project_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


class FakeProjectRepository(ProjectRepository):
    """
    In-memory ``ProjectRepository`` for service-layer tests. No database,
    no I/O - keeps these tests fast and deterministic.
    """

    def __init__(self) -> None:
        self._projects: dict[int, Project] = {}
        self._next_id = 1

    def get_by_id(self, project_id: int) -> Project | None:
        return self._projects.get(project_id)

    def get_by_code(self, code: str) -> Project | None:
        for project in self._projects.values():
            if project.code == code:
                return project

        return None

    def save(self, project: Project) -> Project:
        if project.id is None:
            project = _with_id(project, self._next_id)
            self._next_id += 1

        self._projects[project.id] = project  # type: ignore[index]

        return project

    def list_all(self, *, include_deleted: bool = False) -> list[Project]:
        projects = list(self._projects.values())

        if not include_deleted:
            projects = [
                project
                for project in projects
                if project.lifecycle_state
                is not ProjectLifecycleState.DELETED
            ]

        return sorted(
            projects,
            key=lambda project: project.created_at,
            reverse=True,
        )

    def list_page(self, query):
        """
        In-memory paging. Legitimate here precisely because it is a fake:
        the SQLAlchemy adapter must page in the database, and an
        architecture test holds it to that.
        """

        from app.domain.shared_kernel.pagination import Page

        projects = self.list_all(include_deleted=query.include_deleted)

        if query.lifecycle_state is not None:
            projects = [
                project
                for project in projects
                if project.lifecycle_state is query.lifecycle_state
            ]

        if query.status is not None:
            projects = [
                project
                for project in projects
                if project.status is query.status
            ]

        if query.search is not None:
            needle = query.search.value.lower()

            projects = [
                project
                for project in projects
                if needle in project.name.lower()
                or needle in project.code.lower()
                or needle in project.customer.lower()
                or needle in (project.location or "").lower()
            ]

        start = query.page.offset

        return Page.of(
            tuple(projects[start : start + query.page.limit]),
            total=len(projects),
            request=query.page,
        )



def _with_id(project: Project, project_id: int) -> Project:
    return replace(project, id=project_id)


@pytest.fixture()
def repository() -> FakeProjectRepository:
    return FakeProjectRepository()


def test_create_project_persists_a_draft_project(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )

    assert project.id is not None
    assert project.lifecycle_state is ProjectLifecycleState.DRAFT


def test_create_project_rejects_a_duplicate_code(
    repository: FakeProjectRepository,
) -> None:
    project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )

    with pytest.raises(DuplicateProjectCodeError):
        project_service.create_project(
            repository,
            name="Alpha Substation Two",
            code="ALPHA-001",
            customer="Acme Utilities",
            now=CREATED_AT,
        )


def test_activate_project_moves_draft_to_active(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )

    activated = project_service.activate_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=datetime(2026, 1, 2, 9, 0, 0),
    )

    assert activated.lifecycle_state is ProjectLifecycleState.ACTIVE


def test_activate_project_raises_for_unknown_project(
    repository: FakeProjectRepository,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        project_service.activate_project(
            repository,
            999,
            now=CREATED_AT,
        )


def test_archive_then_delete_project(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )
    project_service.activate_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    project_service.archive_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    deleted = project_service.delete_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    assert deleted.lifecycle_state is ProjectLifecycleState.DELETED


def test_delete_project_directly_from_draft_raises(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )

    with pytest.raises(InvalidProjectTransitionError):
        project_service.delete_project(
            repository,
            project.id,  # type: ignore[arg-type]
            now=CREATED_AT,
        )


def test_restore_project_undoes_one_step(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )
    project_service.activate_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    project_service.archive_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    restored = project_service.restore_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    assert restored.lifecycle_state is ProjectLifecycleState.ACTIVE


def test_update_metadata_on_a_draft_project_succeeds(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )

    updated = project_service.update_project_metadata(
        repository,
        project.id,  # type: ignore[arg-type]
        now=datetime(2026, 1, 2, 9, 0, 0),
        location="Turin",
    )

    assert updated.location == "Turin"


def test_update_metadata_on_an_archived_project_raises(
    repository: FakeProjectRepository,
) -> None:
    project = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )
    project_service.activate_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    project_service.archive_project(
        repository,
        project.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    with pytest.raises(ProjectNotMutableError):
        project_service.update_project_metadata(
            repository,
            project.id,  # type: ignore[arg-type]
            now=CREATED_AT,
            location="Turin",
        )


def test_get_project_raises_for_unknown_project(
    repository: FakeProjectRepository,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        project_service.get_project(repository, 999)


def test_list_projects_excludes_deleted_by_default(
    repository: FakeProjectRepository,
) -> None:
    kept = project_service.create_project(
        repository,
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )
    removed = project_service.create_project(
        repository,
        name="Beta Substation",
        code="BETA-001",
        customer="Acme Utilities",
        now=CREATED_AT,
    )
    project_service.activate_project(
        repository,
        removed.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    project_service.archive_project(
        repository,
        removed.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    project_service.delete_project(
        repository,
        removed.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )

    codes = {
        project.code
        for project in project_service.list_projects(repository)
    }

    assert kept.code in codes
    assert removed.code not in codes
