"""
How a query and a piece of source text are made comparable.

Search here is **lexical and deterministic**: the same query over the
same corpus returns the same hits, in the same order, forever. It
matches terms an engineer typed against terms a document contains. It
does not infer, rank by similarity, or consult a model.

That is a deliberate limit, not a stage on the way to something else.
An engineer searching ``TR1`` is asking which documents say ``TR1`` -
and a system that answered with ``TR2`` because the two are alike would
be making an engineering claim nobody asked it for.

**Terms match whole, never as substrings.** ``TR1`` does not match
``TR15``, and searching ``kV`` does not match ``kVA``. A substring
match would quietly relate a 150 kV transformer to a 150 kVA one, which
in this domain is not a near miss - it is a different piece of
equipment.

**Aspect prefixes are part of the identifier, not punctuation.** In
IEC 81346 a leading ``-`` marks the product aspect, ``+`` the location
aspect and ``=`` the function aspect. ``-Q1`` and ``Q1`` are therefore
two different designations, as are ``+189L`` and ``189L``, and this
module keeps them apart. Folding them together would be the system
asserting an identity the document did not state.

What *is* folded is case and accents, because no engineer means
something different by ``tr1`` than by ``TR1``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: The aspect prefixes of IEC 81346, which bind to the front of the
#: designation they qualify and are part of it.
ASPECT_PREFIXES: tuple[str, ...] = ("-", "+", "=")

#: What counts as one term.
#:
#: An optional aspect prefix, then a run of letters and digits, then any
#: number of dotted continuations so ``-Q1.1`` and ``1.5`` survive
#: whole. Everything the pattern does not match is a separator: spaces,
#: brackets, commas, slashes. ``150/20 kV`` is three terms because the
#: slash joins two independent ratings; ``-Q1`` is one term because the
#: hyphen qualifies what follows it.
#:
#: The prefix is taken only when a **letter appears somewhere in what
#: follows**, which is what separates a designation from arithmetic. An
#: IEC 81346 designation carries a letter class - ``Q`` for a switching
#: device, ``T`` for a transformer - though not always first, which is
#: why ``+189L`` counts. So ``-Q1`` and ``+189L`` are designations while
#: ``-20`` is minus twenty, and a cell holding a negative number stays
#: findable by its digits.
#:
#: The rule cannot separate ``-20A`` the designation from ``-20A`` the
#: current, because nothing in the text does. It is read as a
#: designation, which is the reading that keeps the prefix visible to
#: the engineer rather than silently discarding it.
#:
#: A dotted continuation must follow a digit, so ``-Q1.1`` and ``1.5``
#: survive whole while ``TR1.Il`` - a full stop somebody forgot to put a
#: space after - is two terms and ``TR1`` still finds it.
_TERM = re.compile(
    r"(?:[-+=](?=[0-9]*[a-z]))?[0-9a-z]+(?:(?<=[0-9])\.[0-9]+)*"
)


@dataclass(frozen=True, slots=True)
class TermSpan:
    """One term, and where it sits in the text it was read from."""

    term: str
    start: int
    end: int


#: Characters that *are* an ASCII punctuation mark but are not encoded
#: as one.
#:
#: Unicode has a dozen dashes and none of them decompose to ``-``. A PDF
#: produced by a CAD plotter commonly carries U+2212 MINUS SIGN or
#: U+2010 HYPHEN where the drawing shows a hyphen, and a spreadsheet
#: autocorrected in Word carries U+2013 EN DASH. Left alone all of them
#: fold to nothing, which silently turns ``-Q1`` into ``Q1`` - the one
#: collapse this module exists to prevent. They are mapped back to the
#: ASCII mark they stand for so the aspect prefix survives the document
#: it arrived in.
_ASCII_EQUIVALENTS = {
    "‐": "-",  # hyphen
    "‑": "-",  # non-breaking hyphen
    "‒": "-",  # figure dash
    "–": "-",  # en dash
    "—": "-",  # em dash
    "―": "-",  # horizontal bar
    "⁃": "-",  # hyphen bullet
    "−": "-",  # minus sign
    "⸺": "-",  # two-em dash
    "⸻": "-",  # three-em dash
    "﹘": "-",  # small em dash
    "﹣": "-",  # small hyphen-minus
    "－": "-",  # fullwidth hyphen-minus
    "˖": "+",  # modifier letter plus sign
    "﬩": "+",  # hebrew letter alternative plus sign
    "＋": "+",  # fullwidth plus sign
    "＝": "=",  # fullwidth equals sign
}

#: Unicode categories whose characters may vanish without trace: marks
#: that combine with the letter before them, and formatting characters
#: that are not drawn at all. A soft hyphen disappears so a word broken
#: across two lines of a drawing reads as one word again.
_INVISIBLE_CATEGORIES = frozenset({"Mn", "Mc", "Me", "Cf"})


def _fold_character(character: str) -> str:
    """
    One source character, folded. May yield nothing (a combining mark),
    one character, or several (``1/2`` from a vulgar fraction).

    A **visible** character with no ASCII form becomes a space rather
    than nothing, because deleting it welds its neighbours together:
    ``90°C`` would otherwise be the single term ``90c``, findable by
    neither ``90`` nor ``C``. As a separator it is at worst unsearchable
    itself, which is the honest outcome for a symbol ASCII cannot
    write.
    """

    equivalent = _ASCII_EQUIVALENTS.get(character)

    if equivalent is not None:
        return equivalent

    folded = (
        unicodedata.normalize("NFKD", character)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )

    if folded:
        return folded

    return (
        ""
        if unicodedata.category(character) in _INVISIBLE_CATEGORIES
        else " "
    )


def _fold_with_offsets(text: str) -> tuple[str, tuple[int, ...]]:
    """
    ``text`` folded, plus the source index each folded character came
    from.

    Folding is done one character at a time rather than over the whole
    string so that this mapping exists at all: ``NFKD`` plus dropping
    non-ASCII changes length, and without an index per folded character
    a match found in the folded form could not be pointed at in the
    original. The engineer reads the original.
    """

    folded: list[str] = []
    origins: list[int] = []

    for index, character in enumerate(text):
        for folded_character in _fold_character(character):
            folded.append(folded_character)
            origins.append(index)

    return "".join(folded), tuple(origins)


def fold(text: str) -> str:
    """
    ``text`` with its accents removed and its case dropped.

    Exposed apart from ``tokenize`` so that the folding rules can be
    read, tested and reasoned about on their own - they are where the
    delicate decisions live, and a bug in them is a bug in every term
    this module produces.
    """

    return _fold_with_offsets(text)[0]


def tokenize(text: str) -> tuple[str, ...]:
    """
    Every term in ``text``, in the order it appears, repeats included.

    ``Trasformatore TR1 150/20 kV (-Q1)`` yields
    ``trasformatore tr1 150 20 kv -q1``.

    Read from the folded text directly rather than from
    ``tokenize_with_spans``, because that function may decline to place
    a term it cannot place precisely - and a term that exists must
    still be searchable even when it cannot be pointed at.
    """

    return tuple(_TERM.findall(fold(text)))


def tokenize_with_spans(text: str) -> tuple[TermSpan, ...]:
    """
    Every term in ``text`` that can be pointed at in the original
    string, each carrying the slice it was read from.

    ``text[span.start:span.end]`` is what the document actually says -
    ``TR1`` where the term is ``tr1`` - which is what a snippet shows
    and what a highlight covers.

    **Spans never overlap.** One source character can fold to several,
    so two terms can be read out of a single character: ``A/C`` written
    as the one character ``U+2100`` yields both ``a`` and ``c``, and
    both would claim it. A term that cannot be given a slice of its own
    is left out rather than given a slice that belongs to its
    neighbour, because these offsets become highlights and a highlight
    must sit under the text it matched.
    """

    folded, origins = _fold_with_offsets(text)

    spans: list[TermSpan] = []
    placed = 0

    for match in _TERM.finditer(folded):
        start = max(origins[match.start()], placed)
        end = origins[match.end() - 1] + 1

        if start >= end:
            continue

        spans.append(TermSpan(term=match.group(), start=start, end=end))
        placed = end

    return tuple(spans)


def normalize(text: str) -> str:
    """
    The comparable form of a piece of text: its terms, space separated,
    wrapped in single spaces so each one can be matched with its
    boundaries intact - see ``containment_pattern``.

    The wrapping is why an empty result is ``" "`` rather than ``""``:
    a row of text that contains no terms at all must still be a row the
    pattern can be applied to without matching everything.
    """

    tokens = tokenize(text)

    return f" {' '.join(tokens)} " if tokens else " "


def terms(query: str) -> tuple[str, ...]:
    """
    The terms a query asks for, in the order they were written, without
    repeats.

    Order is kept because it is what the engineer typed and a reader
    comparing a result against their query should recognise it.
    Duplicates are dropped because asking for ``TR1 TR1`` is asking for
    ``TR1``.
    """

    seen: dict[str, None] = {}

    for term in tokenize(query):
        seen.setdefault(term, None)

    return tuple(seen)


def containment_pattern(term: str) -> str:
    """
    The ``LIKE`` pattern that matches one whole term inside normalized
    text.

    The surrounding spaces are the whole point: normalized text is
    space-wrapped, so ``% tr1 %`` matches ``tr1`` standing alone and
    never the ``tr1`` inside ``tr15``.
    """

    return f"% {term} %"


def unprefixed(term: str) -> str | None:
    """
    ``term`` without its aspect prefix, or ``None`` if it has none.

    Used to *explain* an empty result, never to widen a search: when
    ``Q1`` finds nothing the engineer is told the project contains
    ``-Q1`` and asked to decide, rather than being handed the other
    designation as though they had asked for it.
    """

    if term[:1] in ASPECT_PREFIXES and len(term) > 1:
        return term[1:]

    return None


def prefixed_variants(term: str) -> tuple[str, ...]:
    """
    The same designation carrying each aspect prefix in turn.

    ``q1`` yields ``-q1``, ``+q1``, ``=q1``. Offered to a reader whose
    query found nothing, for the same reason as ``unprefixed``: so the
    near miss is visible and theirs to act on.
    """

    if term[:1] in ASPECT_PREFIXES:
        return ()

    return tuple(f"{prefix}{term}" for prefix in ASPECT_PREFIXES)
