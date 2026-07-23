from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.models.project import Project as ProjectRecord


class SqlAlchemyProjectRepository(ProjectRepository):
    """
    SQLAlchemy adapter for the ``ProjectRepository`` port, backed by the
    existing ``app.models.project.Project`` ORM mapping.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, project_id: int) -> Project | None:
        record = self._session.get(ProjectRecord, project_id)

        return self._to_domain(record) if record is not None else None

    def get_by_code(self, code: str) -> Project | None:
        record = (
            self._session.query(ProjectRecord)
            .filter(ProjectRecord.code == code)
            .first()
        )

        return self._to_domain(record) if record is not None else None

    def save(self, project: Project) -> Project:
        if project.id is None:
            record = ProjectRecord()
        else:
            record = self._session.get(ProjectRecord, project.id)

            if record is None:
                record = ProjectRecord()

        self._apply_to_record(project, record)

        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)

        return self._to_domain(record)

    def list_all(self, *, include_deleted: bool = False) -> list[Project]:
        query = self._session.query(ProjectRecord)

        if not include_deleted:
            query = query.filter(
                ProjectRecord.lifecycle_state
                != ProjectLifecycleState.DELETED
            )

        records = query.order_by(ProjectRecord.created_at.desc()).all()

        return [self._to_domain(record) for record in records]

    @staticmethod
    def _apply_to_record(
        project: Project,
        record: ProjectRecord,
    ) -> None:
        record.name = project.name
        record.code = project.code
        record.customer = project.customer
        record.epc = project.epc
        record.country = project.country
        record.location = project.location
        record.description = project.description
        record.lifecycle_state = project.lifecycle_state
        record.canonical_domain_version = project.canonical_domain_version
        record.created_by = project.created_by
        record.created_at = project.created_at
        record.updated_at = project.updated_at
        record.archived_at = project.archived_at
        record.deleted_at = project.deleted_at

    @staticmethod
    def _to_domain(record: ProjectRecord) -> Project:
        return Project(
            id=record.id,
            name=record.name,
            code=record.code,
            customer=record.customer,
            epc=record.epc,
            country=record.country,
            location=record.location,
            description=record.description,
            lifecycle_state=record.lifecycle_state,
            canonical_domain_version=record.canonical_domain_version,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            archived_at=record.archived_at,
            deleted_at=record.deleted_at,
        )
