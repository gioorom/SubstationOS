"""
The Engineering Evidence API (Milestone 28.1).

```
POST /documents/{document_id}/engineering-evidence   extract or re-use
GET  /documents/{document_id}/engineering-evidence   read the current set
```

The composition root for evidence extraction. Note what it constructs:
the canonical text repository and the evidence repository, and nothing
else. There is no content adapter and no parser here, because extraction
reads canonical text and has no way to reach a document.

**Status codes.** `201` when a set was extracted, `200` when the same
canonical source had already been extracted under the same policy, `404`
when the document has no canonical text - extraction is the step after
segmentation, and asking for it first is a state conflict rather than a
malformed request. `500` when the set was built and storage failed.
Everything else returns `200` with a `succeeded: false` result carrying
the typed cause, so `422` keeps meaning exactly one thing across this
codebase.

Finding nothing is **not** a failure: a document may simply contain
nothing these rules recognise. That case returns `201` with
`found_evidence: false`.

No ORM model is exposed. It writes neither the Engineering Index nor the
Knowledge Graph, and creates no entity or relationship.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.engineering_evidence.evidence_failures import (
    EvidenceFailureCode,
)
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.infrastructure.engineering_evidence.sqlalchemy_engineering_evidence_repository import (  # noqa: E501
    SqlAlchemyEngineeringEvidenceRepository,
)
from app.models.document import Document as DocumentRecord
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.routers.security import require_capability
from app.services import audit_service
from app.schemas.engineering_evidence import (
    EvidenceExtractionResultRead,
    EvidenceSetRead,
)
from app.services import engineering_evidence_service

router = APIRouter(
    tags=["Engineering Evidence"],
)

# The two failures that are not answers about the document.
_STATUS_FOR_FAILURE: dict[EvidenceFailureCode, int] = {
    EvidenceFailureCode.CANONICAL_TEXT_MISSING: status.HTTP_404_NOT_FOUND,
    EvidenceFailureCode.EVIDENCE_PERSISTENCE_FAILURE: (
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
    "/documents/{document_id}/engineering-evidence",
    response_model=EvidenceExtractionResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Extract deterministic engineering evidence from a "
    "document's canonical text, or re-use the set it already has",
)
def extract_engineering_evidence(
    document_id: int,
    response: Response,
    actor: AuditIdentity = Depends(
        require_capability(Capability.USE_ENGINEERING_PLATFORM)
    ),
    db: Session = Depends(get_db),
) -> EvidenceExtractionResultRead:
    document = db.get(DocumentRecord, document_id)

    result = engineering_evidence_service.extract_document_evidence(
        SqlAlchemyCanonicalTextRepository(db),
        SqlAlchemyEngineeringEvidenceRepository(db),
        document_id=document_id,
        project_id=document.project_id if document is not None else None,
    )

    if not result.succeeded:
        error_status = _STATUS_FOR_FAILURE.get(result.failure.code)

        if error_status is not None:
            raise HTTPException(
                status_code=error_status, detail=result.failure.message
            )

        response.status_code = status.HTTP_200_OK
    elif result.reused:
        # Nothing was created; the set this source already had is
        # returned unchanged.
        response.status_code = status.HTTP_200_OK

    # Who ran the stage, recorded on the *action*. The artefacts the
    # stage produced carry no actor and no timestamp, which is why two
    # runs under two different logins compare equal.
    audit_service.record_pipeline_execution(
        SqlAlchemyAuditRepository(db),
        identity=actor,
        stage="engineering_evidence",
        document_id=document_id,
        succeeded=result.succeeded,
        reused=result.reused,
        now=datetime.utcnow(),
    )

    return EvidenceExtractionResultRead.from_domain(result)


@router.get(
    "/documents/{document_id}/engineering-evidence",
    response_model=EvidenceSetRead,
    summary="Read a document's engineering evidence, each item with its "
    "full provenance",
)
def read_engineering_evidence(
    document_id: int,
    db: Session = Depends(get_db),
) -> EvidenceSetRead:
    evidence_set = engineering_evidence_service.get_evidence_set(
        SqlAlchemyEngineeringEvidenceRepository(db), document_id
    )

    if evidence_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' has no engineering "
            "evidence; no extraction has run against it.",
        )

    return EvidenceSetRead.model_validate(evidence_set)
