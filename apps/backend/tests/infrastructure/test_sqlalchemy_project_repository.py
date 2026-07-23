from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def test_save_persists_a_new_project_and_assigns_an_id(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)
    project = ProjectFactory.create(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
        created_at=CREATED_AT,
    )

    saved = repository.save(project)

    assert saved.id is not None
    assert saved.name == "Alpha Substation"
    assert saved.lifecycle_state is ProjectLifecycleState.DRAFT


def test_get_by_id_returns_none_for_a_missing_project(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)

    assert repository.get_by_id(999) is None


def test_get_by_id_returns_the_persisted_project(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)
    saved = repository.save(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )

    found = repository.get_by_id(saved.id)  # type: ignore[arg-type]

    assert found is not None
    assert found.code == "ALPHA-001"


def test_get_by_code_returns_the_persisted_project(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)
    repository.save(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )

    found = repository.get_by_code("ALPHA-001")

    assert found is not None
    assert found.name == "Alpha Substation"


def test_get_by_code_returns_none_for_an_unknown_code(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)

    assert repository.get_by_code("UNKNOWN") is None


def test_save_updates_an_existing_project(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)
    saved = repository.save(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )

    activated = repository.save(
        saved.activate(now=datetime(2026, 1, 2, 9, 0, 0))
    )

    assert activated.id == saved.id
    assert activated.lifecycle_state is ProjectLifecycleState.ACTIVE

    reloaded = repository.get_by_id(saved.id)  # type: ignore[arg-type]
    assert reloaded is not None
    assert reloaded.lifecycle_state is ProjectLifecycleState.ACTIVE


def test_list_all_excludes_deleted_projects_by_default(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)

    active_project = repository.save(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )

    deleted_project = repository.save(
        ProjectFactory.create(
            name="Beta Substation",
            code="BETA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )
    deleted_project = repository.save(
        deleted_project.activate(now=CREATED_AT).archive(now=CREATED_AT)
    )
    repository.save(deleted_project.mark_deleted(now=CREATED_AT))

    codes = {project.code for project in repository.list_all()}

    assert active_project.code in codes
    assert "BETA-001" not in codes


def test_list_all_includes_deleted_projects_when_requested(
    db_session: Session,
) -> None:
    repository = SqlAlchemyProjectRepository(db_session)

    project = repository.save(
        ProjectFactory.create(
            name="Beta Substation",
            code="BETA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        )
    )
    project = repository.save(
        project.activate(now=CREATED_AT).archive(now=CREATED_AT)
    )
    repository.save(project.mark_deleted(now=CREATED_AT))

    codes = {
        project.code
        for project in repository.list_all(include_deleted=True)
    }

    assert "BETA-001" in codes
