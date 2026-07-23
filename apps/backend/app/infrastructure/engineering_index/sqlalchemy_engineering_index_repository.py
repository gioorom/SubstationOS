from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    DuplicateIndexEntryError,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.models.engineering_index import (
    EngineeringIndexEntry as EngineeringIndexEntryRecord,
)


class SqlAlchemyEngineeringIndexRepository(EngineeringIndexRepository):
    """
    SQLAlchemy adapter for the ``EngineeringIndexRepository`` port,
    backed by ``app.models.engineering_index.EngineeringIndexEntry``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, entry: IndexEntry) -> IndexEntry:
        record = self._to_record(entry)

        self._session.add(record)

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()

            raise DuplicateIndexEntryError(
                entry.document_id,
                entry.kind,
                entry.identifier,
            ) from error

        self._session.refresh(record)

        return self._to_domain(record)

    def get_by_id(self, entry_id: int) -> IndexEntry | None:
        record = self._session.get(EngineeringIndexEntryRecord, entry_id)

        return self._to_domain(record) if record is not None else None

    def list_by_document(self, document_id: int) -> list[IndexEntry]:
        records = (
            self._session.query(EngineeringIndexEntryRecord)
            .filter(
                EngineeringIndexEntryRecord.document_id == document_id
            )
            .order_by(EngineeringIndexEntryRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def list_by_project(
        self,
        project_id: int,
        *,
        kind: EngineeringIndexEntryKind | None = None,
    ) -> list[IndexEntry]:
        query = self._session.query(EngineeringIndexEntryRecord).filter(
            EngineeringIndexEntryRecord.project_id == project_id
        )

        if kind is not None:
            query = query.filter(EngineeringIndexEntryRecord.kind == kind)

        records = query.order_by(
            EngineeringIndexEntryRecord.created_at.asc()
        ).all()

        return [self._to_domain(record) for record in records]

    def search_by_identifier(
        self,
        project_id: int,
        identifier: str,
    ) -> list[IndexEntry]:
        records = (
            self._session.query(EngineeringIndexEntryRecord)
            .filter(
                EngineeringIndexEntryRecord.project_id == project_id,
                EngineeringIndexEntryRecord.identifier.ilike(
                    f"%{identifier}%"
                ),
            )
            .order_by(EngineeringIndexEntryRecord.created_at.asc())
            .all()
        )

        return [self._to_domain(record) for record in records]

    def replace_for_document(
        self,
        document_id: int,
        project_id: int,
        entries: list[IndexEntry],
    ) -> list[IndexEntry]:
        self._session.query(EngineeringIndexEntryRecord).filter(
            EngineeringIndexEntryRecord.document_id == document_id
        ).delete(synchronize_session=False)

        records = [self._to_record(entry) for entry in entries]
        self._session.add_all(records)

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()

            raise DuplicateIndexEntryError(
                document_id,
                entries[0].kind,
                entries[0].identifier,
            ) from error

        for record in records:
            self._session.refresh(record)

        return [self._to_domain(record) for record in records]

    def delete_by_document(self, document_id: int) -> None:
        self._session.query(EngineeringIndexEntryRecord).filter(
            EngineeringIndexEntryRecord.document_id == document_id
        ).delete(synchronize_session=False)

        self._session.commit()

    @staticmethod
    def _to_record(entry: IndexEntry) -> EngineeringIndexEntryRecord:
        return EngineeringIndexEntryRecord(
            project_id=entry.project_id,
            document_id=entry.document_id,
            kind=entry.kind,
            identifier=entry.identifier,
            locator_kind=entry.locator.kind,
            locator_value=entry.locator.value,
            label=entry.label,
            created_at=entry.created_at,
        )

    @staticmethod
    def _to_domain(record: EngineeringIndexEntryRecord) -> IndexEntry:
        return IndexEntry(
            id=record.id,
            project_id=record.project_id,
            document_id=record.document_id,
            kind=record.kind,
            identifier=record.identifier,
            locator=IndexEntryLocator(
                kind=record.locator_kind,
                value=record.locator_value,
            ),
            label=record.label,
            created_at=record.created_at,
        )
