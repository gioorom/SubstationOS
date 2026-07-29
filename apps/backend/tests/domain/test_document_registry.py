"""
The Document Registry domain: query vocabulary and download naming.

The download-name tests are the security-critical ones. A stored
filename is user-supplied text that ends up in an HTTP header, so both
path traversal and header injection live in that string.
"""

from __future__ import annotations

import pytest

from app.domain.document_registry.document_download import (
    FALLBACK_FILENAME,
    MAX_FILENAME_LENGTH,
    DocumentDownload,
    safe_download_filename,
)
from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentDetail,
    DocumentFormat,
    DocumentSummary,
    media_type_for,
)
from app.domain.document_registry.document_query import (
    DEFAULT_DOCUMENT_DIRECTION,
    DEFAULT_DOCUMENT_SORT,
    DocumentQuery,
    DocumentSearchTerm,
    DocumentSortField,
)
from app.domain.project.project_query import ProjectSearchTerm
from app.domain.shared_kernel.pagination import PageRequest, SortDirection


# --- Search terms ---------------------------------------------------------


@pytest.mark.parametrize(
    "term_type", [DocumentSearchTerm, ProjectSearchTerm]
)
def test_a_search_term_is_trimmed(term_type) -> None:
    assert term_type.of("  TR1  ").value == "TR1"


@pytest.mark.parametrize(
    "term_type", [DocumentSearchTerm, ProjectSearchTerm]
)
def test_internal_whitespace_is_preserved(term_type) -> None:
    """Collapsing it would be a normalisation nobody asked for: "CP 01"
    must not match "CP01"."""

    assert term_type.of("  CP 01  ").value == "CP 01"


@pytest.mark.parametrize(
    "term_type", [DocumentSearchTerm, ProjectSearchTerm]
)
@pytest.mark.parametrize("raw", [None, "", "   ", "\t\n"])
def test_an_empty_term_is_the_absence_of_a_search(term_type, raw) -> None:
    """Not a filter that matches everything - no filter at all."""

    assert term_type.of(raw) is None


# --- Query defaults -------------------------------------------------------


def test_a_document_query_defaults_to_newest_first() -> None:
    """A registry is read to find recent work far more often than to read
    it alphabetically."""

    query = DocumentQuery(page=PageRequest())

    assert query.sort_by is DocumentSortField.UPLOADED_AT
    assert query.direction is SortDirection.DESCENDING
    assert DEFAULT_DOCUMENT_SORT is DocumentSortField.UPLOADED_AT
    assert DEFAULT_DOCUMENT_DIRECTION is SortDirection.DESCENDING


def test_every_query_filter_is_optional() -> None:
    query = DocumentQuery(page=PageRequest())

    assert query.project_id is None
    assert query.scope is None
    assert query.document_format is None
    assert query.category is None
    assert query.search is None


def test_the_sort_vocabulary_is_closed_and_small() -> None:
    """Adding a member is a deliberate act with a test behind it - not
    something a caller can do by sending a different string."""

    assert {member.value for member in DocumentSortField} == {
        "uploaded_at",
        "filename",
        "revision",
        "document_format",
    }


# --- Media types ----------------------------------------------------------


def test_every_format_has_a_media_type() -> None:
    for document_format in DocumentFormat:
        assert media_type_for(document_format)


def test_an_unclassified_document_is_a_generic_stream() -> None:
    """Telling a browser a file is a PDF when nobody established that is
    a worse answer than telling it nothing."""

    assert (
        media_type_for(DocumentFormat.OTHER) == "application/octet-stream"
    )


# --- Download filenames ---------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "../../../etc/passwd",
        "..\\..\\windows\\system32\\config\\sam",
        "/etc/shadow",
        "C:\\Windows\\notepad.exe",
        "....//....//etc/passwd",
    ],
)
def test_a_traversal_filename_cannot_survive(filename: str) -> None:
    safe = safe_download_filename(filename)

    assert ".." not in safe
    assert "/" not in safe
    assert "\\" not in safe


