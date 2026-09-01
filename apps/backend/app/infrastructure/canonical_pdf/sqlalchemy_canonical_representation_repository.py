from __future__ import annotations

from dataclasses import replace

from sqlalchemy.orm import Session

from app.domain.canonical_pdf import canonical_pdf_factory
from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalBlockKind,
    CanonicalPdfDocument,
)
from app.domain.canonical_pdf.canonical_representation_repository import (
    CanonicalRepresentationRepository,
)
from app.models.canonical_pdf import (
    CanonicalPdfBlockRecord,
    CanonicalPdfPageRecord,
    CanonicalPdfRepresentation,
    CanonicalPdfSpanRecord,
)


class SqlAlchemyCanonicalRepresentationRepository(
    CanonicalRepresentationRepository
):
    """
    SQLAlchemy adapter over the four canonical-representation tables.

    Writes only those tables. It holds no reference to the document row,
    to `Document.file_path`, or to stored content of any kind - the
    original PDF is authoritative and this adapter has no way to touch
    it.

    On read it rebuilds the value objects **through the domain factory**,
    so a row that somehow violates an invariant is refused on the way out
    exactly as it would have been on the way in. A representation is
    trusted by every future extractor; it should never be trusted merely
    because it is old.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, representation: CanonicalPdfDocument) -> None:
        record = CanonicalPdfRepresentation(
            artifact_identity=representation.artifact_identity,
            upstream_identity=representation.upstream_identity,
            document_id=representation.document_id,
            content_checksum=representation.content_checksum,
            checksum_algorithm=representation.checksum_algorithm,
            representation_version=representation.representation_version,
            parser_name=representation.parser_name,
            parser_version=representation.parser_version,
            page_count=representation.page_count,
        )

        for page in representation.pages:
            page_record = CanonicalPdfPageRecord(
                page_number=page.page_number,
                width=page.width,
                height=page.height,
            )

            for block in page.blocks:
                block_record = CanonicalPdfBlockRecord(
                    reading_order=block.reading_order,
                    kind=block.kind,
                    x0=block.bounding_box.x0,
                    y0=block.bounding_box.y0,
                    x1=block.bounding_box.x1,
                    y1=block.bounding_box.y1,
                )

                for span in block.spans:
                    block_record.spans.append(
                        CanonicalPdfSpanRecord(
                            reading_order=span.reading_order,
                            line_index=span.line_index,
                            text=span.text,
                            x0=span.bounding_box.x0,
                            y0=span.bounding_box.y0,
                            x1=span.bounding_box.x1,
                            y1=span.bounding_box.y1,
                            font_family=span.style.font_family,
                            font_size=span.style.font_size,
                            bold=span.style.bold,
                            italic=span.style.italic,
                        )
                    )

                page_record.blocks.append(block_record)

            record.pages.append(page_record)

        self._session.add(record)
        self._session.commit()

    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> CanonicalPdfDocument | None:
        record = (
            self._session.query(CanonicalPdfRepresentation)
            .filter(
                CanonicalPdfRepresentation.document_id == document_id,
                CanonicalPdfRepresentation.artifact_identity
                == artifact_identity,
            )
            .one_or_none()
        )

        return self._to_domain(record) if record is not None else None

    def find_latest_for_document(
        self, document_id: int
    ) -> CanonicalPdfDocument | None:
        record = (
            self._session.query(CanonicalPdfRepresentation)
            .filter(CanonicalPdfRepresentation.document_id == document_id)
            .order_by(CanonicalPdfRepresentation.id.desc())
            .first()
        )

        return self._to_domain(record) if record is not None else None

    # --- Mapping ------------------------------------------------------

    @staticmethod
    def _to_domain(
        record: CanonicalPdfRepresentation,
    ) -> CanonicalPdfDocument:
        built = canonical_pdf_factory.build_document(
            document_id=record.document_id,
            content_checksum=record.content_checksum,
            checksum_algorithm=record.checksum_algorithm,
            representation_version=record.representation_version,
            parser_name=record.parser_name,
            parser_version=record.parser_version,
            pages=tuple(
                canonical_pdf_factory.build_page(
                    page_number=page.page_number,
                    width=page.width,
                    height=page.height,
                    blocks=tuple(
                        canonical_pdf_factory.build_block(
                            reading_order=block.reading_order,
                            kind=CanonicalBlockKind(block.kind),
                            bounding_box=(
                                canonical_pdf_factory.build_bounding_box(
                                    block.x0, block.y0, block.x1, block.y1
                                )
                            ),
                            spans=tuple(
                                canonical_pdf_factory.build_span(
                                    reading_order=span.reading_order,
                                    line_index=span.line_index,
                                    text=span.text,
                                    bounding_box=(
                                        canonical_pdf_factory
                                        .build_bounding_box(
                                            span.x0,
                                            span.y0,
                                            span.x1,
                                            span.y1,
                                        )
                                    ),
                                    font_family=span.font_family,
                                    font_size=span.font_size,
                                    bold=span.bold,
                                    italic=span.italic,
                                )
                                for span in block.spans
                            ),
                        )
                        for block in page.blocks
                    ),
                )
                for page in record.pages
            ),
        )

        # The factory validates the representation; identity is
        # provenance recorded about it, not something it validates.
        return replace(
            built,
            artifact_identity=record.artifact_identity,
            upstream_identity=record.upstream_identity,
        )
