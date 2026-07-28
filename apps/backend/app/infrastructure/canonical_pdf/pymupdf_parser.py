"""
The PyMuPDF adapter behind ``PdfParserPort`` (Milestone 26.1).

The **only** module in this system that knows what a PDF is made of.
Everything else - the domain, the service, the API, every future
extractor - deals in canonical value objects, so replacing this library
means rewriting this file and re-canonicalising, and touching nothing
else.

## What it does

Walks PyMuPDF's own structure (page → block → line → span) and records
it. The parser's block order is preserved exactly as produced: no
``sort=True``, no geometric re-ordering. On a multi-column wiring
schedule, a re-ordering heuristic would be this system asserting how the
page should be read, which is precisely the kind of confident guess that
produces plausible nonsense three milestones downstream.

Lines are flattened into spans, as the canonical hierarchy requires, but
each span keeps its ``line_index`` so the parser's own grouping is not
lost - reconstructing it later from coordinates would be inference.

## What it does not do

No OCR - a page of scanned images yields no spans, and that is reported
rather than papered over. No text repair, no de-hyphenation, no
whitespace normalisation, no merging of adjacent spans that happen to
share a font. No file access of any kind: it receives bytes.

It never raises. Every library failure is mapped onto a typed cause, so
the caller records *why* rather than catching whatever the library chose
to throw this release.
"""

from __future__ import annotations

import fitz

from app.domain.canonical_pdf import canonical_pdf_factory
from app.domain.canonical_pdf.canonical_pdf_exceptions import (
    InvalidCanonicalRepresentationError,
)
from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailure,
    CanonicalizationFailureCode,
)
from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalBlockKind,
    CanonicalPdfBlock,
    CanonicalPdfPage,
    CanonicalPdfSpan,
)
from app.domain.canonical_pdf.canonical_pdf_policy import (
    CANONICAL_REPRESENTATION_VERSION,
)
from app.domain.canonical_pdf.pdf_parser_port import (
    PdfParseResult,
    PdfParserPort,
)

PARSER_NAME = "pymupdf"

# PyMuPDF's documented font flag bits. Read from the parser's own flags
# rather than sniffed from the font name: a font called "ArialBold" is
# a string, while flag bit 4 is what the parser actually determined.
_FLAG_ITALIC = 1 << 1
_FLAG_BOLD = 1 << 4

# PyMuPDF block types.
_BLOCK_TYPE_TEXT = 0


