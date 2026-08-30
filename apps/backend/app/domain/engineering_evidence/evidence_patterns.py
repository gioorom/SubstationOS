"""
The pattern catalogue (Milestone 28.1) - the **one** module in this
context that compiles a regular expression.

Every matching decision this layer makes traces back to a pattern
declared here. An architecture test asserts that no other module in the
evidence context calls ``re.compile``, so a rule cannot grow a private
matcher and quietly start recognising something nobody reviewed.

## Designation syntax

Conservative on purpose. The brief for this milestone is explicit that
*not every capitalised token is a designation*, and the cost of being
wrong is asymmetric: a missed designation is a gap a later milestone can
fill, while a false one becomes an entity that an engineer has to
disprove.

Three shapes are recognised, each requiring **letters and digits
together** - which is what distinguishes a designation from a word:

| Shape | Matches | Does not match |
|---|---|---|
| letters then digits | ``T1``, ``TR1``, ``QMT01``, ``M1`` | ``TRASFORMATORE``, ``AT``, ``kV`` |
| numeric function code | ``52-Q1``, ``189-SB1`` | ``145``, ``20-30`` |
| IEC 81346 style | ``+E01``, ``-QA1``, ``+E01-QA1`` | ``-`` , ``+5`` |

Deliberately **not** recognised: bare uppercase words of any length,
bare numbers, single letters, and anything containing lower-case letters
outside the IEC form. Each of those produced false positives on realistic
substation text.
"""

from __future__ import annotations

import re

# --- Designations ---------------------------------------------------------

# 1-4 letters followed by 1-4 digits: T1, TR1, QMT01, M1.
# Upper case only - "Fig1" and "no1" are not designations.
DESIGNATION_LETTERS_THEN_DIGITS = re.compile(r"^[A-Z]{1,4}[0-9]{1,4}$")

# A numeric function code, hyphen, then a letter-digit designation:
# 52-Q1, 189-SB1. The leading number is an ANSI/IEC device function.
DESIGNATION_FUNCTION_CODE = re.compile(r"^[0-9]{2,3}-[A-Z]{1,3}[0-9]{1,3}$")

# IEC 81346 aspect prefixes: +E01, -QA1, +E01-QA1.
DESIGNATION_IEC_81346 = re.compile(
    r"^[+\-][A-Z]{1,3}[0-9]{1,3}(?:-[A-Z]{1,3}[0-9]{1,3})?$"
)

DESIGNATION_PATTERNS = (
    DESIGNATION_LETTERS_THEN_DIGITS,
    DESIGNATION_FUNCTION_CODE,
    DESIGNATION_IEC_81346,
)


# --- Quantities ------------------------------------------------------------

# A number as documents actually write it: digits, optionally with
# grouping or decimal separators. Which separator means what is decided
# by ``evidence_quantities``, not here - this pattern only says "this
# token is numeric in shape".
NUMBER = re.compile(r"^[0-9]+(?:[.,][0-9]+)*$")

# A number and its unit written as one token: "20kV", "630kVA", "240mm²".
# The unit half is matched loosely here and validated against the unit
# catalogue afterwards, so this pattern never decides what a unit is.
NUMBER_WITH_UNIT = re.compile(
    r"^(?P<number>[0-9]+(?:[.,][0-9]+)*)(?P<unit>[A-Za-zÂ²³µΩ]+[²³]?)$"
)


# A **compound** IEC 81346 reference designation: a location aspect
# followed by a product aspect, written as one token - ``+E01-QA1``.
#
# Deliberately narrower than ``DESIGNATION_IEC_81346`` above, in the one
# way that matters: the first segment must carry ``+``. IEC 81346-1
# assigns ``+`` to the **location** aspect and ``-`` to the **product**
# aspect, so ``+E01-QA1`` names a product within a location while
# ``-QA1-XB2`` names a product within a *product*. Those are different
# engineering statements, and only the first is what this milestone
# interprets - see ``evidence_rules.LOCATION_ASPECT_RULE``.
#
# The groups are named because the extractor needs the location segment's
# **character length** to narrow provenance onto the characters that
# actually produced the observation.
DESIGNATION_IEC_81346_COMPOUND = re.compile(
    r"^(?P<location>\+[A-Z]{1,3}[0-9]{1,3})"
    r"(?P<product>-[A-Z]{1,3}[0-9]{1,3})$"
)
