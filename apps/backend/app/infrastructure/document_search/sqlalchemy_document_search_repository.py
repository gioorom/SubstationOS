from __future__ import annotations

import json

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.sql import ColumnElement
from sqlalchemy.orm import Session

from app.database.session_commit import commit_or_restore
from app.domain.document_search.search_exceptions import (
    UnknownSegmentKindError,
)
from app.domain.document_search.search_models import (
    SearchHit,
    SearchPage,
    SearchSegment,
    SegmentKind,
    SegmentLocation,
)
from app.domain.document_search.search_normalization import (
    containment_pattern,
    normalize,
)
from app.domain.document_search.search_repository import (
    DocumentSearchRepository,
)
from app.models.document import Document
from app.models.document_search import DocumentSearchSegment


class SqlAlchemyDocumentSearchRepository(DocumentSearchRepository):
    """
    SQLAlchemy adapter over ``document_search_segments``.

    Writes only that table. It reads the ``documents`` table to name a
    hit's document, and reads nothing else: the index is a projection,
    and a projection that could write back to what it was projected
    from would stop being one.

    Every read is filtered by ``project_id`` inside the statement. The
    filter is not applied to results afterwards, so there is no moment
    at which rows from another project exist in memory and could be
    returned by a later mistake.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_document(
        self, document_id: int, segments: tuple[SearchSegment, ...]
    ) -> int:
        self._forget(document_id)

        for segment in segments:
            self._session.add(_record(segment))

        commit_or_restore(self._session)

        return len(segments)

    def _forget(self, document_id: int) -> int:
        """Delete this document's rows without committing."""

        return (
            self._session.query(DocumentSearchSegment)
            .filter(DocumentSearchSegment.document_id == document_id)
            .delete(synchronize_session=False)
        )

    def search(
        self,
        *,
        project_id: int,
        terms: tuple[str, ...],
        limit: int,
        offset: int,
    ) -> SearchPage:
        if not terms:
            return SearchPage(hits=(), total_segments=0, total_documents=0)

        condition = self._matching(project_id, terms)

        total_segments = self._session.scalar(
            select(func.count())
            .select_from(DocumentSearchSegment)
            .where(condition)
        )
        total_documents = self._session.scalar(
            select(func.count(distinct(DocumentSearchSegment.document_id)))
            .where(condition)
        )

        rows = self._session.execute(
            select(DocumentSearchSegment, Document.filename)
            .join(Document, Document.id == DocumentSearchSegment.document_id)
            .where(condition)
            .order_by(*_READING_ORDER)
            .limit(limit)
            .offset(offset)
        ).all()

        return SearchPage(
            hits=tuple(_hit(record, filename) for record, filename in rows),
            total_segments=int(total_segments or 0),
            total_documents=int(total_documents or 0),
        )

    def terms_present(
        self, *, project_id: int, candidates: tuple[str, ...]
    ) -> frozenset[str]:
        if not candidates:
            return frozenset()

        present: set[str] = set()

        # One statement rather than one per candidate. Each pattern is a
        # scan of this project's text - ``LIKE '% term %'`` leads with a
        # wildcard and no index can serve it - so asking separately
        # would multiply the cost of the one case this is used for: a
        # query that already found nothing.
        rows = self._session.execute(
            select(DocumentSearchSegment.normalized_text).where(
                DocumentSearchSegment.project_id == project_id,
                or_(
                    *(
                        DocumentSearchSegment.normalized_text.like(
                            containment_pattern(candidate)
                        )
                        for candidate in candidates
                    )
                ),
            )
        ).scalars()

        remaining = set(candidates)

        for text in rows:
            for candidate in tuple(remaining):
                if f" {candidate} " in text:
                    present.add(candidate)
                    remaining.discard(candidate)

            if not remaining:
                break

        return frozenset(present)

    def _matching(
        self, project_id: int, terms: tuple[str, ...]
    ) -> ColumnElement[bool]:
        """
        The predicate for "in this project, and containing every term".

        Every term is a separate ``LIKE`` against the space-wrapped
        normalized text, combined with ``AND``: adding a word to a query
        narrows it, as a reader expects.
        """

        return and_(
            DocumentSearchSegment.project_id == project_id,
            *(
                DocumentSearchSegment.normalized_text.like(
                    containment_pattern(term)
                )
                for term in terms
            ),
        )


