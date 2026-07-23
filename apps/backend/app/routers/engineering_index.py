from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    DocumentNotIndexableError,
    DuplicateIndexEntryError,
    IndexedDocumentNotFoundError,
    IndexEntryNotFoundError,
    InvalidIndexEntryIdentifierError,
    InvalidIndexEntryLocatorError,
    InvalidIndexEntryPageError,
    ProjectNotIndexableError,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
)
from app.infrastructure.engineering_index.sqlalchemy_document_lookup import (
    SqlAlchemyDocumentLookup,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.schemas.engineering_index import (
    EngineeringIndexDocumentIndexReplace,
    EngineeringIndexEntriesBulkCreate,
    EngineeringIndexEntryCreate,
    EngineeringIndexEntryRead,
)
from app.services import engineering_index_service


_INVALID_ENTRY_ERRORS = (
    InvalidIndexEntryIdentifierError,
    InvalidIndexEntryPageError,
    InvalidIndexEntryLocatorError,
)


router = APIRouter(
    tags=["Engineering Index"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/engineering-index/entries",
    response_model=EngineeringIndexEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_index_entry(
    payload: EngineeringIndexEntryCreate,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)
    document_lookup = SqlAlchemyDocumentLookup(db)

    locator = (
        IndexEntryLocator(
            kind=payload.locator_kind,
            value=payload.locator_value,
        )
        if payload.locator_kind is not None
        else None
    )

    try:
        entry = engineering_index_service.register_index_entry(
            repository,
            document_lookup,
            document_id=payload.document_id,
            kind=payload.kind,
            identifier=payload.identifier,
            now=datetime.utcnow(),
            page=payload.page,
            locator=locator,
            label=payload.label,
        )
    except IndexedDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except _INVALID_ENTRY_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DuplicateIndexEntryError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return entry


@router.post(
    "/engineering-index/entries/bulk",
    response_model=list[EngineeringIndexEntryRead],
    status_code=status.HTTP_201_CREATED,
)
def create_index_entries_bulk(
    payload: EngineeringIndexEntriesBulkCreate,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)
    document_lookup = SqlAlchemyDocumentLookup(db)

    try:
        entries = engineering_index_service.register_index_entries(
            repository,
            document_lookup,
            document_id=payload.document_id,
            mentions=[
                mention.model_dump() for mention in payload.mentions
            ],
            now=datetime.utcnow(),
        )
    except IndexedDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except _INVALID_ENTRY_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DuplicateIndexEntryError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return entries


@router.get(
    "/engineering-index/entries/{entry_id}",
    response_model=EngineeringIndexEntryRead,
)
def get_index_entry(
    entry_id: int,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)

    try:
        return engineering_index_service.get_index_entry(
            repository,
            entry_id,
        )
    except IndexEntryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/documents/{document_id}/engineering-index",
    response_model=list[EngineeringIndexEntryRead],
)
def list_index_entries_for_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)

    return engineering_index_service.list_index_entries_for_document(
        repository,
        document_id,
    )


@router.put(
    "/documents/{document_id}/engineering-index",
    response_model=list[EngineeringIndexEntryRead],
)
def replace_document_index(
    document_id: int,
    payload: EngineeringIndexDocumentIndexReplace,
    db: Session = Depends(get_db),
):
    """
    Rebuilds this document's Engineering Index: every existing entry is
    atomically replaced by ``payload.mentions``. This is the idempotent
    rebuild endpoint - calling it again with the same mentions leaves
    the index unchanged rather than duplicating it.
    """

    repository = SqlAlchemyEngineeringIndexRepository(db)
    document_lookup = SqlAlchemyDocumentLookup(db)

    try:
        return engineering_index_service.replace_document_index(
            repository,
            document_lookup,
            document_id=document_id,
            mentions=[
                mention.model_dump() for mention in payload.mentions
            ],
            now=datetime.utcnow(),
        )
    except IndexedDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except _INVALID_ENTRY_ERRORS as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DuplicateIndexEntryError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


@router.delete(
    "/documents/{document_id}/engineering-index",
    status_code=status.HTTP_204_NO_CONTENT,
)
def clear_document_index(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Removes every Engineering Index entry for this document, without
    deleting the document itself.
    """

    repository = SqlAlchemyEngineeringIndexRepository(db)
    document_lookup = SqlAlchemyDocumentLookup(db)

    try:
        engineering_index_service.clear_document_index(
            repository,
            document_lookup,
            document_id=document_id,
        )
    except IndexedDocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except DocumentNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except ProjectNotIndexableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return None


@router.get(
    "/projects/{project_id}/engineering-index",
    response_model=list[EngineeringIndexEntryRead],
)
def list_index_entries_for_project(
    project_id: int,
    kind: EngineeringIndexEntryKind | None = None,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)

    return engineering_index_service.list_index_entries_for_project(
        repository,
        project_id,
        kind=kind,
    )


@router.get(
    "/projects/{project_id}/engineering-index/search",
    response_model=list[EngineeringIndexEntryRead],
)
def search_index_entries(
    project_id: int,
    identifier: str,
    db: Session = Depends(get_db),
):
    repository = SqlAlchemyEngineeringIndexRepository(db)

    return engineering_index_service.search_index_by_identifier(
        repository,
        project_id,
        identifier,
    )
