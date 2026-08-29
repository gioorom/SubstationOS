"""
Value objects for Governed Structured Retrieval (EPIC 31.2).

Every type is immutable and deterministic: the same governed graph and
the same query always produce the same result - the same items, in the
same order, with the same identities, the same match strategies and the
same provenance. Nothing here performs I/O, calls a provider, or carries
free text intended for natural-language interpretation.

---

## What a query is, and what it is not

A query is a **closed set of typed fields**, never a question. There is
no free-text field, no property filter, no operator, no expression and
no query language: an engineer asks one of five things, and each of the
five is a dataclass whose fields say exactly what it may ask.

## What a result is

A result is a **reference to governed knowledge plus the reason it was
returned**. It copies a label and a normalized value so an answer is
readable, and it copies nothing else: the statement, the facts, the
entities and the evidence stay in the pipeline, which remains their
single account. Everything else is identity - node id, edge id, review
id, document id, statement key - so there is exactly one copy of every
engineering artefact in this system.

## Provenance is not optional

``GovernedRetrievalItem.provenance`` has no default and no ``| None``.
An item that could not state where it came from cannot be constructed,
which is the same guarantee the governed graph itself enforces with
``nullable=False`` columns. A missing answer is visibly missing; an
untraceable one looks exactly like a good one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedQueryType,
    GovernedResultKind,
    RetrievalScope,
)

# --- Queries -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AssetDesignationQuery:
    """
    "Which governed assets does this designation name?"

    ``designation`` is preserved exactly as the engineer wrote it - the
    folds live in ``governed_normalization`` and are applied at match
    time, so the query always reports what was asked rather than what it
    was reduced to.

    ``project_id`` and ``document_id`` are **filters on governed
    provenance**, not authorization. Authorization is the router's
    responsibility and stays there (see ``security_architecture.md``).
    """

    designation: str
    scope: RetrievalScope
    limit: int
    project_id: int | None = None
    document_id: int | None = None

    query_type = GovernedQueryType.ASSET_BY_DESIGNATION


@dataclass(frozen=True, slots=True)
class AssetQuantityQuery:
    """
    "What quantities does governed knowledge assert about this asset?"

    The asset is named either by designation or by governed node id, and
    exactly one of the two is set (``governed_retrieval_validator``).
    Naming it by designation can resolve to **several** assets - two
    documents may each designate a ``TR1`` - and the result says so
    rather than picking one: see ``GovernedMatchOutcome``.

    ``edge_kind`` narrows to one governed relationship kind. Left unset,
    every governed relationship the asset participates in as subject is
    traversed.
    """

    scope: RetrievalScope
    limit: int
    designation: str | None = None
    subject_node_id: str | None = None
    edge_kind: GraphEdgeKind | None = None
    project_id: int | None = None
    document_id: int | None = None

    query_type = GovernedQueryType.QUANTITY_FOR_ASSET


@dataclass(frozen=True, slots=True)
class RelationshipQuery:
    """"Which governed relationships exist, of this kind, in this
    scope?" - the governed successor to the legacy relationship
    search."""

    scope: RetrievalScope
    limit: int
    edge_kind: GraphEdgeKind | None = None
    project_id: int | None = None
    document_id: int | None = None

    query_type = GovernedQueryType.RELATIONSHIPS


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeQuery:
    """
    "What governed knowledge came out of this document?"

    Answers with the assets, quantities and relationships whose
    provenance names the document - which is the only sense in which
    governed knowledge belongs to a document, since the graph stores
    provenance rather than a foreign key.
    """

    document_id: int
    scope: RetrievalScope
    limit: int
    project_id: int | None = None

    query_type = GovernedQueryType.DOCUMENT_KNOWLEDGE


@dataclass(frozen=True, slots=True)
class GovernedIdentityQuery:
    """
    "What is this governed object, and where did it come from?"

    Exactly one of ``node_id``/``edge_id`` is set. This is also the
    provenance query: every result carries its full provenance, so
    asking for provenance is asking for the object by identity rather
    than for a second, differently-shaped resource.
    """

    scope: RetrievalScope
    node_id: str | None = None
    edge_id: str | None = None

    query_type = GovernedQueryType.GOVERNED_IDENTITY


#: Every shape a caller may ask. Closed on purpose: a new member is a
#: new governed capability, reviewed as such.
GovernedRetrievalQuery = (
    AssetDesignationQuery
    | AssetQuantityQuery
    | RelationshipQuery
    | DocumentKnowledgeQuery
    | GovernedIdentityQuery
)


# --- Results -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GovernedProvenanceView:
    """
    Where one returned piece of governed knowledge came from.

    A field-for-field read model of ``GraphProvenance``: retrieval copies
    it rather than re-deriving any part of it, and adds nothing. The
    chain an engineer can walk from here is

    ``statement_key → review_id → support_fingerprint → document_id``,

    each of which addresses an artefact that already has its own API.
    """

    statement_key: str
    document_id: int
    content_checksum: str
    review_id: int
    reviewer_user_id: int
    reviewer_display_name: str
    reviewed_at: datetime
    semantic_rule_id: str
    semantic_rule_version: str
    semantic_contract_version: str
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    support_fingerprint: str
    project_id: int | None


@dataclass(frozen=True, slots=True)
class GovernedNodeReference:
    """A governed node, by identity and by the label that makes it
    readable. Never a copy of the pipeline entity it projects."""

    node_id: str
    kind: GraphNodeKind
    label: str
    normalized_value: str
    unit: str | None


@dataclass(frozen=True, slots=True)
class GovernedRelationshipReference:
    """One governed relationship, with both endpoints resolved so a
    caller never has to issue a second query to read the answer."""

    edge_id: str
    kind: GraphEdgeKind
    subject: GovernedNodeReference
    object: GovernedNodeReference


@dataclass(frozen=True, slots=True)
class GovernedMatchExplanation:
    """
    The deterministic answer to "why did this match?".

    ``matched_field`` names the governed field that was compared and
    ``matched_value`` carries its value, so the explanation stands on its
    own. ``normalized_query`` is the fold that was applied, or ``None``
    for a query that compares no text at all.
    """

    strategy: GovernedMatchStrategy
    matched_field: str
    matched_value: str
    normalized_query: str | None = None


@dataclass(frozen=True, slots=True)
class GovernedRetrievalItem:
    """
    One piece of retrieved governed knowledge.

    ``result_id`` is derived from governed identity alone
    (``governed_result_identity``) - never from a clock, a counter or a
    row order - so the same graph and the same query produce the same
    identifiers on any machine, forever.

    ``state`` and ``retirement_reason`` are present on every item rather
    than only on historical ones: a caller reading a mixed-scope result
    must be able to tell current knowledge from what the platform used to
    assert without inferring it from the query it sent.
    """

    result_id: str
    kind: GovernedResultKind
    node: GovernedNodeReference | None
    relationship: GovernedRelationshipReference | None
    state: GraphObjectState
    retirement_reason: GraphRetirementReason | None
    match: GovernedMatchExplanation
    provenance: GovernedProvenanceView
    sort_key: tuple[int, str, str, str]

    @property
    def is_current(self) -> bool:
        return self.state is GraphObjectState.ACTIVE


@dataclass(frozen=True, slots=True)
class GovernedGraphVersion:
    """
    Which projection answered.

    Global by construction: a generation covers the whole installation
    (``knowledge_graph.md`` §8). The per-object versions - rule, contract
    and the three policy versions - are on each item's provenance, where
    they genuinely vary.
    """

    generation_number: int | None
    generation_created_at: datetime | None
    promotion_contract_version: str | None


@dataclass(frozen=True, slots=True)
class GovernedRetrievalDiagnostics:
    """
    Deterministic diagnostic information about one execution.

    Not an explanation in the natural-language sense and not a quality
    score: every field is a count, a version or a closed enum value.

    ``duration_seconds`` deliberately varies run to run and is the one
    field that must never enter a determinism assertion - the same rule
    the legacy ``RetrievalExecutionMetadata`` already carried.
    """

    query_type: GovernedQueryType
    scope: RetrievalScope
    normalized_query: str | None
    strategies_attempted: tuple[GovernedMatchStrategy, ...]
    candidates_examined: int
    matched_count: int
    returned_count: int
    ambiguous: bool
    no_match: bool
    normalization_version: str
    matching_policy_version: str
    graph_version: GovernedGraphVersion
    duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class GovernedRetrievalResult:
    """
    What one query returned.

    ``outcome`` is computed from ``total_before_limit``, never from the
    returned page: a limit must not be able to turn several governed
    answers into one apparently certain one.
    """

    query: GovernedRetrievalQuery
    outcome: GovernedMatchOutcome
    items: tuple[GovernedRetrievalItem, ...]
    total_before_limit: int
    applied_limit: int
    diagnostics: GovernedRetrievalDiagnostics
    retrieved_at: datetime

    @property
    def is_ambiguous(self) -> bool:
        return self.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
