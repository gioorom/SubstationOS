from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_query import (
    ProjectQuery,
    ProjectSortField,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.project.project_status import ProjectStatus
from app.domain.shared_kernel.pagination import Page, SortDirection
from app.models.project import Project as ProjectRecord
from app.models.project import ProjectStatus as StoredStatus

#: The one place a governed sort field becomes a column. A closed table
#: keyed by enum member: nowhere in this codebase does a caller-supplied
#: string reach a column name, and an architecture test asserts it.
_SORT_COLUMNS = {
    ProjectSortField.CREATED_AT: ProjectRecord.created_at,
    ProjectSortField.UPDATED_AT: ProjectRecord.updated_at,
    ProjectSortField.NAME: ProjectRecord.name,
    ProjectSortField.CODE: ProjectRecord.code,
}

#: The fields ``ProjectSearchTerm`` documents itself as searching. Stated
#: once, here, so the documentation and the query cannot disagree.
_SEARCHED_COLUMNS = (
    ProjectRecord.name,
    ProjectRecord.code,
    ProjectRecord.customer,
    ProjectRecord.location,
)


def _escape_like(value: str) -> str:
    r"""Escape the SQL ``LIKE`` wildcards so a literal ``%`` or ``_`` in a
    search term matches itself. ``\`` is escaped first, or it would
    double-escape the escapes that follow."""

    return (
        value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )


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

    def list_page(self, query: ProjectQuery) -> Page[Project]:
        filtered = self._apply_filters(
            self._session.query(ProjectRecord), query
        )

        # Counted by the database over the filtered set, never by
        # measuring a list that was loaded first.
        total = filtered.with_entities(
            func.count(ProjectRecord.id)
        ).scalar()

        records = (
            self._apply_order(filtered, query)
            .offset(query.page.offset)
            .limit(query.page.limit)
            .all()
        )

        return Page.of(
            tuple(self._to_domain(record) for record in records),
            total=total or 0,
            request=query.page,
        )

    @staticmethod
    def _apply_filters(
        statement: "Query[ProjectRecord]", query: ProjectQuery
    ) -> "Query[ProjectRecord]":
        if not query.include_deleted:
            statement = statement.filter(
                ProjectRecord.lifecycle_state
                != ProjectLifecycleState.DELETED
            )

        if query.lifecycle_state is not None:
            statement = statement.filter(
                ProjectRecord.lifecycle_state == query.lifecycle_state
            )

        if query.status is not None:
            statement = statement.filter(
                ProjectRecord.status == query.status.value
            )

        if query.search is not None:
            # The term is bound as a parameter: search text is data, never
            # a fragment of a statement. `%` and `_` inside it are escaped
            # so a search for "100%" means "100%" and not "everything".
            pattern = f"%{_escape_like(query.search.value)}%"

            statement = statement.filter(
                or_(
                    *(
                        column.ilike(pattern, escape="\\")
                        for column in _SEARCHED_COLUMNS
                    )
                )
            )

        return statement

    @staticmethod
    def _apply_order(
        statement: "Query[ProjectRecord]", query: ProjectQuery
    ) -> "Query[ProjectRecord]":
        column = _SORT_COLUMNS[query.sort_by]

        ordered = (
            column.asc()
            if query.direction is SortDirection.ASCENDING
            else column.desc()
        )

        # `id` breaks ties, so two projects created in the same second
        # never swap places between two reads. Without it, paging over a
        # non-unique sort key can show one row twice and skip another.
        return statement.order_by(ordered, ProjectRecord.id.asc())

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
        # Stored as the ORM enum, so a read is always typed and no
        # attribute has to be resolved by name on the way back.
        record.status = StoredStatus(project.status.value)
        record.voltage_level = project.voltage_level

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
            status=ProjectStatus(record.status.value),
            voltage_level=record.voltage_level,
        )
