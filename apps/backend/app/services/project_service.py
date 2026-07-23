"""
Application services for the Project Lifecycle, per Architecture Freeze
v1.0. Each function is a single use case, orchestrating the domain
(``app.domain.project``) through the ``ProjectRepository`` port - never a
raw database session. Deliberately independent from any AI, extraction,
or indexing concern: those are future services layered on top, not
mixed into this one.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.project.project_exceptions import (
    DuplicateProjectCodeError,
    ProjectNotFoundError,
    ProjectNotMutableError,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_models import (
    UNVERSIONED_CANONICAL_DOMAIN,
    Project,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.project.project_validator import ProjectValidator


def _require_project(
    repository: ProjectRepository,
    project_id: int,
) -> Project:
    project = repository.get_by_id(project_id)

    if project is None:
        raise ProjectNotFoundError(project_id)

    return project


def create_project(
    repository: ProjectRepository,
    *,
    name: str,
    code: str,
    customer: str,
    now: datetime,
    epc: str | None = None,
    country: str | None = None,
    location: str | None = None,
    description: str | None = None,
    canonical_domain_version: str = UNVERSIONED_CANONICAL_DOMAIN,
    created_by: str | None = None,
) -> Project:
    """
    Creates a new Project in the Draft state.

    Per Architecture Freeze v1.0, creation provisions the Project itself
    and the scope for its Document Repository, Engineering Index,
    Project Knowledge Graph, and Traceability context - nothing else.
    No extraction, no indexing, no AI, and no background jobs are
    triggered here; those scopes exist only as this Project's identity
    for later milestones to populate.
    """

    if repository.get_by_code(code) is not None:
        raise DuplicateProjectCodeError(code)

    project = ProjectFactory.create(
        name=name,
        code=code,
        customer=customer,
        created_at=now,
        epc=epc,
        country=country,
        location=location,
        description=description,
        canonical_domain_version=canonical_domain_version,
        created_by=created_by,
    )

    return repository.save(project)


def activate_project(
    repository: ProjectRepository,
    project_id: int,
    *,
    now: datetime,
) -> Project:
    project = _require_project(repository, project_id)

    return repository.save(project.activate(now=now))


def archive_project(
    repository: ProjectRepository,
    project_id: int,
    *,
    now: datetime,
) -> Project:
    project = _require_project(repository, project_id)

    return repository.save(project.archive(now=now))


def restore_project(
    repository: ProjectRepository,
    project_id: int,
    *,
    now: datetime,
) -> Project:
    """
    Undoes exactly one step of the lifecycle: Deleted -> Archived, or
    Archived -> Active. See ``Project.restore``.
    """

    project = _require_project(repository, project_id)

    return repository.save(project.restore(now=now))


def delete_project(
    repository: ProjectRepository,
    project_id: int,
    *,
    now: datetime,
) -> Project:
    """
    Soft deletes a Project. Never issues a hard delete - the Project
    record, and every document, index entry, and graph node that
    references it, remain in place for audit and eventual restore.
    """

    project = _require_project(repository, project_id)

    return repository.save(project.mark_deleted(now=now))


def update_project_metadata(
    repository: ProjectRepository,
    project_id: int,
    *,
    now: datetime,
    name: str | None = None,
    customer: str | None = None,
    epc: str | None = None,
    country: str | None = None,
    location: str | None = None,
    description: str | None = None,
) -> Project:
    """
    Updates descriptive metadata on a mutable (Draft or Active) Project.
    Raises ``ProjectNotMutableError`` for an Archived or Deleted
    Project - both are read-only. The project code is never accepted
    here: it is immutable once published (CLAUDE.md §16).
    """

    project = _require_project(repository, project_id)

    if not project.is_mutable():
        raise ProjectNotMutableError(
            project.code,
            project.lifecycle_state,
        )

    if name is not None:
        ProjectValidator.validate_name(name)

    updated = project.with_metadata(
        now=now,
        name=name,
        customer=customer,
        epc=epc,
        country=country,
        location=location,
        description=description,
    )

    return repository.save(updated)


def get_project(
    repository: ProjectRepository,
    project_id: int,
) -> Project:
    return _require_project(repository, project_id)


def list_projects(
    repository: ProjectRepository,
    *,
    include_deleted: bool = False,
) -> list[Project]:
    return repository.list_all(include_deleted=include_deleted)
