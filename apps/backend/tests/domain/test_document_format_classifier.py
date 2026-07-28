"""
Tests for the document format classifier (Milestone 25.2).

The classifier is the one place a format is decided, so these tests are
about the *rule*: which evidence wins, what happens when evidence
disagrees, and what happens when nobody has an opinion. Every case names
the behaviour an engineer would expect from the file itself.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import (
    ClassifiedFormat,
    FormatClassificationOutcome,
    FormatEvidenceKind,
)
from app.domain.document_identity.format_classifier import (
    classify_document_format,
)

PDF_BYTES = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3"
PNG_BYTES = b"\x89PNG\r\n\x1a\n"
DWG_BYTES = b"AC1027\x00\x00\x00\x00"
ZIP_BYTES = b"PK\x03\x04\x14\x00\x06\x00"


# --- The signature decides ---------------------------------------------


def test_a_pdf_signature_classifies_the_document_as_pdf() -> None:
    classification = classify_document_format(
        content_prefix=PDF_BYTES, filename="drawing.pdf"
    )

    assert classification.outcome is FormatClassificationOutcome.CLASSIFIED
    assert classification.detected_format is ClassifiedFormat.PDF
    assert classification.decided_by is FormatEvidenceKind.CONTENT_SIGNATURE


def test_a_dwg_signature_classifies_the_document_as_dwg() -> None:
    classification = classify_document_format(content_prefix=DWG_BYTES)

    assert classification.detected_format is ClassifiedFormat.DWG


def test_a_png_signature_classifies_the_document_as_an_image() -> None:
    classification = classify_document_format(content_prefix=PNG_BYTES)

    assert classification.detected_format is ClassifiedFormat.IMAGE


def test_the_signature_overrules_a_contradicting_extension() -> None:
    """The bytes are the document; the name is a label somebody typed."""

    classification = classify_document_format(
        content_prefix=PDF_BYTES,
        declared_mime_type="image/vnd.dwg",
        filename="single_line_diagram.dwg",
    )

    assert classification.detected_format is ClassifiedFormat.PDF
    assert classification.decided_by is FormatEvidenceKind.CONTENT_SIGNATURE


def test_evidence_overruled_by_the_signature_is_still_reported() -> None:
    """Certainty about the format is not a reason to hide that the file's
    name says something else - that is worth an engineer's attention."""

    classification = classify_document_format(
        content_prefix=PDF_BYTES, filename="single_line_diagram.dwg"
    )

    disagreeing = classification.disagreeing_evidence

    assert [evidence.kind for evidence in disagreeing] == [
        FormatEvidenceKind.FILENAME_EXTENSION
    ]


def test_agreeing_evidence_is_not_reported_as_disagreement() -> None:
    classification = classify_document_format(
        content_prefix=PDF_BYTES,
        declared_mime_type="application/pdf",
        filename="report.pdf",
    )

    assert classification.disagreeing_evidence == ()


# --- Falling back to weaker evidence -----------------------------------


def test_the_mime_type_decides_when_no_signature_is_readable() -> None:
    classification = classify_document_format(
        content_prefix=None, declared_mime_type="application/pdf"
    )

    assert classification.detected_format is ClassifiedFormat.PDF
    assert classification.decided_by is FormatEvidenceKind.DECLARED_MIME_TYPE


def test_the_extension_decides_when_it_is_the_only_evidence() -> None:
    classification = classify_document_format(filename="cable_list.xlsx")

    assert classification.detected_format is ClassifiedFormat.XLSX
    assert classification.decided_by is FormatEvidenceKind.FILENAME_EXTENSION


def test_a_mime_type_carrying_parameters_is_still_recognised() -> None:
    classification = classify_document_format(
        declared_mime_type="application/pdf; charset=binary"
    )

    assert classification.detected_format is ClassifiedFormat.PDF


def test_the_extension_is_matched_case_insensitively() -> None:
    classification = classify_document_format(filename="LAYOUT.DWG")

    assert classification.detected_format is ClassifiedFormat.DWG


def test_mime_and_extension_agreeing_classifies_by_the_stronger_of_them(
) -> None:
    classification = classify_document_format(
        declared_mime_type="application/pdf", filename="report.pdf"
    )

    assert classification.decided_by is FormatEvidenceKind.DECLARED_MIME_TYPE


# --- Deadlock and silence ----------------------------------------------


def test_mime_and_extension_disagreeing_produces_conflicting() -> None:
    """Neither is a fact *from* the file, so neither can arbitrate the
    other. Choosing one would be the arbitrary classification this
    milestone forbids."""

    classification = classify_document_format(
        declared_mime_type="application/pdf", filename="layout.dwg"
    )

    assert classification.outcome is FormatClassificationOutcome.CONFLICTING
    assert classification.detected_format is None
    assert classification.decided_by is None


def test_no_evidence_at_all_produces_unknown() -> None:
    classification = classify_document_format()

    assert classification.outcome is FormatClassificationOutcome.UNKNOWN
    assert classification.detected_format is None


def test_an_unrecognised_extension_alone_produces_unknown() -> None:
    classification = classify_document_format(filename="notes.qzx")

    assert classification.outcome is FormatClassificationOutcome.UNKNOWN


def test_unclassifiable_content_falls_through_to_the_weaker_sources(
) -> None:
    classification = classify_document_format(
        content_prefix=b"not a signature at all", filename="notes.pdf"
    )

    assert classification.detected_format is ClassifiedFormat.PDF
    assert classification.decided_by is FormatEvidenceKind.FILENAME_EXTENSION


def test_a_container_signature_abstains_rather_than_guessing() -> None:
    """xlsx and docx are both ZIP archives: the header says "this is a
    ZIP", not "this is a spreadsheet". The classifier says so and lets the
    filename decide."""

    classification = classify_document_format(
        content_prefix=ZIP_BYTES, filename="cable_list.xlsx"
    )

    assert classification.detected_format is ClassifiedFormat.XLSX
    assert classification.decided_by is FormatEvidenceKind.FILENAME_EXTENSION


def test_a_container_signature_with_no_other_evidence_is_unknown() -> None:
    classification = classify_document_format(content_prefix=ZIP_BYTES)

    assert classification.outcome is FormatClassificationOutcome.UNKNOWN


def test_every_classification_records_all_three_sources() -> None:
    """Whatever the verdict, the record shows what each source said -
    including "no MIME type was declared", which is itself evidence."""

    classification = classify_document_format(content_prefix=PDF_BYTES)

    assert [evidence.kind for evidence in classification.evidence] == [
        FormatEvidenceKind.CONTENT_SIGNATURE,
        FormatEvidenceKind.DECLARED_MIME_TYPE,
        FormatEvidenceKind.FILENAME_EXTENSION,
    ]


# --- Determinism -------------------------------------------------------


def test_the_same_inputs_always_produce_the_same_classification() -> None:
    arguments = {
        "content_prefix": PDF_BYTES,
        "declared_mime_type": "application/pdf",
        "filename": "report.pdf",
    }

    first = classify_document_format(**arguments)
    second = classify_document_format(**arguments)

    assert first == second


def test_the_classification_does_not_depend_on_the_filename_when_signed(
) -> None:
    signed = classify_document_format(content_prefix=PDF_BYTES)
    renamed = classify_document_format(
        content_prefix=PDF_BYTES, filename="anything_at_all.bin"
    )

    assert signed.detected_format is renamed.detected_format
