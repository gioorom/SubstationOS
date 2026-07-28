"""
Exact numeric parsing for engineering quantities (Milestone 28.1).

``Decimal`` throughout, never ``float``. A rated voltage that reads back
as 20.000000000000004 kV is a defect nobody can explain to an engineer,
and binary floating point makes that inevitable for ordinary decimal
values.

## The separator policy, stated in full

European and Anglo-Saxon documents disagree about what ``1.250`` means,
and both conventions appear in real substation documentation. Rather than
guess, the policy is explicit about which forms it can read exactly and
which it cannot:

| Written | Read as | Outcome |
|---|---|---|
| ``630`` | 630 | exact |
| ``12,5`` / ``12.5`` | 12.5 | exact - one separator, 1-2 following digits |
| ``1.250`` / ``1,250`` | - | **ambiguous** - could be 1250 or 1.25 |
| ``1.234,5`` | - | **ambiguous** - mixed conventions |
| ``12,,5``, ``1.2.3`` | - | invalid |

The three-digit case is the important one. It is genuinely undecidable
without knowing the document's locale, which this system does not know,
so it is reported as ``AMBIGUOUS`` and carried **without a normalised
value**. A reviewer can settle it; a guess could not be un-guessed once
it had become a rated value in the graph.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum

from app.domain.engineering_evidence.evidence_patterns import NUMBER


class QuantityParseOutcome(str, Enum):
    """Why a numeric token could or could not be read exactly."""

    EXACT = "exact"
    # Readable as a number, not readable as *one* number: the separator
    # could be a decimal point or a thousands mark.
    AMBIGUOUS_SEPARATOR = "ambiguous_separator"
    # Not a number this policy can read at all.
    INVALID = "invalid"


def parse_quantity(text: str) -> tuple[Decimal | None, QuantityParseOutcome]:
    """
    Read a numeric token exactly, or say why it cannot be.

    Returns ``(None, ...)`` for anything but ``EXACT``. There is
    deliberately no "best effort" value: a caller holding a number has a
    number, and a caller holding ``None`` knows it must not invent one.
    """

    if not NUMBER.match(text):
        return None, QuantityParseOutcome.INVALID

    separators = [character for character in text if character in ".,"]

    if not separators:
        return _decimal(text)

    if len(separators) > 1:
        # Mixed or repeated grouping: "1.234,5", "1.234.567". Both are
        # readable by a human who knows the convention and neither is
        # readable by this policy.
        return None, QuantityParseOutcome.AMBIGUOUS_SEPARATOR

    _, _, fraction = text.partition(separators[0])

    if len(fraction) == 3:
        # The undecidable case: 1.250 is 1250 in one convention and 1.25
        # in the other.
        return None, QuantityParseOutcome.AMBIGUOUS_SEPARATOR

    if len(fraction) > 3:
        return None, QuantityParseOutcome.AMBIGUOUS_SEPARATOR

    return _decimal(text.replace(",", "."))


def _decimal(text: str) -> tuple[Decimal | None, QuantityParseOutcome]:
    try:
        return Decimal(text), QuantityParseOutcome.EXACT
    except InvalidOperation:
        return None, QuantityParseOutcome.INVALID
