from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.engineering_index.document_lookup import (
    DocumentIndexContext,
    DocumentLookupPort,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord


class SqlAlchemyDocumentLookup(DocumentLookupPort):
    """
    SQLAlchemy adapter for the ``DocumentLookupPort``, reading the
    existing ``Document``/``Project`` persistence models. No new
    Document domain bounded context is introduced by this adapter - it
    reads exactly the two fields (``Document.scope``,
    ``Project.lifecycle_state``) the Engineering Index needs.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def find(self, document_id: int) -> DocumentIndexContext | None:
        document = self._session.get(DocumentRecord, document_id)

        if document is None:
            return None

        project = (
            self._session.get(ProjectRecord, document.project_id)
            if document.project_id is not None
            else None
        )

        return DocumentIndexContext(
            document_id=document.id,
            project_id=project.id if project is not None else None,
            scope=document.scope,
            project_lifecycle_state=(
                project.lifecycle_state if project is not None else None
            ),
        )