@pytest.mark.parametrize(
    "filename",
    [
        'evil";\r\nX-Injected: yes',
        "line\nbreak.pdf",
        "carriage\rreturn.pdf",
        'quote".pdf',
    ],
)
def test_a_header_injection_cannot_survive(filename: str) -> None:
    safe = safe_download_filename(filename)

    for dangerous in ('"', "\r", "\n", ";"):
        assert dangerous not in safe


def test_an_ordinary_filename_is_left_recognisable() -> None:
    """Sanitising must not rename people's documents beyond recognition."""

    assert (
        safe_download_filename("schema-funzionale_rev-02.pdf")
        == "schema-funzionale_rev-02.pdf"
    )


def test_accents_are_transliterated_not_dropped_wholesale() -> None:
    assert safe_download_filename("schéma.pdf") == "schema.pdf"


def test_a_filename_that_sanitises_to_nothing_gets_a_fallback() -> None:
    """A document called "../../" is still downloadable; it just is not
    called that."""

    assert safe_download_filename("../../") == FALLBACK_FILENAME
    assert safe_download_filename("") == FALLBACK_FILENAME
    assert safe_download_filename("...") == FALLBACK_FILENAME


def test_a_leading_dot_cannot_make_a_hidden_file() -> None:
    assert not safe_download_filename(".bashrc").startswith(".")


def test_a_very_long_filename_is_truncated() -> None:
    safe = safe_download_filename("a" * 500 + ".pdf")

    assert len(safe) <= MAX_FILENAME_LENGTH


def test_the_download_disposition_is_always_an_attachment() -> None:
    download = DocumentDownload.of(
        document_id=1,
        storage_reference="anything-opaque",
        filename="schema.pdf",
        document_format=DocumentFormat.PDF,
        size_bytes=100,
    )

    assert download.content_disposition == (
        'attachment; filename="schema.pdf"'
    )
    assert "inline" not in download.content_disposition


def test_the_download_carries_the_media_type_for_its_format() -> None:
    download = DocumentDownload.of(
        document_id=1,
        storage_reference="opaque",
        filename="layout.dwg",
        document_format=DocumentFormat.DWG,
        size_bytes=10,
    )

    assert download.media_type == media_type_for(DocumentFormat.DWG)


# --- Value objects --------------------------------------------------------


def _detail(**overrides) -> DocumentDetail:
    from datetime import datetime

    from app.domain.project.project_document_scope import DocumentScope

    fields = {
        "document_id": 1,
        "project_id": 2,
        "project_name": "Cabina Gamma",
        "filename": "schema.pdf",
        "document_format": DocumentFormat.PDF,
        "category": DocumentCategory.FUNCTIONAL_SCHEMATIC,
        "revision": "00",
        "scope": DocumentScope.PROJECT,
        "uploaded_at": datetime(2026, 7, 1, 9, 0),
        "content_checksum": "a" * 64,
        "checksum_algorithm": "sha256",
        "size_bytes": 1024,
        "content_available": True,
        "ingestion_state": "processed",
        "ingestion_outcome": "ready_for_extraction",
    }
    fields.update(overrides)

    return DocumentDetail(**fields)


def test_a_detail_can_narrow_itself_to_a_summary() -> None:
    summary = _detail().summary

    assert isinstance(summary, DocumentSummary)
    assert summary.document_id == 1
    assert summary.filename == "schema.pdf"


def test_no_registry_value_object_has_a_storage_field() -> None:
    """The structural guarantee: a schema cannot leak what its source
    value object does not have."""

    for value_object in (_detail(), _detail().summary):
        for field in value_object.__slots__:
            assert "path" not in field
            assert "storage" not in field


def test_a_download_is_the_one_carrier_of_a_storage_reference() -> None:
    """It has one because the transport must hand it back to the content
    port - and a test asserts it never reaches a response."""

    download = DocumentDownload.of(
        document_id=1,
        storage_reference="opaque",
        filename="a.pdf",
        document_format=DocumentFormat.PDF,
        size_bytes=1,
    )

    assert download.storage_reference == "opaque"
