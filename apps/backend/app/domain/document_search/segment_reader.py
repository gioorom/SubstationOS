"""
The port that produces what there is to index for a document.

Indexing does not read documents. It reads the **canonical
representations** already derived from them - the PDF's verbatim spans,
the workbook's cells - because those are what this system has agreed
are a faithful reading of the bytes. Re-parsing the original here would
create a second, unreviewed opinion about what a document says.

A document with no canonical representation therefore yields no
segments. That is not a failure: it is the honest answer that nothing
has yet established what the document contains.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.document_search.search_models import SearchSegment


class DocumentSegmentReader(ABC):
    """Reads a document's canonical representation as search segments."""

    @abstractmethod
    def segments_for(self, document_id: int) -> tuple[SearchSegment, ...]:
        """
        Every segment worth indexing for this document, in reading
        order.

        Returns empty when the document has no canonical representation,
        when its representation is empty, or when it is of a family this
        system cannot yet read. The caller must treat an empty result as
        "nothing to index", never as an error to retry.
        """

        raise NotImplementedError
