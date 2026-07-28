"""
The canonical text segmentation of a document (EPIC 2, Milestone 27.1).

The stable textual structure every future extractor consumes. It is built
from the Canonical PDF Representation (Milestone 26.1) and from nothing
else - never from the original PDF, which by this point in the pipeline
nothing reopens.

## What a "section" is here, and what it is not

This is the one name in the hierarchy that could mislead, so it is worth
being exact.

A ``CanonicalTextSection`` is **one page**. Nothing more.

It is *not* a chapter, a heading, a clause, a drawing zone, or an
engineering section. Those would all have to be inferred, and inferring
them is precisely what this milestone refuses to do: a heading detector
that decided "TECHNICAL DATA" was a section title would be guessing from
font size, and every extractor downstream would inherit the guess as if
it were an observation.

The page transition is a boundary the parser genuinely observed, so it is
a boundary this layer may record. When a later milestone learns to
recognise real document sections - with review, with evidence, and with
its own failure modes - it can add them as their own concept. It must not
quietly redefine this one.

The same discipline applies at every level:

| Level | Is exactly | Never |
|---|---|---|
| Section | one PDF page | a chapter, heading or engineering section |
| Paragraph | one PDF block, as the parser delimited it | a semantic paragraph, a table, a list |
| Line | one PDF line, as the parser grouped its spans | a sentence, a row, a field |
| Token | one whitespace-delimited run inside one span | a word, a tag, an equipment reference |

Every level is named for the structure it records. None of them means
anything about the substation.

## Provenance

Every object carries its way back to the Canonical Representation, and
every token carries the full chain:

```
document -> page -> block -> span -> character range
```

An extractor that concludes something from a token can therefore point at
the exact characters of the exact span it came from. That chain is the
reason this layer exists at all: a claim about a substation whose
evidence cannot be located in a document is not evidence, it is an
assertion.

## Immutability and equality

Every level is a frozen value object and **nothing here carries a
timestamp**. Segmenting the same representation twice must produce values
that compare equal, and a timestamp would silently make that impossible.
When a segmentation was built is a fact about the stored row.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpanProvenance:
    """
    Where a token's characters came from, exactly.

    ``character_start``/``character_end`` are offsets into the
    originating span's own ``text``, so the substring can be recovered
    and checked against the Canonical Representation without re-parsing
    anything. Half-open, Python slice convention.

    A token never straddles two spans. Tokens are cut *within* a span, so
    a word split across a style boundary - "MV" in bold followed by
    "switchgear" - yields two tokens rather than one merged word.
    Merging them would be a judgement about what the document meant, and
    would leave the result pointing at no single span.
    """

    page_number: int
    block_reading_order: int
    span_reading_order: int
    line_index: int
    character_start: int
    character_end: int

    @property
    def character_length(self) -> int:
        return self.character_end - self.character_start


@dataclass(frozen=True, slots=True)
class CanonicalTextToken:
    """
    One whitespace-delimited run of characters, inside one span.

    ``text`` is the original substring, verbatim. ``normalized_text`` is
    the deterministic normalisation of it (see
    ``canonical_text_normalization``) - never an expansion, a correction
    or an engineering interpretation. Both are kept: the original is what
    the document says, the normalised form is what two documents can be
    compared on, and neither can substitute for the other.

    ``position`` is the token's index within its **line**, counted across
    every span of that line, so token order survives the span boundaries
    that produced it.
    """

    position: int
    text: str
    normalized_text: str
    provenance: SpanProvenance


@dataclass(frozen=True, slots=True)
class CanonicalTextLine:
    """
    One line, as the parser grouped its spans - not a sentence, and not a
    table row.

    ``line_index`` is the parser's own index within the block, carried
    through from Milestone 26.1's spans. Recording it rather than
    re-deriving line membership from coordinates is the difference
    between an observation and an inference.
    """

    line_index: int
    tokens: tuple[CanonicalTextToken, ...] = ()

    @property
    def text(self) -> str:
        """The line's tokens joined by single spaces.

        A **reconstruction**, not the document's own text: tokenisation
        discarded the original spacing, and pretending otherwise would
        offer a string the document never contained. Whoever needs the
        verbatim line reads the Canonical Representation's spans, which
        are still there and still authoritative.
        """

        return " ".join(token.text for token in self.tokens)

    @property
    def is_empty(self) -> bool:
        return not self.tokens


@dataclass(frozen=True, slots=True)
class CanonicalTextParagraph:
    """
    One PDF block, as the parser delimited it.

    Called a paragraph because that is what a block usually is, and named
    honestly in its own docstring because sometimes it is not: a table
    cell, a title bar, a revision stamp. This layer does not know which,
    and does not guess.

    ``block_reading_order`` is the parser's own ordering. No geometric
    re-ordering happens here, exactly as none happened in Milestone 26.1.
    """

    paragraph_index: int
    page_number: int
    block_reading_order: int
    lines: tuple[CanonicalTextLine, ...] = ()

    @property
    def token_count(self) -> int:
        return sum(len(line.tokens) for line in self.lines)

    @property
    def is_empty(self) -> bool:
        return self.token_count == 0


@dataclass(frozen=True, slots=True)
class CanonicalTextSection:
    """
    One page. See this module's docstring - this is deliberately not a
    chapter, a heading or an engineering section.

    ``section_index`` is 0-based ordering within the document;
    ``page_number`` is the 1-based page an engineer would name. Both are
    kept because they answer different questions, and collapsing them
    would force every caller to convert.
    """

    section_index: int
    page_number: int
    paragraphs: tuple[CanonicalTextParagraph, ...] = ()

    @property
    def token_count(self) -> int:
        return sum(paragraph.token_count for paragraph in self.paragraphs)

    @property
    def is_empty(self) -> bool:
        return self.token_count == 0


@dataclass(frozen=True, slots=True)
class CanonicalTextDocument:
    """
    One document's complete segmentation, bound to the exact Canonical
    Representation it was built from.

    ``content_checksum`` and ``representation_version`` identify that
    representation; ``segmentation_version`` identifies the rules used to
    segment it. All three are recorded because all three can change
    independently, and a segmentation whose provenance is unknown cannot
    be trusted by anything downstream.

    Deliberately **no timestamp** - see the module docstring.
    """

    document_id: int
    content_checksum: str
    representation_version: str
    segmentation_version: str
    sections: tuple[CanonicalTextSection, ...] = ()

    @property
    def section_count(self) -> int:
        return len(self.sections)

    @property
    def token_count(self) -> int:
        return sum(section.token_count for section in self.sections)

    @property
    def is_empty(self) -> bool:
        """No tokens anywhere - a segmentation carrying nothing to
        extract from."""

        return self.token_count == 0

    def tokens(self):
        """Every token in document order.

        The read a future extractor actually performs, offered once here
        so that each of them does not re-implement the nested walk - and
        get the ordering subtly different.
        """

        for section in self.sections:
            for paragraph in section.paragraphs:
                for line in paragraph.lines:
                    yield from line.tokens
