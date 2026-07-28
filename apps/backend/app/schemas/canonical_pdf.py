from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailureCode,
)
from app.domain.canonical_pdf.canonical_pdf_models import CanonicalBlockKind

# --- Response ------------------------------------------------------------


class BoundingBoxRead(BaseModel):
    """PDF user-space points, origin top-left - the parser's own
    convention, unconverted."""

    x0: float
    y0: float
    x1: float
    y1: float

    model_config = ConfigDict(from_attributes=True)


class TextStyleRead(BaseModel):
    font_family: str
    font_size: float
    bold: bool
    italic: bool

    model_config = ConfigDict(from_attributes=True)


class CanonicalPdfSpanRead(BaseModel):
    """``text`` is verbatim - not stripped, normalised or repaired."""

    reading_order: int
    line_index: int
    text: str
    bounding_box: BoundingBoxRead
    style: TextStyleRead

    model_config = ConfigDict(from_attributes=True)


class CanonicalPdfBlockRead(BaseModel):
    """``reading_order`` is the parser's own index, not an order this
    system inferred."""

    reading_order: int
    kind: CanonicalBlockKind
    bounding_box: BoundingBoxRead
    spans: tuple[CanonicalPdfSpanRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalPdfPageRead(BaseModel):
    page_number: int
    width: float
    height: float
    blocks: tuple[CanonicalPdfBlockRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalRepresentationSummaryRead(BaseModel):
    """
    What a representation *is*, without its contents.

    The provenance fields are the point: which bytes, which parser, which
    representation contract. A representation whose provenance is unknown
    cannot be trusted years later.
    """

    document_id: int
    content_checksum: str
    checksum_algorithm: str
    representation_version: str
    parser_name: str
    parser_version: str
    page_count: int

    model_config = ConfigDict(from_attributes=True)


class CanonicalRepresentationRead(CanonicalRepresentationSummaryRead):
    """The full representation, pages and all."""

    pages: tuple[CanonicalPdfPageRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalizationFailureRead(BaseModel):
    code: CanonicalizationFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class CanonicalizationResultRead(BaseModel):
    """
    One canonicalisation's outcome.

    ``reused`` is ``true`` when identical bytes already had a
    representation and nothing was re-parsed - the observable proof that
    canonicalisation is idempotent.
    """

    succeeded: bool
    reused: bool
    representation: CanonicalRepresentationSummaryRead | None
    failure: CanonicalizationFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "CanonicalizationResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            representation=(
                None
                if result.representation is None
                else CanonicalRepresentationSummaryRead.model_validate(
                    result.representation
                )
            ),
            failure=(
                None
                if result.failure is None
                else CanonicalizationFailureRead.model_validate(
                    result.failure
                )
            ),
        )
