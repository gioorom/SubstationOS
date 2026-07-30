"""
The Canonical PDF Representation API (Milestone 26.1).

```
POST /documents/{document_id}/canonical-representation   build or re-use
GET  /documents/{document_id}/canonical-representation   read the current one
GET  .../canonical-representation/pages/{page_number}    read one page of it
```

The page-scoped read was added for the Engineering Workspace (EPIC
30.2), which renders one page at a time and needs that page's spans and
bounding boxes without transferring every other page to get them. It is
a projection of the stored representation and derives nothing.

This router is the composition root for canonicalisation: it constructs
the parser, the representation repository, and the content and
storage-location adapters Milestone 25.2 already provides, and hands them
to the service, which knows only the ports. Replacing PyMuPDF is a change
to one adapter and this file.

**Status codes.** `201` when a representation was built, `200` when
identical bytes already had one and it was re-used. A refusal that is a
legitimate *answer about the document* - an unsupported format, an
encrypted or corrupted PDF, no extractable text - returns `200` with a
`succeeded: false` result carrying the typed cause, the same discipline
ingestion and the Engineering Engine already follow, so `422` keeps
meaning exactly one thing: a structurally invalid request. The three
exceptions are cases where no answer about the document exists: `404` for
a document that is not there, `409` for one no ingestion job has declared
ready, and `500` when the representation was built and storage failed -
which is this system's fault, not an answer.

It performs no extraction, invokes no provider, and writes neither the
Engineering Index nor the Knowledge Graph.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailureCode,
)
from app.infrastructure.canonical_pdf.pymupdf_parser import PyMuPdfParser
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
)
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_storage_location import (  # noqa: E501
    SqlAlchemyDocumentStorageLocation,
)
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.schemas.canonical_pdf import (
    CanonicalizationResultRead,
    CanonicalPdfPageRead,
    CanonicalRepresentationRead,
)
from app.services import canonical_pdf_service

router = APIRouter(
    tags=["Canonical PDF Representation"],
)

# The three failures that are not answers about the document. Everything
# else is one, and is returned as a result rather than as an error.
_STATUS_FOR_FAILURE: dict[CanonicalizationFailureCode, int] = {
    CanonicalizationFailureCode.DOCUMENT_NOT_FOUND: (
        status.HTTP_404_NOT_FOUND
    ),
    CanonicalizationFailureCode.NOT_READY_FOR_EXTRACTION: (
        status.HTTP_409_CONFLICT
    ),
    CanonicalizationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE: (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ),
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/documents/{document_id}/canonical-representation",
    response_model=CanonicalizationResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Build the canonical representation of a PDF, or re-use the "
    "one identical bytes already have",
)
def canonicalize_document(
    document_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> CanonicalizationResultRead:
    result = canonical_pdf_service.canonicalize_document(
        PyMuPdfParser(),
        SqlAlchemyCanonicalRepresentationRepository(db),
        FilesystemDocumentContentAdapter(),
        SqlAlchemyDocumentStorageLocation(db),
        SqlAlchemyDocumentMetadataRepository(db),
        SqlAlchemyIngestionJobRepository(db),
        document_id=document_id,
    )

    if not result.succeeded:
        error_status = _STATUS_FOR_FAILURE.get(result.failure.code)

        if error_status is not None:
            raise HTTPException(
                status_code=error_status, detail=result.failure.message
            )

        response.status_code = status.HTTP_200_OK
    elif result.reused:
        # Nothing was created; the representation these bytes already had
        # is returned unchanged.
        response.status_code = status.HTTP_200_OK

    return CanonicalizationResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/canonical-representation",
    response_model=CanonicalRepresentationRead,
    summary="Read a document's canonical representation - the only "
    "supported way to consume its text",
)
def read_canonical_representation(
    document_id: int,
    db: Session = Depends(get_db),
) -> CanonicalRepresentationRead:
    representation = canonical_pdf_service.get_representation(
        SqlAlchemyCanonicalRepresentationRepository(db), document_id
    )

    if representation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no canonical "
            "representation; it has not been canonicalised.",
        )

    return CanonicalRepresentationRead.model_validate(representation)


@router.get(
    "/documents/{document_id}/canonical-representation/pages/"
    "{page_number}",
    response_model=CanonicalPdfPageRead,
    summary="Read one page of a document's canonical representation - "
    "the spans, and where on the page the parser saw them",
)
def read_canonical_representation_page(
    document_id: int,
    page_number: int,
    db: Session = Depends(get_db),
) -> CanonicalPdfPageRead:
    """
    The page-scoped read of an artefact that already exists in full.

    A reader displaying page 7 of a 200-page drawing set needs the spans
    and bounding boxes of page 7, and this endpoint is the difference
    between transferring those and transferring all two hundred pages to
    use one. It **adds nothing**: every field comes from the stored
    representation, no coordinate is computed here, and no page that the
    parser did not record can be requested into existence.

    ``page_number`` is 1-based, as the representation records it.
    """

    page = canonical_pdf_service.get_page(
        SqlAlchemyCanonicalRepresentationRepository(db),
        document_id,
        page_number,
    )

    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no canonical page "
            f"'{page_number}'; either it has not been canonicalised, or "
            "its representation does not record that page.",
        )

    return CanonicalPdfPageRead.model_validate(page)
