"""
The document processing workflow (EPIC 2, Milestone 26.2).

**The one supported path from an uploaded PDF to a semantic consumer.**

```
Uploaded PDF
   -> Ingestion                     (25.1: lifecycle, governed acceptance)
   -> Document Identity             (25.2: checksum, classified format)
   -> Canonical PDF Representation  (26.1: the only PDF decode in the system)
   -> Canonical Text Segmentation   (27.1: the structure consumers read)
   -> Assembled text                (26.2: a deterministic render of it)
   -> Existing downstream consumer  (the Knowledge Graph, unchanged)
```

Before this milestone the upload endpoint ran its own second path: it
opened the stored PDF with PyMuPDF and handed the result straight to the
Knowledge Graph. That path is gone. Nothing downstream of
canonicalisation touches a file, a byte or a parser.

## What this module is, and is not

It **orchestrates existing services and adds no processing of its own**.
Ingestion, canonicalisation and segmentation are called exactly as their
own endpoints call them, so a document processed through here and a
document processed stage-by-stage end up with identical records. The only
thing this module contributes is the *order*, and an honest account of
where the sequence stopped.

It contains no parsing, no extraction, no interpretation and no
Knowledge Graph rules - the downstream consumer is injected, and this
module neither knows nor cares what it does with the text.

## Idempotency

Every stage is already idempotent, and this workflow inherits that rather
than reimplementing it: an existing ingestion job, canonical
representation or segmentation is re-used, not rebuilt. Re-running the
workflow over an unchanged document therefore re-parses nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.canonical_pdf.canonical_representation_repository import (
    CanonicalRepresentationRepository,
)
from app.domain.canonical_pdf.pdf_parser_port import PdfParserPort
from app.domain.canonical_text.canonical_text_assembler import (
    assemble_document_text,
)
from app.domain.canonical_text.canonical_text_repository import (
    CanonicalTextRepository,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.domain.document_ingestion.ingestion_repository import (
    IngestionJobRepository,
)
from app.domain.engineering_index.document_metadata import (
    DocumentMetadataPort,
)
from app.services import (
    canonical_pdf_service,
    canonical_text_service,
    document_ingestion_service,
)


class PipelineStage(str, Enum):
    """Which stage a run reached, and - on failure - which one stopped
    it. Named stages rather than a single "upload failed": each sends an
    engineer somewhere different."""

    INGESTION = "ingestion"
    CANONICAL_REPRESENTATION = "canonical_representation"
    SEGMENTATION = "segmentation"
    TEXT_ASSEMBLY = "text_assembly"
    DOWNSTREAM_CONSUMER = "downstream_consumer"


class PipelineFailureCode(str, Enum):
    """
    The conditions **this workflow itself** detects.

    Deliberately small. Every failure a stage can describe in its own
    vocabulary is reported in that vocabulary - ``DocumentPipelineFailure``
    carries the failing stage's own code verbatim - because
    ``unsupported_format`` and ``encrypted_document`` already say exactly
    what happened, and restating them here would create a fourth parallel
    taxonomy that could drift from the other three.
    """

    # Ingestion concluded, and not with READY_FOR_EXTRACTION. The
    # ingestion job carries its own failure code; this names the shape of
    # the problem for a caller reading the workflow's result.
    INGESTION_INCOMPLETE = "ingestion_incomplete"
    # A stage reported success and the next stage could not find what it
    # produced. Nothing in the pipeline should be able to reach this; if
    # it does, the two stages disagree about reality and continuing would
    # build on a contradiction.
    INCONSISTENT_PIPELINE_STATE = "inconsistent_pipeline_state"
    # The segmentation carries text and it renders to nothing.
    NO_EXTRACTABLE_TEXT = "no_extractable_text"
    # The injected consumer raised. Its own exception type and message
    # are carried in ``detail``.
    DOWNSTREAM_CONSUMER_FAILURE = "downstream_consumer_failure"


@dataclass(frozen=True, slots=True)
class DocumentPipelineFailure:
    """
    Where the pipeline stopped, and why.

    ``code`` is a plain string on purpose: it carries the **failing
    stage's own** vocabulary - an ``IngestionFailureCode``, a
    ``CanonicalizationFailureCode``, a ``SegmentationFailureCode`` or a
    ``PipelineFailureCode`` - rather than a value translated into a
    fourth. ``stage`` says which vocabulary to read it in.
    """

    stage: PipelineStage
    code: str
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentPipelineResult:
    """
    What one run of the workflow concluded.

    ``reused_representation``/``reused_segmentation`` report that an
    existing artefact was re-used rather than rebuilt - the observable
    evidence that re-running the workflow re-parses nothing.
    """

    succeeded: bool
    stage_reached: PipelineStage
    text: str | None = None
    consumer_result: object | None = None
    reused_representation: bool = False
    reused_segmentation: bool = False
    failure: DocumentPipelineFailure | None = None


def process_uploaded_document(
    *,
    document_id: int,
    ingestion_repository: IngestionJobRepository,
    document_metadata_port: DocumentMetadataPort,
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    parser: PdfParserPort,
    representation_repository: CanonicalRepresentationRepository,
    text_repository: CanonicalTextRepository,
    now: datetime,
    consumer: Callable[[str], object] | None = None,
) -> DocumentPipelineResult:
    """
    Run one document through the whole pipeline and, if a ``consumer`` is
    given, hand it the assembled text.

    ``consumer`` receives **a string and nothing else**. It is not given
    the document id, the storage reference, the representation or the
    segmentation, because a consumer that could reach any of those could
    decode the PDF for itself - which is the arrangement this milestone
    exists to end.

    Stages run in order and the first failure stops the run: there is no
    point segmenting a document that could not be parsed, and reporting
    four failures when one caused the others would obscure the cause.
    """

    ingestion = document_ingestion_service.ingest_document(
        ingestion_repository,
        document_metadata_port,
        document_id=document_id,
        now=now,
        content_port=content_port,
        storage_location_port=storage_location_port,
    )

    if not ingestion.is_ready_for_extraction:
        failure = ingestion.failure

        return _failed(
            PipelineStage.INGESTION,
            failure.code.value
            if failure is not None
            else PipelineFailureCode.INGESTION_INCOMPLETE.value,
            failure.message
            if failure is not None
            else f"Ingestion of document '{document_id}' did not conclude "
            "READY_FOR_EXTRACTION.",
            detail=failure.detail if failure is not None else None,
        )

    canonicalisation = canonical_pdf_service.canonicalize_document(
        parser,
        representation_repository,
        content_port,
        storage_location_port,
        document_metadata_port,
        ingestion_repository,
        document_id=document_id,
    )

    if not canonicalisation.succeeded:
        return _failed(
            PipelineStage.CANONICAL_REPRESENTATION,
            canonicalisation.failure.code.value,
            canonicalisation.failure.message,
            detail=canonicalisation.failure.detail,
        )

    segmentation = canonical_text_service.segment_document(
        representation_repository,
        text_repository,
        document_id=document_id,
    )

    if not segmentation.succeeded:
        return _failed(
            PipelineStage.SEGMENTATION,
            segmentation.failure.code.value,
            segmentation.failure.message,
            detail=segmentation.failure.detail,
            reused_representation=canonicalisation.reused,
        )

    text = assemble_document_text(segmentation.segmentation)

    if not text.strip():
        # The segmentation holds tokens and they render to nothing. The
        # segmenter already refuses a token-less segmentation, so this is
        # the assembler and the segmenter disagreeing - reported rather
        # than passed downstream as an empty string, which a consumer
        # would read as "this document says nothing".
        return _failed(
            PipelineStage.TEXT_ASSEMBLY,
            PipelineFailureCode.NO_EXTRACTABLE_TEXT.value,
            f"Document '{document_id}' segmented to "
            f"{segmentation.segmentation.token_count} token(s) and "
            "assembled to no text.",
            reused_representation=canonicalisation.reused,
            reused_segmentation=segmentation.reused,
        )

    if consumer is None:
        return DocumentPipelineResult(
            succeeded=True,
            stage_reached=PipelineStage.TEXT_ASSEMBLY,
            text=text,
            reused_representation=canonicalisation.reused,
            reused_segmentation=segmentation.reused,
        )

    try:
        consumer_result = consumer(text)
    except Exception as error:  # noqa: BLE001 - see below
        # Deliberately broad. The consumer is injected and this workflow
        # cannot enumerate how someone else's code fails; what it can do
        # is report *that* the downstream stage failed, name the stage,
        # and carry the cause rather than swallowing it.
        return _failed(
            PipelineStage.DOWNSTREAM_CONSUMER,
            PipelineFailureCode.DOWNSTREAM_CONSUMER_FAILURE.value,
            f"The downstream consumer failed for document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
            reused_representation=canonicalisation.reused,
            reused_segmentation=segmentation.reused,
        )

    return DocumentPipelineResult(
        succeeded=True,
        stage_reached=PipelineStage.DOWNSTREAM_CONSUMER,
        text=text,
        consumer_result=consumer_result,
        reused_representation=canonicalisation.reused,
        reused_segmentation=segmentation.reused,
    )


def _failed(
    stage: PipelineStage,
    code: str,
    message: str,
    *,
    detail: str | None = None,
    reused_representation: bool = False,
    reused_segmentation: bool = False,
) -> DocumentPipelineResult:
    return DocumentPipelineResult(
        succeeded=False,
        stage_reached=stage,
        reused_representation=reused_representation,
        reused_segmentation=reused_segmentation,
        failure=DocumentPipelineFailure(
            stage=stage, code=code, message=message, detail=detail
        ),
    )
