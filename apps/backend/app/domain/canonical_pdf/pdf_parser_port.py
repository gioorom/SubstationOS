"""
The PDF parsing port (Milestone 26.1).

The domain declares *what a parse produces*; an infrastructure adapter
decides *which library produces it*. That boundary is the point: PDF
parsing is the most library-coupled step in this system, and confining it
to one adapter behind one contract means replacing PyMuPDF later is a
re-canonicalisation, not a rewrite.

**The port takes bytes, not a path.** The adapter therefore cannot open a
file, walk a directory or reach storage at all - the bytes arrive through
Milestone 25.2's ``DocumentContentPort``, which stays the one governed way
into stored content. It also makes the parser trivially testable against
literal bytes.

An implementation **must not** perform OCR, must not sort, merge or repair
anything, and must not raise: every failure is returned as a typed
``PdfParseResult`` so the caller records a cause rather than catching
whatever a library chose to throw.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailure,
)
from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalPdfDocument,
)


@dataclass(frozen=True, slots=True)
class PdfParseResult:
    """Either a ``document`` or a ``failure`` - never both, never
    neither."""

    parsed: bool
    document: CanonicalPdfDocument | None = None
    failure: CanonicalizationFailure | None = None


class PdfParserPort(ABC):
    """Turns the bytes of a PDF into a canonical representation."""

    @property
    @abstractmethod
    def parser_name(self) -> str:
        """The library's name, recorded on every representation it
        produces so "which parser produced this text?" is answerable
        years later without guessing."""

        raise NotImplementedError

    @property
    @abstractmethod
    def parser_version(self) -> str:
        """The library's version, recorded for the same reason. Two
        parser versions can legitimately disagree about a difficult PDF;
        an undated representation makes that disagreement invisible."""

        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        content: bytes,
        *,
        document_id: int,
        content_checksum: str,
        checksum_algorithm: str,
    ) -> PdfParseResult:
        """
        Parse ``content`` into a ``CanonicalPdfDocument``.

        Deterministic: the same bytes must always produce an equal
        representation. Implementations therefore preserve the parser's
        own ordering and must not apply geometric sorting, which would
        make the output depend on tie-breaking rather than on the
        document.

        Returns a typed failure - encrypted, corrupted, empty, or a
        parser fault - rather than raising. The checksum is carried
        through rather than recomputed here: this port receives bytes and
        has no way to know they are the bytes anybody identified.
        """

        raise NotImplementedError
