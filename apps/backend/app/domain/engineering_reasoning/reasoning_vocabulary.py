"""
The closed vocabulary of deterministic engineering reasoning
(EPIC 32.1, extended by EPIC 32.2).

Every value here is a member of a closed enum, because a reasoning result
that could carry an outcome nobody planned is a reasoning result nobody
can act on.

## One vocabulary per reasoning family, not one for all of them

Two families ship, and each has its **own** outcome and diagnostic
vocabulary:

| Family | Outcomes | Diagnostics |
|---|---|---|
| `QUANTITY_CONSISTENCY` | `ReasoningOutcome` | `ReasoningDiagnosticCode` |
| `STRUCTURAL_RELATIONSHIP` | `StructuralReasoningOutcome` | `StructuralReasoningDiagnosticCode` |

Sharing one vocabulary would have been cheaper and wrong. `CONSISTENT`
means "these governed values agree"; it cannot be stretched to mean "this
relationship holds" without making both meanings unreadable. The family
on a result says which dictionary its outcome is written in.

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
    What a **quantity consistency** rule concluded.

    Four members, and the distinction between the last three is the point
    of the vocabulary.

    This vocabulary belongs to `ReasoningRuleFamily.QUANTITY_CONSISTENCY`
    and to nothing else. `CONSISTENT` answers "do these governed values
    agree?" - it is not a general-purpose yes, and EPIC 32.2 deliberately
    did **not** reuse it to mean "this relationship holds". Two assets
    sharing a location are not "consistent"; the word would be a category
    error that every downstream reader would inherit.
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

    A family is added when a rule exists to put in it - never in
    anticipation. **The family also says which outcome vocabulary a
    result carries**, which is why it is not a decoration: reading an
    outcome without reading the family would be reading a word from the
    wrong dictionary.
    """

    #: "Do the governed values describing this quantity agree?"
    #: Outcomes: `ReasoningOutcome`.
    QUANTITY_CONSISTENCY = "quantity_consistency"

    #: "What does governed knowledge establish about the structural
    #: relationship between these two assets?" Outcomes:
    #: `StructuralReasoningOutcome`.
    #:
    #: Added by EPIC 32.2, once EPIC 32.P1 gave the governed graph a
    #: relationship between two structural objects. The family is named
    #: for the **kind of question**, not for the one rule in it: a
    #: second structural question would be a second rule here, and would
    #: still not be a rule engine.
    STRUCTURAL_RELATIONSHIP = "structural_relationship"


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


class StructuralReasoningOutcome(str, Enum):
    """
    What a **structural relationship** rule concluded.

    Three members, and the absent fourth is the important one.

    ## Why there is no negative outcome

    There is no `NOT_ESTABLISHED`, no `NOT_SHARED` and no `DISJOINT`,
    because the governed graph has **no complete-world basis**. It is a
    partial projection of the statements engineers have approved
    (ADR-0024): a location relationship exists only where a document
    happened to write a compound IEC 81346 designation, an extraction
    rule read it, and a reviewer approved the interpretation.

    Two consequences follow, and either alone would be decisive:

    1. **Absence is not refutation.** An asset with no governed location
       edge is an asset nobody has recorded a location for - not an asset
       that is nowhere.
    2. **Distinct location identities are not distinct places.** Location
       identity is document-scoped by design (EPIC 32.P1): the same
       ``+E01`` written in two documents is two governed identities. So
       ``A -> X`` and ``B -> Y`` with ``X != Y`` is entirely compatible
       with A and B standing in the same room.

    A negative outcome would therefore assert something no governed input
    supports. `INSUFFICIENT_KNOWLEDGE` is the true answer, and it stays
    the answer until an ontology exists that can prove the negative.
    """

    #: Governed knowledge establishes the relationship: both assets have
    #: an applicable governed relationship to the **same** governed
    #: structural location identity.
    ESTABLISHED = "established"

    #: The governed inputs the rule required were not available, or were
    #: available and do not establish the relationship. **Not a negative
    #: conclusion** - see the class docstring.
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"

    #: The question, or the governed knowledge answering it, resolved to
    #: more than one possibility, so it was never a single question.
    #: Reasoning refuses to pick one.
    AMBIGUOUS = "ambiguous"


class DerivedRelationshipKind(str, Enum):
    """
    A relationship a **reasoning rule derived**, which governed knowledge
    does not assert.

    ## This vocabulary is deliberately disjoint from the governed ones

    No member here may appear in `GraphEdgeKind`, `SemanticStatementType`
    or `FactPredicate`, and an architecture test asserts all three
    intersections are empty. That disjointness is the structural form of
    AF-REASON-001: a derived relationship and a governed one must not be
    representable as the same thing, because within a few milestones
    nobody would be able to tell which of the two they were looking at.

    A derived relationship is never promoted, never persisted and never
    reviewed. It lives inside a `ReasoningResult` for as long as that
    result is in memory.
    """

    #: "Governed knowledge places both of these assets in one and the
    #: same governed structural location."
    #:
    #: Deliberately **not** `CONNECTED_TO`, `SAME_BAY`, `ADJACENT_TO` or
    #: `SAME_CIRCUIT`. It says the two assets share a governed
    #: structural-location context and it says nothing else: not that
    #: current can flow between them, not that they are near each other,
    #: not what kind of place they are in, and not that either is
    #: energised. A substation location routinely holds equipment from
    #: several unrelated circuits.
    SHARES_STRUCTURAL_LOCATION_WITH = "shares_structural_location_with"


class StructuralReasoningDiagnosticCode(str, Enum):
    """
    Why a structural relationship rule reached its outcome.

    Machine-readable and deterministic, exactly as
    `ReasoningDiagnosticCode` is for quantity consistency. A separate
    vocabulary because the reasons are different reasons - reporting a
    missing location edge as `NO_REQUIRED_QUANTITY` would be nonsense a
    reader would have to decode.
    """

    #: Both assets have an applicable governed relationship to the same
    #: governed structural location.
    SHARED_STRUCTURAL_LOCATION_ESTABLISHED = (
        "shared_structural_location_established"
    )

    #: The left asset has no applicable governed location relationship in
    #: the assembled context.
    LEFT_LOCATION_MISSING = "left_location_missing"

    #: The right asset has no applicable governed location relationship.
    RIGHT_LOCATION_MISSING = "right_location_missing"

    #: Neither asset has one.
    BOTH_LOCATIONS_MISSING = "both_locations_missing"

    #: Both assets have a governed location, and the two governed
    #: location **identities differ**.
    #:
    #: This is reported as `INSUFFICIENT_KNOWLEDGE`, never as a negative
    #: conclusion. Location identity is document-scoped, so two
    #: identities may name one place; and the graph is partial, so a
    #: shared location may simply be unrecorded.
    DISTINCT_LOCATION_IDENTITIES = "distinct_location_identities"

    #: One of the assets has governed relationships to **more than one**
    #: structural location, and which of them the question is about
    #: cannot be decided from the governed inputs.
    MULTIPLE_APPLICABLE_LOCATIONS = "multiple_applicable_locations"

    #: A designation in the question resolved to more than one governed
    #: asset. Reasoning refuses to choose - choosing would be silent
    #: cross-document entity resolution.
    ASSET_IDENTITY_AMBIGUOUS = "asset_identity_ambiguous"
