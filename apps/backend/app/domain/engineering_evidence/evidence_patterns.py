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

Five shapes are recognised. The first three were declared by Milestone
28.1 and required **letters and digits together** - which is what
distinguishes a designation from a word. EPIC 32.E2 added the last two
after measuring 41,739 tokens of a single Italian DSO's HV/MV functional
diagrams, where product-aspect designations turned out **not** to obey
that rule.

| Shape | Matches | Does not match |
|---|---|---|
| letters then digits | ``T1``, ``TR1``, ``QMT01``, ``M1`` | ``TRASFORMATORE``, ``AT``, ``kV`` |
| numeric function code | ``52-Q1``, ``189-SB1`` | ``145``, ``20-30`` |
| IEC 81346 style | ``+E01``, ``-QA1``, ``+E01-QA1`` | ``-`` , ``+5`` |
| product aspect (32.E2) | ``-E``, ``-E1``, ``-X``, ``-TA`` | ``-``, ``-SCHEMA`` |
| dot-qualified product (32.E2) | ``-E1.L``, ``-E.AM``, ``-EV.TVL`` | ``-.L``, ``-E1.`` |

Deliberately **not** recognised: bare uppercase words of any length,
bare numbers, single letters, and anything containing lower-case letters
outside the IEC form. Each of those produced false positives on realistic
substation text.

## Why the product-aspect shapes do not require digits

``-E``, ``-X`` and ``-TA`` are real terminal-block designations, observed
28 times across the real document set. The ``-`` **is** the distinguishing
mark here - IEC 81346 assigns it to the product aspect - so the letters
need not carry a digit to be a designation. Length is bounded at four
letters because that is what keeps ``-SCHEMA`` and ``- FUNZIONALE`` out,
and no observed real designation is longer.
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

# A product-aspect designation: the IEC 81346 ``-`` mark, letters, and
# optionally digits - ``-E``, ``-E1``, ``-X``, ``-TA``.
#
# Digits are optional here and mandatory in
# ``DESIGNATION_LETTERS_THEN_DIGITS`` for a reason: an unprefixed word
# needs digits to be distinguishable from prose, while a ``-`` prefix is
# itself the mark that says "this is a product aspect". Four letters is
# the observed maximum and is what keeps ``-SCHEMA`` out.
DESIGNATION_PRODUCT_ASPECT = re.compile(r"^-[A-Z]{1,4}[0-9]{0,4}$")

# A dot-qualified product-aspect designation - ``-E1.L``, ``-E.AM``,
# ``-EV.TVL``. All nine real forms in the source set match this and
# nothing else does.
#
# **The dot is lexical, not hierarchical.** EPIC 32.E2 records the whole
# token as ONE atomic designation. ``-E1.L`` does not create ``-E1``, does
# not create ``L``, and asserts no parent/child relationship.
#
# The reason is that **no source evidence positively establishes that the
# leading segment denotes the parent engineering object** - not that any
# observation disproves a hierarchy. The real documents do place ``-E``
# at ``+GSH001`` and ``-E.AM`` at ``+GSH003``, which argues against a
# naive *physical containment* reading, but a reference-designation
# hierarchy need not imply co-location and this platform has established
# no such invariant. See ``engineering_evidence.md``.
DESIGNATION_DOT_QUALIFIED_PRODUCT = re.compile(
    r"^-[A-Z]{1,4}[0-9]{0,4}\.[A-Z]{1,4}[0-9]{0,4}$"
)

DESIGNATION_PATTERNS = (
    DESIGNATION_LETTERS_THEN_DIGITS,
    DESIGNATION_FUNCTION_CODE,
    DESIGNATION_IEC_81346,
    DESIGNATION_PRODUCT_ASPECT,
    DESIGNATION_DOT_QUALIFIED_PRODUCT,
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

# A **standalone** IEC 81346 location aspect - the whole token is the
# location: ``+GSH002``, ``+DQ1910``, ``+TELAIO``, ``+CELLA``, ``+Z``.
#
# Letters are required and digits are not, because the real document set
# writes locations both ways: ``+GSH002`` and ``+DQ1910`` alongside the
# word forms ``+TELAIO`` and ``+CELLA``. Eight letters is the observed
# maximum; requiring at least one letter is what keeps ``+390000000`` -
# the ``+39`` of an Italian telephone number - out.
#
# Measured over 41,739 real tokens this matches 268 times, across nine
# distinct values, with no false positive.
DESIGNATION_IEC_81346_LOCATION = re.compile(r"^\+[A-Z]{1,8}[0-9]{0,4}$")
