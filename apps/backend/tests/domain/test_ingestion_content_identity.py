"""
Tests for the ingestion pipeline's content-identity and format steps
(Milestone 25.2).

Kept apart from ``test_ingestion_lifecycle.py``, which specifies the
lifecycle and the metadata-only pipeline Milestone 25.1 shipped. These
tests specify what the two new steps add - and, just as importantly, that
a caller who supplies neither still gets exactly the 25.1 behaviour.

Every input here is constructed by hand. The pipeline performs no I/O, so
its tests need none either.
"""

from __future__ import annotations

from app.domain.document_identity.content_identity import (
    ContentIdentity,
    ContentIdentityFailureReason,
    ContentIdentityResult,
)
from app.domain.document_identity.document_format import (
    ClassifiedFormat,
    FormatClassification,
    FormatClassificationOutcome,
    FormatEvidence,
    FormatEvidenceKind,
)
from app.domain.document_ingestion.ingestion_models import (
    IngestionFailureCode,
)
from app.domain.document_ingestion.ingestion_pipeline import (
    execute_ingestion_pipeline,
)
from app.domain.engineering_index.document_metadata import DocumentMetadata
from app.domain.project.project_document_scope import DocumentScope

CHECKSUM = "a" * 64


def _metadata(**overrides) -> DocumentMetadata:
    defaults = dict(
        document_id=10,
        project_id=1,
        title="montante-T2-schema.pdf",
        document_format="pdf",
        document_category="functional_schematic",
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    defaults.update(overrides)

    return DocumentMetadata(**defaults)


def _identity(**overrides) -> ContentIdentityResult:
    return ContentIdentityResult(
        resolved=True,
        identity=ContentIdentity(
            storage_reference=overrides.get("storage_reference", "docs/one.pdf"),
            checksum_algorithm="sha256",
            checksum=overrides.get("checksum", CHECKSUM),
            size_bytes=overrides.get("size_bytes", 2048),
        ),
    )


def _identity_failure(
    reason: ContentIdentityFailureReason,
) -> ContentIdentityResult:
    return ContentIdentityResult(
        resolved=False, failure_reason=reason, detail="explained here"
    )


def _classification(
    outcome: FormatClassificationOutcome = (
        FormatClassificationOutcome.CLASSIFIED
    ),
    detected: ClassifiedFormat | None = ClassifiedFormat.PDF,
    decided_by: FormatEvidenceKind | None = (
        FormatEvidenceKind.CONTENT_SIGNATURE
    ),
    evidence: tuple[FormatEvidence, ...] = (),
) -> FormatClassification:
    return FormatClassification(
        outcome=outcome,
        detected_format=detected,
        decided_by=decided_by,
        evidence=evidence
        or (
            FormatEvidence(
                kind=FormatEvidenceKind.CONTENT_SIGNATURE,
                detail="leading bytes matched b'%PDF-'",
                detected_format=ClassifiedFormat.PDF,
            ),
        ),
    )


# --- What the new steps record -----------------------------------------


def test_a_resolved_identity_is_recorded_on_the_snapshot() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    assert result.succeeded
    assert result.document.content.checksum == CHECKSUM
    assert result.document.content.checksum_algorithm == "sha256"
    assert result.document.content.size_bytes == 2048
    assert result.document.content.storage_reference == "docs/one.pdf"


def test_the_classified_format_and_its_provenance_are_recorded() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    assert result.document.format.detected_format == "pdf"
    assert result.document.format.decided_by == "content_signature"


def test_the_stored_format_is_recorded_beside_the_detected_one() -> None:
    """A document filed as unclassified whose bytes say PDF is not a
    failure - and the pipeline does not overwrite the document either. It
    records both, so the divergence is visible and a backfill can act on
    it deliberately."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(document_format="other"),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    assert result.succeeded
    assert result.document.document_format == "other"
    assert result.document.format.detected_format == "pdf"
    assert result.document.format.matches_stored_format is False


def test_a_stored_format_matching_the_bytes_is_reported_as_matching(
) -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(document_format="pdf"),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    assert result.document.format.matches_stored_format is True


def test_evidence_overruled_by_the_signature_is_carried_onto_the_job(
) -> None:
    classification = _classification(
        evidence=(
            FormatEvidence(
                kind=FormatEvidenceKind.CONTENT_SIGNATURE,
                detail="leading bytes matched b'%PDF-'",
                detected_format=ClassifiedFormat.PDF,
            ),
            FormatEvidence(
                kind=FormatEvidenceKind.FILENAME_EXTENSION,
                detail="extension '.dwg'",
                detected_format=ClassifiedFormat.DWG,
            ),
        )
    )

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=classification,
    )

    assert result.document.format.disagreeing_evidence == (
        "filename_extension: extension '.dwg'",
    )


# --- Content failures, each named separately ---------------------------


def test_missing_content_fails_as_content_not_found() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.CONTENT_NOT_FOUND
        ),
        format_classification=_classification(),
    )

    assert result.failure.code is IngestionFailureCode.CONTENT_NOT_FOUND


def test_unreadable_content_fails_as_content_inaccessible() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.CONTENT_INACCESSIBLE
        ),
    )

    assert result.failure.code is IngestionFailureCode.CONTENT_INACCESSIBLE


def test_empty_content_fails_as_empty_content() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.EMPTY_CONTENT
        ),
    )

    assert result.failure.code is IngestionFailureCode.EMPTY_CONTENT


def test_a_broken_read_fails_as_a_checksum_failure() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.CHECKSUM_FAILURE
        ),
    )

    assert result.failure.code is IngestionFailureCode.CHECKSUM_FAILURE


def test_no_content_failure_is_collapsed_into_pipeline_execution_failure(
) -> None:
    """``PIPELINE_EXECUTION_FAILURE`` is for a cause genuinely unknown.
    Every content failure has a name, and using the generic code would
    send an engineer looking in the wrong place."""

    codes = {
        execute_ingestion_pipeline(
            document_id=10,
            metadata=_metadata(),
            content_identity=_identity_failure(reason),
        ).failure.code
        for reason in ContentIdentityFailureReason
    }

    assert IngestionFailureCode.PIPELINE_EXECUTION_FAILURE not in codes
    assert len(codes) == len(ContentIdentityFailureReason)


def test_a_content_failure_carries_the_explanation_it_was_given() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.CONTENT_NOT_FOUND
        ),
    )

    assert result.failure.detail == "explained here"


def test_a_content_failure_still_records_what_was_known_about_the_document(
) -> None:
    """The job explains itself even when it failed: the document's
    metadata was collected before the content was reached."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.CONTENT_NOT_FOUND
        ),
    )

    assert result.document is not None
    assert result.document.title == "montante-T2-schema.pdf"
    assert result.document.content is None


