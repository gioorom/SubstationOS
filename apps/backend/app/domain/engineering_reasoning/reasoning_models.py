"""
Value objects for deterministic engineering reasoning (EPIC 32.1).

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
conflicting statements names both; reducing that to one "primary"
statement would make the conflict unexplainable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.context_builder.context_builder_models import ContextItem
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
    ReasoningRuleFamily,
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
    query: QuantityConsistencyQuery
    rule: ReasoningRuleIdentity
    outcome: ReasoningOutcome
    contributors: tuple[ReasoningContributor, ...]
    diagnostics: ReasoningDiagnostics
    reasoning_policy_version: str
    context_assembly_version: str | None
    evaluated_at: datetime

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
        """Whether any governed knowledge contributed. False for
        ``INSUFFICIENT_KNOWLEDGE``, and that is the honest reading."""

        return bool(self.contributors)
