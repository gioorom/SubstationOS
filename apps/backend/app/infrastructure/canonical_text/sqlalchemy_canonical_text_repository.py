from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
    CanonicalTextLine,
    CanonicalTextParagraph,
    CanonicalTextSection,
    CanonicalTextToken,
    SpanProvenance,
)
from app.domain.canonical_text.canonical_text_repository import (
    CanonicalTextRepository,
)
from app.models.canonical_text import (
    CanonicalTextDocumentRecord,
    CanonicalTextLineRecord,
    CanonicalTextParagraphRecord,
    CanonicalTextSectionRecord,
    CanonicalTextTokenRecord,
)


class SqlAlchemyCanonicalTextRepository(CanonicalTextRepository):
    """
    SQLAlchemy adapter over the five canonical-text tables.

    Writes only those tables. It holds no reference to the canonical
    representation's tables, to the document row, or to stored content of
    any kind - a segmentation is derived *from* a representation, and
    deriving something must never modify what it was derived from.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, segmentation: CanonicalTextDocument) -> None:
        record = CanonicalTextDocumentRecord(
            document_id=segmentation.document_id,
            content_checksum=segmentation.content_checksum,
            representation_version=segmentation.representation_version,
            segmentation_version=segmentation.segmentation_version,
            section_count=segmentation.section_count,
            token_count=segmentation.token_count,
        )

        for section in segmentation.sections:
            record.sections.append(_section_record(section))

        self._session.add(record)
        self._session.commit()

    def find_for_representation(
        self,
        document_id: int,
        content_checksum: str,
        segmentation_version: str,
    ) -> CanonicalTextDocument | None:
        record = (
            self._session.query(CanonicalTextDocumentRecord)
            .filter(
                CanonicalTextDocumentRecord.document_id == document_id,
                CanonicalTextDocumentRecord.content_checksum
                == content_checksum,
                CanonicalTextDocumentRecord.segmentation_version
                == segmentation_version,
            )
            .order_by(CanonicalTextDocumentRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> CanonicalTextDocument | None:
        record = (
            self._session.query(CanonicalTextDocumentRecord)
            .filter(CanonicalTextDocumentRecord.document_id == document_id)
            .order_by(CanonicalTextDocumentRecord.id.desc())
            .first()
        )

        return _to_domain(record) if record is not None else None


# --- Mapping ----------------------------------------------------------


def _section_record(
    section: CanonicalTextSection,
) -> CanonicalTextSectionRecord:
    record = CanonicalTextSectionRecord(
        section_index=section.section_index,
        page_number=section.page_number,
    )

    for paragraph in section.paragraphs:
        record.paragraphs.append(_paragraph_record(paragraph))

    return record


def _paragraph_record(
    paragraph: CanonicalTextParagraph,
) -> CanonicalTextParagraphRecord:
    record = CanonicalTextParagraphRecord(
        paragraph_index=paragraph.paragraph_index,
        page_number=paragraph.page_number,
        block_reading_order=paragraph.block_reading_order,
    )

    for line in paragraph.lines:
        record.lines.append(_line_record(line))

    return record


def _line_record(line: CanonicalTextLine) -> CanonicalTextLineRecord:
    record = CanonicalTextLineRecord(line_index=line.line_index)

    for token in line.tokens:
        record.tokens.append(_token_record(token))

    return record


def _token_record(token: CanonicalTextToken) -> CanonicalTextTokenRecord:
    return CanonicalTextTokenRecord(
        position=token.position,
        text=token.text,
        normalized_text=token.normalized_text,
        page_number=token.provenance.page_number,
        block_reading_order=token.provenance.block_reading_order,
        span_reading_order=token.provenance.span_reading_order,
        line_index=token.provenance.line_index,
        character_start=token.provenance.character_start,
        character_end=token.provenance.character_end,
    )


def _to_domain(
    record: CanonicalTextDocumentRecord,
) -> CanonicalTextDocument:
    return CanonicalTextDocument(
        document_id=record.document_id,
        content_checksum=record.content_checksum,
        representation_version=record.representation_version,
        segmentation_version=record.segmentation_version,
        sections=tuple(
            CanonicalTextSection(
                section_index=section.section_index,
                page_number=section.page_number,
                paragraphs=tuple(
                    CanonicalTextParagraph(
                        paragraph_index=paragraph.paragraph_index,
                        page_number=paragraph.page_number,
                        block_reading_order=paragraph.block_reading_order,
                        lines=tuple(
                            CanonicalTextLine(
                                line_index=line.line_index,
                                tokens=tuple(
                                    CanonicalTextToken(
                                        position=token.position,
                                        text=token.text,
                                        normalized_text=(
                                            token.normalized_text
                                        ),
                                        provenance=SpanProvenance(
                                            page_number=token.page_number,
                                            block_reading_order=(
                                                token.block_reading_order
                                            ),
                                            span_reading_order=(
                                                token.span_reading_order
                                            ),
                                            line_index=token.line_index,
                                            character_start=(
                                                token.character_start
                                            ),
                                            character_end=(
                                                token.character_end
                                            ),
                                        ),
                                    )
                                    for token in line.tokens
                                ),
                            )
                            for line in paragraph.lines
                        ),
                    )
                    for paragraph in section.paragraphs
                ),
            )
            for section in record.sections
        ),
    )
