from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.canonical_text.canonical_text_failures import (
    SegmentationFailureCode,
)

# --- Response ------------------------------------------------------------


class SpanProvenanceRead(BaseModel):
    """The chain back to the canonical representation: which page, which
    block, which span, which characters of it."""

    page_number: int
    block_reading_order: int
    span_reading_order: int
    line_index: int
    character_start: int
    character_end: int

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextTokenRead(BaseModel):
    """``text`` is the original substring; ``normalized_text`` is its
    deterministic normalisation. Both are exposed - neither substitutes
    for the other."""

    position: int
    text: str
    normalized_text: str
    provenance: SpanProvenanceRead

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextLineRead(BaseModel):
    line_index: int
    tokens: tuple[CanonicalTextTokenRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextParagraphRead(BaseModel):
    """One PDF block, as the parser delimited it - not a semantic
    paragraph."""

    paragraph_index: int
    page_number: int
    block_reading_order: int
    lines: tuple[CanonicalTextLineRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextSectionRead(BaseModel):
    """One page. Deliberately not a chapter, heading or engineering
    section - ``page_number`` says exactly what it is."""

    section_index: int
    page_number: int
    paragraphs: tuple[CanonicalTextParagraphRead, ...]

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextSummaryRead(BaseModel):
    """
    What a segmentation *is*, without its contents.

    The provenance fields are the point: which representation, and under
    which segmentation rules.
    """

    document_id: int
    content_checksum: str
    representation_version: str
    segmentation_version: str
    section_count: int
    token_count: int

    model_config = ConfigDict(from_attributes=True)


class CanonicalTextRead(CanonicalTextSummaryRead):
    """The full segmentation, sections and all."""

    sections: tuple[CanonicalTextSectionRead, ...]

    model_config = ConfigDict(from_attributes=True)


class SegmentationFailureRead(BaseModel):
    code: SegmentationFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class SegmentationResultRead(BaseModel):
    """``reused`` is ``true`` when this representation was already
    segmented under these rules and nothing was recomputed - the
    observable proof that segmentation is idempotent."""

    succeeded: bool
    reused: bool
    segmentation: CanonicalTextSummaryRead | None
    failure: SegmentationFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "SegmentationResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            segmentation=(
                None
                if result.segmentation is None
                else CanonicalTextSummaryRead.model_validate(
                    result.segmentation
                )
            ),
            failure=(
                None
                if result.failure is None
                else SegmentationFailureRead.model_validate(result.failure)
            ),
        )