class PyMuPdfParser(PdfParserPort):
    """``PdfParserPort`` implemented with PyMuPDF."""

    @property
    def parser_name(self) -> str:
        return PARSER_NAME

    @property
    def parser_version(self) -> str:
        return fitz.VersionBind

    def parse(
        self,
        content: bytes,
        *,
        document_id: int,
        content_checksum: str,
        checksum_algorithm: str,
    ) -> PdfParseResult:
        if not content:
            return _failed(
                CanonicalizationFailureCode.EMPTY_CONTENT,
                f"Document '{document_id}' has no bytes to parse.",
            )

        try:
            document = fitz.open(stream=content, filetype="pdf")
        except (fitz.FileDataError, fitz.EmptyFileError) as error:
            return _failed(
                CanonicalizationFailureCode.CORRUPTED_DOCUMENT,
                f"Document '{document_id}' could not be opened as a PDF.",
                detail=str(error),
            )
        except (RuntimeError, ValueError) as error:
            return _failed(
                CanonicalizationFailureCode.PARSER_FAILURE,
                f"The PDF parser failed to open document "
                f"'{document_id}'.",
                detail=str(error),
            )

        try:
            return self._parse_open_document(
                document,
                document_id=document_id,
                content_checksum=content_checksum,
                checksum_algorithm=checksum_algorithm,
            )
        finally:
            document.close()

    def _parse_open_document(
        self,
        document: fitz.Document,
        *,
        document_id: int,
        content_checksum: str,
        checksum_algorithm: str,
    ) -> PdfParseResult:
        if document.needs_pass:
            # Encrypted, and distinct from corrupted: the bytes are
            # intact and someone with the password could read them. That
            # is a question for whoever supplied the file, not a
            # data-integrity fault, and there is no password to try -
            # this system does not hold one and must not guess.
            return _failed(
                CanonicalizationFailureCode.ENCRYPTED_DOCUMENT,
                f"Document '{document_id}' is password-protected.",
            )

        if document.page_count == 0:
            return _failed(
                CanonicalizationFailureCode.EMPTY_DOCUMENT,
                f"Document '{document_id}' is a valid PDF carrying no "
                "pages.",
            )

        try:
            pages = tuple(
                _build_page(page_number, document[page_number - 1])
                for page_number in range(1, document.page_count + 1)
            )
        except InvalidCanonicalRepresentationError as error:
            # The parser produced something the model refuses. Recorded
            # as a parser failure rather than silently corrected: a
            # representation quietly repaired into shape would be trusted
            # by every future extractor.
            return _failed(
                CanonicalizationFailureCode.PARSER_FAILURE,
                f"The parser produced an invalid representation of "
                f"document '{document_id}'.",
                detail=error.detail,
            )
        except (RuntimeError, ValueError) as error:
            return _failed(
                CanonicalizationFailureCode.PARSER_FAILURE,
                f"The PDF parser failed while reading document "
                f"'{document_id}'.",
                detail=str(error),
            )

        return PdfParseResult(
            parsed=True,
            document=canonical_pdf_factory.build_document(
                document_id=document_id,
                content_checksum=content_checksum,
                checksum_algorithm=checksum_algorithm,
                representation_version=CANONICAL_REPRESENTATION_VERSION,
                parser_name=PARSER_NAME,
                parser_version=fitz.VersionBind,
                pages=pages,
            ),
        )


def _build_page(page_number: int, page: fitz.Page) -> CanonicalPdfPage:
    raw = page.get_text("dict")

    return canonical_pdf_factory.build_page(
        page_number=page_number,
        width=float(raw["width"]),
        height=float(raw["height"]),
        blocks=tuple(
            _build_block(reading_order, raw_block)
            for reading_order, raw_block in enumerate(raw["blocks"])
        ),
    )


def _build_block(reading_order: int, raw_block: dict) -> CanonicalPdfBlock:
    is_text = raw_block["type"] == _BLOCK_TYPE_TEXT

    return canonical_pdf_factory.build_block(
        reading_order=reading_order,
        kind=(
            CanonicalBlockKind.TEXT if is_text else CanonicalBlockKind.IMAGE
        ),
        bounding_box=_bounding_box(raw_block["bbox"]),
        spans=_build_spans(raw_block) if is_text else (),
    )


def _build_spans(raw_block: dict) -> tuple[CanonicalPdfSpan, ...]:
    """Lines are flattened into a single span sequence, in the parser's
    order, with each span remembering the line it came from."""

    spans: list[CanonicalPdfSpan] = []

    for line_index, raw_line in enumerate(raw_block.get("lines", ())):
        for raw_span in raw_line.get("spans", ()):
            flags = int(raw_span["flags"])

            spans.append(
                canonical_pdf_factory.build_span(
                    reading_order=len(spans),
                    line_index=line_index,
                    text=raw_span["text"],
                    bounding_box=_bounding_box(raw_span["bbox"]),
                    font_family=raw_span["font"],
                    font_size=float(raw_span["size"]),
                    bold=bool(flags & _FLAG_BOLD),
                    italic=bool(flags & _FLAG_ITALIC),
                )
            )

    return tuple(spans)


def _bounding_box(raw_bbox):
    x0, y0, x1, y1 = raw_bbox

    return canonical_pdf_factory.build_bounding_box(
        float(x0), float(y0), float(x1), float(y1)
    )


def _failed(
    code: CanonicalizationFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> PdfParseResult:
    return PdfParseResult(
        parsed=False,
        failure=CanonicalizationFailure(
            code=code, message=message, detail=detail
        ),
    )
