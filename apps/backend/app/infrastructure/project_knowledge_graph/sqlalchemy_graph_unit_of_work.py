from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.project_knowledge_graph.graph_unit_of_work import (
    GraphUnitOfWork,
)


class SqlAlchemyGraphUnitOfWork(GraphUnitOfWork):
    """
    SQLAlchemy adapter for the ``GraphUnitOfWork`` port - a thin wrapper
    around the same ``Session`` the ``SqlAlchemyGraphStore`` and
    ``SqlAlchemyGraphExecutionRepository`` passed to one
    ``execute_batch`` call also use, so commit/rollback here applies to
    every mutation they made.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
