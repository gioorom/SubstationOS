from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.project.project_models import Project


class ProjectRepository(ABC):
    """
    Port for loading and persisting ``Project`` aggregates. The domain
    depends only on this contract; an infrastructure adapter
    (e.g. ``SqlAlchemyProjectRepository``) provides the implementation.
    """

    @abstractmethod
    def get_by_id(self, project_id: int) -> Project | None:
        """Return the project with this id, or ``None`` if none exists."""

        raise NotImplementedError

    @abstractmethod
    def get_by_code(self, code: str) -> Project | None:
        """Return the project with this code, or ``None`` if none exists."""

        raise NotImplementedError

    @abstractmethod
    def save(self, project: Project) -> Project:
        """
        Insert a new project (when ``project.id`` is ``None``) or update
        an existing one, and return the persisted aggregate (with ``id``
        populated on insert).
        """

        raise NotImplementedError

    @abstractmethod
    def list_all(self, *, include_deleted: bool = False) -> list[Project]:
        """
        Return every project, ordered by creation time descending. Soft
        deleted projects are excluded unless ``include_deleted`` is
        ``True``.
        """

        raise NotImplementedError