#: The order hits are returned in, and the reason grouping by document
#: works on a page: a document's segments are adjacent, and within a
#: document they arrive in the order a reader would meet them - down the
#: pages of a drawing, across the rows of a sheet. ``id`` last makes the
#: order total, so the same query always returns the same page.
_READING_ORDER = (
    DocumentSearchSegment.document_id,
    DocumentSearchSegment.page_number,
    DocumentSearchSegment.paragraph_index,
    DocumentSearchSegment.line_index,
    DocumentSearchSegment.worksheet_index,
    DocumentSearchSegment.row_number,
    DocumentSearchSegment.column_number,
    DocumentSearchSegment.id,
)


def _record(segment: SearchSegment) -> DocumentSearchSegment:
    """A domain segment as the row that stores it."""

    location = segment.location

    return DocumentSearchSegment(
        project_id=segment.project_id,
        document_id=segment.document_id,
        content_checksum=segment.content_checksum,
        kind=segment.kind.value,
        page_number=location.page_number,
        paragraph_index=location.paragraph_index,
        line_index=location.line_index,
        worksheet_index=location.worksheet_index,
        worksheet_name=location.worksheet_name,
        row_number=location.row_number,
        column_number=location.column_number,
        cell_offsets=_encode_offsets(location.cell_offsets),
        text=segment.text,
        normalized_text=normalize(segment.text),
    )


def _kind(stored: str) -> SegmentKind:
    """
    The source family a stored row names.

    A value this version does not know is a typed failure rather than a
    ``ValueError`` from the enum, because the identifier that could not
    be read is the whole of what a reader needs to know.
    """

    try:
        return SegmentKind(stored)
    except ValueError as error:
        raise UnknownSegmentKindError(stored) from error


def _encode_offsets(
    offsets: tuple[tuple[int, int], ...],
) -> str | None:
    """Cell boundaries as JSON, or ``None`` when there are none to
    record - a PDF line has no cells, and an empty list would suggest a
    row whose cells were all missed."""

    return json.dumps([list(pair) for pair in offsets]) if offsets else None


def _decode_offsets(stored: str | None) -> tuple[tuple[int, int], ...]:
    """
    Cell boundaries as written, or nothing.

    Anything unreadable yields no boundaries rather than an error - not
    only malformed JSON but valid JSON of the wrong shape, which is the
    form a version mismatch would take. The consequence is a hit that
    names its row but not its cell, which is a smaller harm than a
    search that fails outright over a display detail.
    """

    if not stored:
        return ()

    try:
        decoded = json.loads(stored)
    except json.JSONDecodeError:
        return ()

    if not isinstance(decoded, list):
        return ()

    boundaries: list[tuple[int, int]] = []

    for pair in decoded:
        if (
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(value, int) for value in pair)
        ):
            boundaries.append((pair[0], pair[1]))

    return tuple(boundaries)


def _hit(record: DocumentSearchSegment, filename: str) -> SearchHit:
    """A stored row as the hit a reader is shown."""

    return SearchHit(
        document_id=record.document_id,
        document_filename=filename,
        content_checksum=record.content_checksum,
        kind=_kind(record.kind),
        location=SegmentLocation(
            page_number=record.page_number,
            paragraph_index=record.paragraph_index,
            line_index=record.line_index,
            worksheet_index=record.worksheet_index,
            worksheet_name=record.worksheet_name,
            row_number=record.row_number,
            column_number=record.column_number,
            cell_offsets=_decode_offsets(record.cell_offsets),
        ),
        text=record.text,
    )
