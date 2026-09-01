"""
The canonical textual representation of a PDF (EPIC 2, Milestone 26.1).

This is the **single source of truth for every future semantic
extraction**. The original PDF stays authoritative as a document - it is
what an engineer signs, prints and archives - but nothing downstream
parses it again. Extraction reads this representation, for three
reasons:

1. **Reproducibility.** A representation is a fixed value tied to a
   specific checksum, parser and representation version. Re-parsing the
   original later, under a different library version, could yield
   different text and would silently change the meaning of a conclusion
   already drawn from it.
2. **Determinism of everything downstream.** An extractor reading these
   value objects cannot be affected by the PDF's internals, encryption
   state, or the parser's failure modes - those were all resolved once,
   here, and recorded.
3. **One decoding boundary.** PDF parsing is the riskiest, most
   library-coupled step in the system. Confining it to one milestone,
   one adapter and one persisted artefact means a future change of parser
   is a re-canonicalisation, not a system-wide behavioural change.

## What this representation is not

It records **what the parser observed**, never what the document
"probably means". There is deliberately nowhere in this hierarchy to put:

- merged paragraphs, rewritten text, or stripped repeated headers;
- an inferred table, list, heading or document section;
- an engineering entity, an equipment tag, or any interpretation of the
  text's meaning;
- a value the parser did not supply.

Every one of those is a judgement, and judgements belong to milestones
that can be reviewed as judgements. The moment this model gains a
``section`` or ``table`` field, the boundary is gone.

## The hierarchy

```
CanonicalPdfDocument      one PDF, at one checksum
  └─ CanonicalPdfPage     one page, in page order
       └─ CanonicalPdfBlock   one parser block, in the parser's own order
            └─ CanonicalPdfSpan   one run of same-styled text
```

Every level is immutable, so a representation cannot be edited after the
fact - only rebuilt from bytes, which is the only thing that could
legitimately change it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CanonicalBlockKind(str, Enum):
    """
    What kind of content the parser reported for a block.

    ``IMAGE`` blocks carry no spans. They are recorded rather than
    dropped because "this page had a figure here" is something the parser
    observed, and a representation that silently omitted it would
    misrepresent the page as sparser than it is. Nothing here says what
    the image *is* - reading it would be OCR, which this milestone does
    not perform.
    """

    TEXT = "text"
    IMAGE = "image"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """
    A rectangle in PDF user-space points, as the parser reported it.

    Origin is the **top-left** of the page, y increasing downwards -
    PyMuPDF's convention, recorded as-is rather than converted, because
    converting would mean this value no longer matches what the parser
    said.
    """

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True, slots=True)
class TextStyle:
    """
    The styling the parser reported for a run of text.

    ``bold`` and ``italic`` come from the parser's own font flags, not
    from inspecting the font name for the word "Bold" - that would be a
    guess dressed up as a fact. Fields the parser does not supply are
    simply absent from this model rather than defaulted.
    """

    font_family: str
    font_size: float
    bold: bool
    italic: bool


@dataclass(frozen=True, slots=True)
class CanonicalPdfSpan:
    """
    One run of text sharing a single style, exactly as the parser
    produced it.

    ``text`` is **verbatim**: not stripped, not normalised, not
    case-folded, not de-hyphenated. Whitespace an engineer would call
    noise is still what the document contains, and deciding otherwise is
    an interpretation.

    ``line_index`` records which of the parser's lines this span belonged
    to. Without it, a later reader could not tell whether two spans sat
    on the same line, and would have to re-derive it from coordinates -
    which is inference. With it, the parser's own grouping survives.
    """

    reading_order: int
    line_index: int
    text: str
    bounding_box: BoundingBox
    style: TextStyle


@dataclass(frozen=True, slots=True)
class CanonicalPdfBlock:
    """
    One block as the parser delimited it, in the parser's own order.

    ``reading_order`` is the index the parser produced, **not** a reading
    order this system worked out. No geometric sorting is applied: a
    system that re-ordered blocks would be asserting how the page should
    be read, which for a multi-column wiring schedule is exactly the kind
    of guess that produces confident nonsense downstream.
    """

    reading_order: int
    kind: CanonicalBlockKind
    bounding_box: BoundingBox
    spans: tuple[CanonicalPdfSpan, ...] = ()

    @property
    def text(self) -> str:
        """The block's spans concatenated verbatim, in order. A
        convenience for readers, not a stored field - nothing is
        normalised on the way through."""

        return "".join(span.text for span in self.spans)


@dataclass(frozen=True, slots=True)
class CanonicalPdfPage:
    """
    One page. ``page_number`` is 1-based, as an engineer reads it and as
    a document's own page references use it - never a 0-based index that
    would have to be corrected at every boundary.

    A page with no blocks is perfectly valid and is recorded as such. A
    blank page in a drawing set is a fact about the document.
    """

    page_number: int
    width: float
    height: float
    blocks: tuple[CanonicalPdfBlock, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.blocks

    @property
    def text(self) -> str:
        return "".join(block.text for block in self.blocks)


@dataclass(frozen=True, slots=True)
class CanonicalPdfDocument:
    """
    The whole representation of one PDF at one specific content
    checksum.

    ``content_checksum`` is what binds this representation to the exact
    bytes it was built from (Milestone 25.2's identity). If a document's
    bytes change, the new checksum makes the new representation a
    *different* value rather than an overwrite of the old one, and the
    historical representation stays explainable: it says which bytes,
    which parser, which version.

    ``parser_name``/``parser_version``/``representation_version`` are
    recorded for the same reason. A representation whose provenance is
    unknown cannot be trusted years later, and "which parser produced
    this text?" is the first question anyone will ask when a downstream
    extraction looks wrong.

    Deliberately **no timestamp**: the value is a function of the bytes
    and the parser, and two runs over identical bytes must compare equal.
    When it was built is a fact about the row, not about the
    representation.
    """

    document_id: int
    content_checksum: str
    checksum_algorithm: str
    representation_version: str
    parser_name: str
    parser_version: str
    pages: tuple[CanonicalPdfPage, ...] = ()

    #: This artifact's deterministic identity, and the identity of the
    #: artifact it was derived from. ``None`` only for a row stored
    #: before the identity chain existed: unknown is not a value, and an
    #: artifact that cannot say what it was derived from can never prove
    #: a reuse is valid. See ``app/domain/artifact_identity``.
    artifact_identity: str | None = None
    upstream_identity: str | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def is_empty(self) -> bool:
        """No pages at all - a PDF that carries no document."""

        return not self.pages

    def page(self, page_number: int) -> CanonicalPdfPage | None:
        """
        One page by its 1-based number, or ``None`` when the
        representation has no such page.

        A lookup, never a search: ``page_number`` is the parser's own
        1-based number, so this cannot silently return a neighbouring
        page for an out-of-range request.
        """

        for page in self.pages:
            if page.page_number == page_number:
                return page

        return None

    @property
    def has_text(self) -> bool:
        """Whether the parser found any text span anywhere.

        ``False`` says exactly one thing: no text was extractable. It does
        **not** say the document is scanned, is an image, or is empty -
        those are conclusions, and this milestone reads nothing that
        could support them.
        """

        return any(
            span.text
            for page in self.pages
            for block in page.blocks
            for span in block.spans
        )
