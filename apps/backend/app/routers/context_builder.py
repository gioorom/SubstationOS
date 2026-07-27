from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.domain.context_builder.budget_policy import (
    DEFAULT_MAX_ATTRIBUTES,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_ENTITIES,
    DEFAULT_MAX_METADATA_ENTRIES,
    DEFAULT_MAX_RELATIONSHIPS,
    DEFAULT_MAX_WARNINGS,
)
from app.domain.context_builder.context_builder_exceptions import (
    ContextBuilderError,
)
from app.domain.context_builder.context_builder_models import (
    ContextBuilderResult,
)
from app.schemas.context_builder import (
    ContextBuildRequestBody,
    ContextBuilderResultRead,
    collection_from_schema,
)
from app.services import context_builder_service

router = APIRouter(
    tags=["Context Builder"],
)


@router.post(
    "/projects/{project_id}/context-builder/build",
    response_model=ContextBuilderResultRead,
    summary="Assemble a bounded, provenance-aware ContextPackage from a "
    "KnowledgeCandidateCollection",
)
def build_context_package(
    project_id: int,
    body: ContextBuildRequestBody,
) -> ContextBuilderResult:
    candidates = collection_from_schema(body.candidates)
    metadata_entries = tuple(
        (entry.key, entry.value) for entry in body.metadata_entries
    )

    try:
        return context_builder_service.build_context_package(
            project_id=project_id,
            candidates=candidates,
            max_candidates=body.max_candidates
            if body.max_candidates is not None
            else DEFAULT_MAX_CANDIDATES,
            max_entities=body.max_entities
            if body.max_entities is not None
            else DEFAULT_MAX_ENTITIES,
            max_relationships=body.max_relationships
            if body.max_relationships is not None
            else DEFAULT_MAX_RELATIONSHIPS,
            max_attributes=body.max_attributes
            if body.max_attributes is not None
            else DEFAULT_MAX_ATTRIBUTES,
            max_metadata_entries=body.max_metadata_entries
            if body.max_metadata_entries is not None
            else DEFAULT_MAX_METADATA_ENTRIES,
            max_warnings=body.max_warnings
            if body.max_warnings is not None
            else DEFAULT_MAX_WARNINGS,
            metadata_entries=metadata_entries,
            retrieval_policy_version=body.retrieval_policy_version,
            now=datetime.utcnow(),
        )
    except ContextBuilderError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
