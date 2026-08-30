"""
Value objects for deterministic engineering reasoning
(EPIC 32.1, extended by EPIC 32.2).

Every type is immutable. The same governed context, the same query and
the same rule version always produce the same `ReasoningResult` -
including its identity, its contributor ordering and its diagnostics.

---

## The distinction this module exists to hold (AF-REASON-001)

```
Governed Knowledge          !=          Reasoning Conclusion
```

A `ReasoningResult` is **derived**. It is not an Engineering Fact, not a
Semantic Statement, not a Human Review, not a governed graph object, and
not a promotion candidate. Nothing here can be mistaken for one: a
conclusion carries a `rule_id` and a `rule_version`, which no governed
artefact has, and it carries no `entity_key`, `statement_key` or
`node_id` **of its own** - only references to the governed objects it
read.

## Provenance is structural, not conventional (AF-REASON-002)

`ReasoningContributor` holds the governed identities of one input, and
`ReasoningResult.contributors` has no default. A conclusion that could
not say which governed knowledge produced it cannot be constructed - the
same guarantee `GovernedRetrievalItem.provenance` gives one layer up.

**Every** contributor is retained. A conclusion that depends on two
conflicting statements names both, and a conclusion that rests on two
governed location relationships names both; reducing either to one
"primary" statement would make the conclusion uncheckable.

## Two families, one envelope (EPIC 32.2)

`ReasoningResult` carries what is true of **every** conclusion - its
identity, its rule, its contributors, its policy versions - and defers
what is true of one family to a typed field:

| Family | `query` | `outcome` | `diagnostics` | `structural` |
|---|---|---|---|---|
| `QUANTITY_CONSISTENCY` | `QuantityConsistencyQuery` | `ReasoningOutcome` | `ReasoningDiagnostics` | `None` |
| `STRUCTURAL_RELATIONSHIP` | `SharedStructuralLocationQuery` | `StructuralReasoningOutcome` | `StructuralReasoningDiagnostics` | `SharedStructuralLocationAssessment` |

`rule.family` is the discriminator. Every consumer that must tell the two
apart reads it and gets a static type - never a dictionary, never prose.
The common surface the 32.1 consumers already used (`result_id`, `rule`,
`outcome`, `contributors`, `diagnostics.code`, `query.question`) is
unchanged, which is why extending the model broke none of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.context_builder.context_builder_models import ContextItem
from app.domain.engineering_reasoning.reasoning_exceptions import (
    SameAssetComparisonError,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    DerivedRelationshipKind,
    ReasoningDiagnosticCode,
    ReasoningOutcome,
    ReasoningRuleFamily,
    StructuralReasoningDiagnosticCode,
    StructuralReasoningOutcome,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
)

# --- The question ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuantityConsistencyQuery:
    """
    "Do the governed values for this quantity of this asset agree?"

    A **typed** question, never free text. The subject is named by the
    designation an engineer wrote; the quantity is named by the governed
    relationship kind that asserts it - which is the only vocabulary this
    platform has for "which quantity", and deliberately so: inventing a
    ``nominal_current`` name the ontology cannot produce would be
    inventing engineering ontology.

    ``project_id`` is carried for diagnostics and identity only.
    Reasoning applies no scope of its own; the context it reads was
    already scoped and authorised upstream.
    """

    subject_designation: str
    quantity_kind: GraphEdgeKind
    project_id: int | None = None

    @property
    def question(self) -> str:
        """A stable, deterministic rendering of the question asked."""

        return (
            f"is the governed {self.quantity_kind.value} of "
            f"'{self.subject_designation}' self-consistent?"
        )


@dataclass(frozen=True, slots=True)
class SharedStructuralLocationQuery:
    """
    "Do these two governed assets share the same governed structural
    location?"

    A **typed** question, never free text, and never a traversal
    instruction: there is no depth, no direction, no edge filter and no
    path expression. The rule knows the one shape it reads.

    ## Why the assets are named by governed identity

    ``left_asset_node_id`` and ``right_asset_node_id`` are governed graph
    node ids, resolved **upstream** by retrieval. Two documents may each
    designate a ``TR1``; comparing the designations would silently merge
    two different transformers, which is the cross-document entity
    resolution no governed rule performs. Reasoning receives identities
    that were already resolved and resolves nothing itself.

    The designations are carried too, and are used **only** to render the
    question for a human reader. Nothing in the conclusion, and nothing
    in the result identity, derives from them.

    ## Same-asset questions are refused at construction

    See `SameAssetComparisonError`.
    """

    left_asset_node_id: str
    right_asset_node_id: str
    left_designation: str
    right_designation: str
    project_id: int | None = None

    def __post_init__(self) -> None:
        if self.left_asset_node_id == self.right_asset_node_id:
            raise SameAssetComparisonError(self.left_asset_node_id)

    @property
    def question(self) -> str:
        """
        A stable, deterministic rendering of the question **as asked**,
        preserving the order the caller used, for display.

        Deliberately not the identity input - see ``identity_question``.
        """

        return (
            f"do '{self.left_designation}' and '{self.right_designation}' "
            "share a governed structural location?"
        )

    @property
    def identity_question(self) -> str:
        """
        The question in **canonical** form: the two governed asset
        identities, sorted.

        Sharing a location is a symmetric relation, so asking about
        (A, B) and asking about (B, A) is asking the same engineering
        question and must produce the same conclusion identity. Sorting
        here is what makes that true of the hash rather than merely true
        of the words.
        """

        first, second = sorted(
            (self.left_asset_node_id, self.right_asset_node_id)
        )

        return (
            f"do governed assets '{first}' and '{second}' share a "
            "governed structural location?"
        )


# --- What a conclusion is built from -------------------------------------


@dataclass(frozen=True, slots=True)
class ReasoningContributor:
    """
    One governed input a conclusion rests on, by identity.

    Copies the compared value and unit, because a conflict that could not
    show the two values would not explain itself. Copies nothing else:
    the statement, the review, the facts and the evidence stay where they
    are, addressed by the identities below.

    ``order_key`` is the governed retrieval sort key, so contributors are
    ordered by the same total order the rest of the platform uses - never
    by "relevance", which reasoning does not have.
    """

    #: The context item this came from, which is the governed result id.
    item_id: str

    #: The governed graph objects.
    node_id: str | None
    edge_id: str | None

    #: The compared engineering value, exactly as governed knowledge
    #: holds it. ``Decimal`` because a rated power that read back as
    #: 630.0000000000001 would be a defect nobody could explain.
    value: Decimal | None
    unit: str | None
    label: str

    #: The governed provenance chain, by identity.
    statement_key: str
    review_id: int
    reviewer_display_name: str
    support_fingerprint: str
    document_id: int
    content_checksum: str
    semantic_rule_id: str
    semantic_rule_version: str

    order_key: tuple[int, str, str, str]

    @classmethod
    def of(
        cls, item: ContextItem, value: Decimal | None
    ) -> "ReasoningContributor":
        """Builds a contributor from a context item, copying nothing the
        governed item does not already hold."""

        result = item.result
        provenance = result.provenance

        return cls(
            item_id=result.result_id,
            node_id=None if result.node is None else result.node.node_id,
            edge_id=(
                None
                if result.relationship is None
                else result.relationship.edge_id
            ),
            value=value,
            unit=None if result.node is None else result.node.unit,
            label="" if result.node is None else result.node.label,
            statement_key=provenance.statement_key,
            review_id=provenance.review_id,
            reviewer_display_name=provenance.reviewer_display_name,
            support_fingerprint=provenance.support_fingerprint,
            document_id=provenance.document_id,
            content_checksum=provenance.content_checksum,
            semantic_rule_id=provenance.semantic_rule_id,
            semantic_rule_version=provenance.semantic_rule_version,
            order_key=result.sort_key,
        )

    @classmethod
    def of_relationship(cls, item: ContextItem) -> "ReasoningContributor":
        """
        Builds a contributor from a governed **relationship** item.

        A relationship has no value and no unit - it asserts that two
        governed objects stand in a stated relation, not that something
        measures anything - so both stay ``None`` rather than being
        filled with a placeholder a reader could mistake for a reading.

        ``label`` is the **subject's** label, because that is what
        identifies which asset's relationship this is when several are
        listed together. The full shape of the relationship is on the
        result's inference path, where it can be read as a path rather
        than guessed at from a string.
        """

        result = item.result
        provenance = result.provenance
        relationship = result.relationship

        return cls(
            item_id=result.result_id,
            node_id=None,
            edge_id=None if relationship is None else relationship.edge_id,
            value=None,
            unit=None,
            label=(
                "" if relationship is None else relationship.subject.label
            ),
            statement_key=provenance.statement_key,
            review_id=provenance.review_id,
            reviewer_display_name=provenance.reviewer_display_name,
            support_fingerprint=provenance.support_fingerprint,
            document_id=provenance.document_id,
            content_checksum=provenance.content_checksum,
            semantic_rule_id=provenance.semantic_rule_id,
            semantic_rule_version=provenance.semantic_rule_version,
            order_key=result.sort_key,
        )


# --- The rule ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReasoningRuleIdentity:
    """
    Which rule ran, and which version of it.

    A material change to what a rule concludes **must** change
    ``version``. Two results carrying the same rule id and version and
    the same governed inputs are required to agree; that promise is only
    keepable if the version moves when the behaviour does.
    """

    rule_id: str
    rule_version: str
    family: ReasoningRuleFamily

    @property
    def identity(self) -> str:
        return f"{self.rule_id}@{self.rule_version}"


# --- Diagnostics ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReasoningDiagnostics:
    """
    Deterministic, machine-readable account of one evaluation.

    Counts and closed enum values only - no free text, no score, and no
    quality judgement. ``duration_seconds`` is operational, varies run to
    run, and is excluded from result identity for exactly that reason.
    """

    code: ReasoningDiagnosticCode
    required_input_count: int
    available_input_count: int
    contributing_input_count: int
    candidate_subject_count: int
    distinct_value_count: int
    distinct_unit_count: int
    subject_retrieval_outcome: GovernedMatchOutcome | None
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class StructuralReasoningDiagnostics:
    """
    Deterministic, machine-readable account of one structural
    evaluation.

    A separate type from `ReasoningDiagnostics` rather than a widened
    one: counting distinct *values* and distinct *units* is meaningless
    for a relationship question, and a shared type would have carried two
    fields that are always zero here and two that are always zero there.

    Counts and closed enum values only. ``duration_seconds`` is
    operational, varies run to run, and is excluded from result identity
    for exactly that reason.
    """

    code: StructuralReasoningDiagnosticCode
    left_location_count: int
    right_location_count: int
    contributing_input_count: int
    subject_retrieval_outcome: GovernedMatchOutcome | None
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class SharedLocationInferencePath:
    """
    The ordered governed path a positive conclusion rests on.

    ```
    left asset  --left edge-->  location  <--right edge--  right asset
    ```

    Every element is a governed identity, and all five are kept. Reducing
    this to "A and B share X" would discard exactly what makes the
    conclusion checkable: *which* two approved statements put them there.
    An engineer disputing the conclusion disputes one of these edges, and
    cannot do so if the result never named them.

    The path is stored in **canonical order** - the two sides sorted by
    asset identity - so the same conclusion has the same path whichever
    way round it was asked. The query keeps the order the caller used.
    """

    left_asset_node_id: str
    left_edge_id: str
    location_node_id: str
    right_edge_id: str
    right_asset_node_id: str

    @property
    def governed_identities(self) -> tuple[str, ...]:
        """Every governed identity the inference read, in path order."""

        return (
            self.left_asset_node_id,
            self.left_edge_id,
            self.location_node_id,
            self.right_edge_id,
            self.right_asset_node_id,
        )


@dataclass(frozen=True, slots=True)
class SharedStructuralLocationAssessment:
    """
    The family-specific part of a structural relationship conclusion.

    Carried beside the common result metadata rather than merged into it,
    so a consumer can tell a quantity conclusion from a structural one
    **by type**, without reading prose and without a property bag.

    ``derived_relationship`` and ``shared_location_node_id`` are populated
    only for `ESTABLISHED`: a rule that named a derived relationship it
    had not established would be asserting the conclusion in the shape of
    a field.
    """

    outcome: StructuralReasoningOutcome
    diagnostics: StructuralReasoningDiagnostics
    derived_relationship: DerivedRelationshipKind | None
    shared_location_node_id: str | None
    shared_location_label: str | None
    inference_path: SharedLocationInferencePath | None

    @property
    def is_established(self) -> bool:
        return self.outcome is StructuralReasoningOutcome.ESTABLISHED


#: Every question a reasoning rule may be asked. Closed on purpose: a new
#: member is a new reasoning capability, reviewed as such.
ReasoningQuery = QuantityConsistencyQuery | SharedStructuralLocationQuery


# --- The conclusion ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReasoningResult:
    """
    One deterministic engineering conclusion.

    **Derived, and never governed knowledge.** It is not promoted, not
    reviewable, and not persisted as engineering truth. If a conclusion
    should ever become governed knowledge, it must travel the same route
    as everything else: a semantic statement an engineer approves
    (AF-REASON-003). Nothing here shortens that route.

    ``result_id`` is deterministic (``reasoning_identity``): the same
    query, rule version and governed inputs produce the same identity on
    any machine. ``evaluated_at`` is operational and is deliberately not
    part of it.
    """

    result_id: str
    query: ReasoningQuery
    rule: ReasoningRuleIdentity
    outcome: ReasoningOutcome | StructuralReasoningOutcome
    contributors: tuple[ReasoningContributor, ...]
    diagnostics: ReasoningDiagnostics | StructuralReasoningDiagnostics
    reasoning_policy_version: str
    context_assembly_version: str | None
    evaluated_at: datetime

    #: The family-specific conclusion, when the family has one.
    #:
    #: ``None`` for quantity consistency, whose whole conclusion is its
    #: outcome and its contributors. Populated for structural
    #: relationship reasoning, which additionally has a derived
    #: relationship, a shared location and an inference path to report.
    #:
    #: **Not a property bag**: it is one typed value object per family,
    #: and `rule.family` says which one to expect. A consumer switching
    #: on the family gets a static type, not a dictionary lookup.
    structural: SharedStructuralLocationAssessment | None = None

    @property
    def is_derived(self) -> bool:
        """
        Always true, and it is here to be read.

        A reasoning result is an inference. Anything reading one at a
        boundary - a prompt, a response, an API - can state that without
        having to know what produced it.
        """

        return True

    @property
    def has_governed_support(self) -> bool:
        """
        Whether any governed knowledge contributed.

        False whenever a rule reached its outcome without reading any
        governed input - a question with no subject, or an ambiguity
        settled before any knowledge was consulted.

        It is **not** a synonym for a positive outcome. A structural
        conclusion of `INSUFFICIENT_KNOWLEDGE` may rest on two governed
        relationships that were read, compared, and found to name
        different locations; that knowledge contributed, and the result
        names it.
        """

        return bool(self.contributors)
