"""
The closed vocabulary of deterministic engineering reasoning (EPIC 32.1).

Every value here is a member of a closed enum, because a reasoning result
that could carry an outcome nobody planned is a reasoning result nobody
can act on.

---

## Why four outcomes and not two

A boolean would collapse three genuinely different engineering
situations into one:

| Situation | Boolean would say | What an engineer needs to know |
|---|---|---|
| Two governed values agree | true | the knowledge agrees |
| Two governed values differ | false | **the documents disagree** - somebody must look |
| No governed value exists | false | **nobody has approved anything** - there is nothing to disagree with |
| The subject names two assets | false | **the question was ambiguous** - it was never answered |

The last three are not the same problem and do not have the same fix.
Reporting them identically would be the single most damaging
simplification this milestone could make.

## What is deliberately absent

No `PROBABLY_CONSISTENT`, no `LIKELY`, no confidence percentage, no
score. Reasoning here is deterministic: the same governed inputs under
the same rule version always produce the same outcome, and a probability
would be a claim this milestone has no basis to make.

Retrieval's match-strategy precedence is **not** a confidence and is
never converted into one (AF-RET-003).
"""

from __future__ import annotations

from enum import Enum


class ReasoningOutcome(str, Enum):
    """
    What a deterministic reasoning rule concluded.

    Four members, and the distinction between the last three is the point
    of the vocabulary.
    """

    #: The governed inputs the rule required were present and agree.
    CONSISTENT = "consistent"

    #: The governed inputs were present and **disagree** under the rule.
    #:
    #: This says the governed statements conflict. It does **not** say a
    #: document is wrong, that an engineer rejected anything, or which
    #: value is correct - reasoning knows only that two approved
    #: statements cannot both describe the same thing.
    INCONSISTENT = "inconsistent"

    #: The rule's required governed inputs were not available.
    #:
    #: **Not a synonym for consistent.** "No contradiction was found"
    #: and "there was nothing to contradict" are different answers, and
    #: conflating them would let an empty graph certify a substation.
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"

    #: The question resolved to more than one governed subject, so it was
    #: never a single question.
    #:
    #: Reasoning refuses to pick one. Deciding that two governed assets
    #: sharing a designation are the same equipment is cross-document
    #: entity resolution, which no governed rule performs.
    AMBIGUOUS = "ambiguous"


class ReasoningRuleFamily(str, Enum):
    """
    Which kind of engineering question a rule answers.

    One member, from the one thing governed semantics currently supports.
    A family is added when a rule exists to put in it - never in
    anticipation.
    """

    #: "Do the governed values describing this quantity agree?"
    QUANTITY_CONSISTENCY = "quantity_consistency"


class ReasoningDiagnosticCode(str, Enum):
    """
    Why the rule reached its outcome.

    Machine-readable and deterministic. Human-readable text, where a
    caller wants it, is rendered *from* these - never instead of them,
    and never by asking a model to explain a comparison the platform
    already performed exactly.
    """

    #: Every governed value found was equal, in the same unit.
    VALUES_EQUAL = "values_equal"

    #: Governed values in the same unit differ.
    VALUES_CONFLICT = "values_conflict"

    #: Exactly one governed value was found. Whether that is enough is
    #: the rule's decision, recorded in its own documentation.
    SINGLE_VALUE = "single_value"

    #: The subject resolved, but no governed quantity of the required
    #: kind is asserted about it.
    NO_REQUIRED_QUANTITY = "no_required_quantity"

    #: No governed subject matched at all.
    NO_SUBJECT = "no_subject"

    #: The designation named more than one governed asset.
    AMBIGUOUS_SUBJECT = "ambiguous_subject"

    #: Values were found but cannot be compared - different units, and
    #: this platform has no authoritative conversion for them in governed
    #: knowledge.
    #:
    #: Reported rather than guessed. Converting kVA to VA inside a
    #: reasoning rule would be a units engine built on data the governed
    #: graph does not carry.
    UNSUPPORTED_COMPARISON = "unsupported_comparison"

    #: A governed value is not a comparable number.
    UNPARSABLE_VALUE = "unparsable_value"
