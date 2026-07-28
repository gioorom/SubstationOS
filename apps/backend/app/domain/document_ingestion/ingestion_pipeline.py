"""
The ingestion pipeline (Milestone 25.1, extended in 25.2) - the
deterministic checks one document passes before it is declared ready for
a future extractor.

    document metadata
            |
       metadata exists and is usable?
            |
       content identity resolved?      (found, readable, non-empty, hashed)
            |
       format classified?              (signature > MIME > extension)
            |
       stored format consistent?       (recorded, not silently overwritten)
            |
       collect snapshot                (copied, never derived)
            |
       IngestionPipelineResult

**What this deliberately does not do**, and must not grow into:

- it performs **no semantic extraction**: the only bytes that reach a
  decision here are a file's leading signature and a SHA-256 digest,
  neither of which says anything about what a document *contains*;
- no parsing, no OCR, no text extraction, no LLM, no embeddings;
- it writes nothing - not the Engineering Index, not the Project
  Knowledge Graph, not even the job. It returns a conclusion, and the
  service persists it.

Pure and deterministic: same inputs, same result, every time. **No I/O**
- content identity and the leading bytes are resolved by the service
through ``DocumentContentPort`` and handed in, exactly as document
metadata already is. That is what keeps this function's determinism
verifiable rather than merely asserted.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.document_identity.content_identity import (
    ContentIdentity,
    ContentIdentityFailureReason,
    ContentIdentityResult,
)
from app.domain.document_identity.document_format import (
    ClassifiedFormat,
    FormatClassification,
    FormatClassificationOutcome,
)
from app.domain.document_ingestion.ingestion_models import (
    DocumentContentIdentitySnapshot,
    DocumentFormatSnapshot,
    IngestedDocumentSnapshot,
    IngestionFailure,
    IngestionFailureCode,
    IngestionOutcome,
    IngestionPipelineResult,
)
from app.domain.document_ingestion.ingestion_policy import (
    INGESTION_PIPELINE_VERSION,
    SUPPORTED_INGESTION_FORMATS,
    is_supported_format,
)
from app.domain.engineering_index.document_metadata import DocumentMetadata

# Content-identity failures map one-for-one onto ingestion failure codes.
# A table rather than a branch chain, and one-for-one rather than
# collapsed: each reason sends an engineer somewhere different.
_CONTENT_FAILURE_CODES: dict[
    ContentIdentityFailureReason, IngestionFailureCode
] = {
    ContentIdentityFailureReason.CONTENT_NOT_FOUND: (
        IngestionFailureCode.CONTENT_NOT_FOUND
    ),
    ContentIdentityFailureReason.CONTENT_INACCESSIBLE: (
        IngestionFailureCode.CONTENT_INACCESSIBLE
    ),
    ContentIdentityFailureReason.EMPTY_CONTENT: (
        IngestionFailureCode.EMPTY_CONTENT
    ),
    ContentIdentityFailureReason.CHECKSUM_FAILURE: (
        IngestionFailureCode.CHECKSUM_FAILURE
    ),
}


def _failed(
    code: IngestionFailureCode,
    message: str,
    *,
    detail: str | None = None,
    document: IngestedDocumentSnapshot | None = None,
    pipeline_version: str,
) -> IngestionPipelineResult:
    return IngestionPipelineResult(
        outcome=IngestionOutcome.FAILED,
        pipeline_version=pipeline_version,
        document=document,
        failure=IngestionFailure(code=code, message=message, detail=detail),
    )


def _base_snapshot(metadata: DocumentMetadata) -> IngestedDocumentSnapshot:
    """Every field copied from what the repository already holds. Nothing
    is derived, computed or inferred - a snapshot that added a fact would
    be an extraction, which this pipeline does not perform."""

    return IngestedDocumentSnapshot(
        document_id=metadata.document_id,
        project_id=metadata.project_id,
        title=metadata.title,
        document_format=metadata.document_format,
        document_category=metadata.document_category,
        revision=metadata.revision,
        scope=metadata.scope,
    )


def execute_ingestion_pipeline(
    *,
    document_id: int,
    metadata: DocumentMetadata | None,
    content_identity: ContentIdentityResult | None = None,
    format_classification: FormatClassification | None = None,
    pipeline_version: str = INGESTION_PIPELINE_VERSION,
) -> IngestionPipelineResult:
    """
    Runs every check, in order, and returns the first failure or a
    ready-for-extraction result.

    ``metadata`` is ``None`` when the repository holds no such document;
    ``content_identity`` and ``format_classification`` are resolved by the
    service through the content port and handed in, because this function
    performs no I/O. Both being ``None`` runs the metadata-only pipeline
    Milestone 25.1 shipped - which is what the backfill path and any
    caller without a content port get, and which is still an honest, if
    shallower, ingestion.
    """

    if metadata is None:
        return _failed(
            IngestionFailureCode.DOCUMENT_NOT_FOUND,
            f"Document '{document_id}' does not exist; there is nothing "
            "to ingest.",
            pipeline_version=pipeline_version,
        )

    snapshot = _base_snapshot(metadata)

    if not snapshot.title.strip():
        return _failed(
            IngestionFailureCode.INVALID_STORED_METADATA,
            f"Document '{document_id}' has no filename recorded.",
            detail="A document with no stored name cannot be identified "
            "to a future extractor.",
            document=snapshot,
            pipeline_version=pipeline_version,
        )

    if not is_supported_format(snapshot.document_format):
        return _failed(
            IngestionFailureCode.UNSUPPORTED_FORMAT,
            f"Document '{document_id}' records format "
            f"'{snapshot.document_format}', which is not a format this "
            "system defines.",
            detail=(
                "Known formats: "
                + ", ".join(sorted(SUPPORTED_INGESTION_FORMATS))
                + ". A value outside this set indicates a row written "
                "under a different schema version, not a document that "
                "went unclassified - an unclassified document ingests "
                "normally."
            ),
            document=snapshot,
            pipeline_version=pipeline_version,
        )

    if content_identity is not None:
        if not content_identity.resolved:
            return _failed(
                _CONTENT_FAILURE_CODES[content_identity.failure_reason],
                f"Document '{document_id}' has no usable stored content.",
                detail=content_identity.detail,
                document=snapshot,
                pipeline_version=pipeline_version,
            )

        identity = content_identity.identity
        snapshot = _with_content(snapshot, identity)

    if format_classification is not None:
        classified, failure = _classify(
            document_id, snapshot, format_classification, pipeline_version
        )
        if failure is not None:
            return failure
        snapshot = classified

    return IngestionPipelineResult(
        outcome=IngestionOutcome.READY_FOR_EXTRACTION,
        pipeline_version=pipeline_version,
        document=snapshot,
    )


def _with_content(
    snapshot: IngestedDocumentSnapshot,
    identity: ContentIdentity,
) -> IngestedDocumentSnapshot:
    return replace(
        snapshot,
        content=DocumentContentIdentitySnapshot(
            storage_reference=identity.storage_reference,
            checksum_algorithm=identity.checksum_algorithm,
            checksum=identity.checksum,
            size_bytes=identity.size_bytes,
        ),
    )


def _classify(
    document_id: int,
    snapshot: IngestedDocumentSnapshot,
    classification: FormatClassification,
    pipeline_version: str,
) -> tuple[IngestedDocumentSnapshot | None, IngestionPipelineResult | None]:
    """
    Records the classifier's decision, or fails on one it could not make.

    **The stored format is never overwritten here.** A document whose
    record says ``other`` and whose bytes say ``pdf`` is not a failure -
    ``other`` means unclassified, and the classifier has now classified
    it. The snapshot records both, so the divergence is visible and a
    backfill can act on it deliberately rather than an ingestion mutating
    a document row as a side effect.
    """

    from dataclasses import replace

    if classification.outcome is FormatClassificationOutcome.UNKNOWN:
        return None, _failed(
            IngestionFailureCode.UNKNOWN_FORMAT,
            f"Document '{document_id}' could not be classified: no "
            "content signature, MIME type or extension identified a "
            "known format.",
            detail="; ".join(
                f"{evidence.kind.value}: {evidence.detail}"
                for evidence in classification.evidence
            ),
            document=snapshot,
            pipeline_version=pipeline_version,
        )

    if classification.outcome is FormatClassificationOutcome.CONFLICTING:
        return None, _failed(
            IngestionFailureCode.CONFLICTING_FORMAT_EVIDENCE,
            f"Document '{document_id}' has contradictory format evidence "
            "and no content signature to settle it.",
            detail="; ".join(
                f"{evidence.kind.value}: {evidence.detail}"
                for evidence in classification.evidence
            ),
            document=snapshot,
            pipeline_version=pipeline_version,
        )

    detected: ClassifiedFormat = classification.detected_format

    return (
        replace(
            snapshot,
            format=DocumentFormatSnapshot(
                detected_format=detected.value,
                decided_by=classification.decided_by.value,
                stored_format=snapshot.document_format,
                disagreeing_evidence=tuple(
                    f"{evidence.kind.value}: {evidence.detail}"
                    for evidence in classification.disagreeing_evidence
                ),
            ),
        ),
        None,
    )
