"""
The Canonical Text Segmentation API (Milestone 27.1).

```
POST /documents/{document_id}/canonical-text   segment or re-use
GET  /documents/{document_id}/canonical-text   read the current segmentation
```

The composition root for segmentation. Note what it constructs: the
canonical representation repository and the text repository, and nothing
else. There is no content adapter and no parser here, because
segmentation's only input is the representation - it has no way to reach
the original PDF.

**Status codes** follow the discipline the rest of this codebase already
uses. `201` when a segmentation was built, `200` when the same
representation had already been segmented under the same rules. A
`404` for a document with no canonical representation - segmentation is
the step after canonicalisation, and asking for it first is a state
conflict rather than a malformed request. `500` when the segmentation was
built and storage failed, which is this system's fault rather than an
answer. Everything else returns `200` with a `succeeded: false` result
carrying the typed cause, so `422` keeps meaning exactly one thing across
this codebase: a structurally invalid request.

It performs no extraction, invokes no provider, and writes neither the
Engineering Index nor the Knowledge Graph.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.canonical_text.canonical_text_failures import (
    SegmentationFailureCode,
)
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
)
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.routers.security import require_capability
from app.services import audit_service
from app.schemas.canonical_text import (
    CanonicalTextRead,
    SegmentationResultRead,
)
from app.services import canonical_text_service

router = APIRouter(
    tags=["Canonical Text Segmentation"],
)

# The two failures that are not answers about the document.
_STATUS_FOR_FAILURE: dict[SegmentationFailureCode, int] = {
    SegmentationFailureCode.CANONICAL_REPRESENTATION_MISSING: (
        status.HTTP_404_NOT_FOUND
    ),
    SegmentationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE: (
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
    "/documents/{document_id}/canonical-text",
    response_model=SegmentationResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Segment a document's canonical representation, or re-use "
    "the segmentation it already has",
)
def segment_document(
    document_id: int,
    response: Response,
    actor: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
    db: Session = Depends(get_db),
) -> SegmentationResultRead:
    result = canonical_text_service.segment_document(
        SqlAlchemyCanonicalRepresentationRepository(db),
        SqlAlchemyCanonicalTextRepository(db),
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
        # Nothing was created; the existing segmentation is returned.
        response.status_code = status.HTTP_200_OK

    # Who ran the stage, recorded on the *action*. The artefacts the
    # stage produced carry no actor and no timestamp, which is why two
    # runs under two different logins compare equal.
    audit_service.record_pipeline_execution(
        SqlAlchemyAuditRepository(db),
        identity=actor,
        stage="canonical_text",
        document_id=document_id,
        succeeded=result.succeeded,
        reused=result.reused,
        now=datetime.utcnow(),
    )

    return SegmentationResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/canonical-text",
    response_model=CanonicalTextRead,
    summary="Read a document's canonical text segmentation - the "
    "structure every future extractor consumes",
)
def read_canonical_text(
    document_id: int,
    db: Session = Depends(get_db),
) -> CanonicalTextRead:
    segmentation = canonical_text_service.get_segmentation(
        SqlAlchemyCanonicalTextRepository(db), document_id
    )

    if segmentation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no canonical text "
            "segmentation; it has not been segmented.",
        )

    return CanonicalTextRead.model_validate(segmentation)