def test_content_is_resolved_before_the_format_is_judged() -> None:
    """Unreadable bytes make every format verdict meaningless, so the
    content failure is the one reported."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity_failure(
            ContentIdentityFailureReason.EMPTY_CONTENT
        ),
        format_classification=_classification(
            FormatClassificationOutcome.UNKNOWN, None, None
        ),
    )

    assert result.failure.code is IngestionFailureCode.EMPTY_CONTENT


# --- Format failures ----------------------------------------------------


def test_an_unclassifiable_document_fails_as_unknown_format() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(
            FormatClassificationOutcome.UNKNOWN,
            None,
            None,
            evidence=(
                FormatEvidence(
                    kind=FormatEvidenceKind.CONTENT_SIGNATURE,
                    detail="leading bytes matched no known signature",
                ),
            ),
        ),
    )

    assert result.failure.code is IngestionFailureCode.UNKNOWN_FORMAT
    assert result.document.format is None


def test_contradictory_evidence_fails_as_conflicting_not_as_unknown(
) -> None:
    """A gap and a contradiction are different problems: one document has
    no evidence, the other has too much of it."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(
            FormatClassificationOutcome.CONFLICTING, None, None
        ),
    )

    assert (
        result.failure.code
        is IngestionFailureCode.CONFLICTING_FORMAT_EVIDENCE
    )


def test_a_format_failure_explains_what_each_source_said() -> None:
    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(
            FormatClassificationOutcome.CONFLICTING,
            None,
            None,
            evidence=(
                FormatEvidence(
                    kind=FormatEvidenceKind.DECLARED_MIME_TYPE,
                    detail="declared 'application/pdf'",
                    detected_format=ClassifiedFormat.PDF,
                ),
                FormatEvidence(
                    kind=FormatEvidenceKind.FILENAME_EXTENSION,
                    detail="extension '.dwg'",
                    detected_format=ClassifiedFormat.DWG,
                ),
            ),
        ),
    )

    assert "declared_mime_type" in result.failure.detail
    assert "filename_extension" in result.failure.detail


def test_a_document_with_no_stored_name_is_refused() -> None:
    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata(title="   ")
    )

    assert result.failure.code is IngestionFailureCode.INVALID_STORED_METADATA


# --- Compatibility with the metadata-only pipeline ----------------------


def test_a_caller_with_no_content_port_still_gets_the_25_1_pipeline(
) -> None:
    """"Nobody looked" is not "the content is broken". A caller without a
    content port runs the shallower pipeline Milestone 25.1 shipped, and
    it is still an honest ingestion - it claims nothing about content it
    never examined."""

    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata()
    )

    assert result.succeeded
    assert result.document.content is None
    assert result.document.format is None


def test_content_identity_alone_is_enough_to_record_it() -> None:
    result = execute_ingestion_pipeline(
        document_id=10, metadata=_metadata(), content_identity=_identity()
    )

    assert result.succeeded
    assert result.document.content is not None
    assert result.document.format is None


def test_the_extended_pipeline_is_deterministic() -> None:
    arguments = dict(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    assert execute_ingestion_pipeline(
        **arguments
    ) == execute_ingestion_pipeline(**arguments)


def test_the_pipeline_records_no_semantic_content() -> None:
    """It knows which bytes these are and what kind of file they form. It
    knows nothing about what the document says, and there is nowhere on
    the record to put such a claim."""

    result = execute_ingestion_pipeline(
        document_id=10,
        metadata=_metadata(),
        content_identity=_identity(),
        format_classification=_classification(),
    )

    import dataclasses

    field_names = {
        field.name for field in dataclasses.fields(result.document)
    }

    assert field_names == {
        "document_id",
        "project_id",
        "title",
        "document_format",
        "document_category",
        "revision",
        "scope",
        "content",
        "format",
    }
