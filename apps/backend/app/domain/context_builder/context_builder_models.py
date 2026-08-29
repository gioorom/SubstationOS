"""
Value objects for Governed Context Assembly (EPIC 31.3).

Context Assembly organizes **governed** engineering knowledge for
downstream reasoning. It creates no knowledge, infers no relationship,
resolves no identity, approves nothing, and ranks nothing by confidence.
Retrieval decided *what matched*; this context decides *how those
governed results are represented as context*, and that is the whole of
its responsibility.

Every type here is immutable and deterministic: the same
``GovernedRetrievalResult``s and the same ``ContextAssemblyConfiguration``
always produce the same ``ContextPackage``, including selection order,
coverage, statistics and warnings.

---

## What changed in EPIC 31.3, and why

Until this milestone Context Builder consumed
``KnowledgeCandidateCollection`` - the legacy Structured Retrieval
vocabulary - and the Engineering Engine reached it through a temporary
adapter (``governed_context_projection.py``) that mapped governed
results into candidates. That adapter is gone, and with it three things
it had to carry:

- a **score**, which was an ordering value shaped like a confidence;
- ``GraphEntityId``/``GraphRelationshipType``, legacy Canonical Facts
  types with no governed meaning;
- a provenance model that could be empty, because a legacy candidate's
  strongest origin was a ``GraphExecution`` id.

## Why a ``ContextItem`` wraps a governed result rather than copying it

``ContextItem`` holds the ``GovernedRetrievalItem`` itself plus the
``ContextItemOrigin`` describing the query that produced it. It copies
**no** engineering payload:

- provenance is structurally mandatory, because it is mandatory on the
  governed item and there is nowhere here for it to be dropped;
- ambiguity survives, because the origin carries the retrieval outcome;
- there is exactly one representation of a governed answer in this
  system, so no two copies can disagree.

This is the same "reuse the upstream read-oriented type" pattern Context
Builder already followed for ``KnowledgeCandidate`` - pointed at a type
that is worth reusing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalItem,
    GovernedRetrievalResult,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedQueryType,
    GovernedResultKind,
    RetrievalScope,
)


class BudgetCategory(str, Enum):
    """Every dimension Context Assembly bounds - a closed, exhaustive
    set, never an open-ended free-form category."""

    ITEMS = "items"
    ASSETS = "assets"
    QUANTITIES = "quantities"
    RELATIONSHIPS = "relationships"
    METADATA_ENTRIES = "metadata_entries"
    WARNINGS = "warnings"


class CoverageCategory(str, Enum):
    ASSET_COVERAGE = "asset_coverage"
    QUANTITY_COVERAGE = "quantity_coverage"
    RELATIONSHIP_COVERAGE = "relationship_coverage"
    ITEM_UTILIZATION = "item_utilization"
    CONTEXT_COMPLETENESS = "context_completeness"


class ContextWarningCategory(str, Enum):
    """
    What a context can honestly warn about.

    ``MISSING_PROVENANCE`` is **gone** as of EPIC 31.3, and its absence
    is the point: a governed item cannot be constructed without
    provenance, so a warning about missing provenance would describe a
    state the platform can no longer produce. A warning that can never
    fire is worse than no warning - it reads as reassurance.

    ``AMBIGUOUS_RETRIEVAL`` and ``UNSUPPORTED_CRITERIA`` replace it, and
    both describe things that genuinely happen.
    """

    BUDGET_EXCEEDED = "budget_exceeded"
    ITEM_DISCARDED = "item_discarded"
    AMBIGUOUS_RETRIEVAL = "ambiguous_retrieval"
    MISSING_QUANTITIES = "missing_quantities"
    MISSING_RELATIONSHIPS = "missing_relationships"
    PARTIAL_COVERAGE = "partial_coverage"


@dataclass(frozen=True, slots=True)
class ContextItemOrigin:
    """
    Which governed retrieval answered, and how certainly.

    Carried per item rather than per package because one context may be
    assembled from several governed queries - a designation lookup and a
    quantity traversal, or one query per designation the request named -
    and "which of them was ambiguous?" must stay answerable.

    ``matched_before_limit`` is the count **retrieval** saw, not the
    count that entered this context. A downstream reader that only knew
    the second could not tell a complete answer from a truncated one.
    """

    query_type: GovernedQueryType
    outcome: GovernedMatchOutcome
    scope: RetrievalScope
    normalized_query: str | None
    matched_before_limit: int

    @property
    def is_ambiguous(self) -> bool:
        return self.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES


@dataclass(frozen=True, slots=True)
class ContextItem:
    """
    One governed result admitted into a context.

    ``result`` is the untouched ``GovernedRetrievalItem`` - so the
    governed identity, the match strategy that explains it, and the
    mandatory provenance travel with it and cannot be dropped on the way
    through. ``origin`` is the only thing Context Assembly adds, and it
    is about the *query*, never about the knowledge.
    """

    result: GovernedRetrievalItem
    origin: ContextItemOrigin

    @property
    def item_id(self) -> str:
        """Governed identity. Deterministic, never a counter or a
        clock - see ``governed_result_identity``."""

        return self.result.result_id

    @property
    def kind(self) -> GovernedResultKind:
        return self.result.kind

    @property
    def order_key(self) -> tuple[int, str, str, str]:
        """
        The order retrieval already decided.

        Context Assembly re-sorts by this key rather than trusting the
        order a caller happened to pass, and adds nothing of its own:
        re-ranking governed results would be Context Assembly deciding
        which knowledge matters, which is retrieval's judgement and not
        its own.
        """

        return self.result.sort_key


@dataclass(frozen=True, slots=True)
class ContextSelectionPolicy:
    """The versioned, documented selection ordering Context Assembly
    applies - never random, never heuristic, and **never a score**.
    Items are ordered by the governed retrieval sort key (match strategy
    precedence, then folded labels, then governed identity) and then by
    item identity; see ``item_selection.py``."""

    version: str


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """The fixed, configurable limits Context Assembly enforces while
    assembling one ``ContextPackage``. A caller may narrow these limits
    per request; Context Assembly never widens them beyond the
    documented bounds in ``context_builder_validator.py``."""

    version: str
    max_items: int
    max_assets: int
    max_quantities: int
    max_relationships: int
    max_metadata_entries: int
    max_warnings: int


@dataclass(frozen=True, slots=True)
class ContextAssemblyConfiguration:
    """Everything about *how* one assembly run behaves - never *what*
    it assembles (that is ``ContextBuildRequest.results``)."""

    budget_policy: BudgetPolicy
    selection_policy: ContextSelectionPolicy
    context_assembly_version: str


@dataclass(frozen=True, slots=True)
class ContextMetadataEntry:
    """One caller-supplied, budget-capped supplementary metadata
    entry - e.g. an echo of the originating request's designation, for
    audit and debugging. Never used to carry secrets."""

    key: str
    value: str


@dataclass(frozen=True, slots=True)
class DiscardedItem:
    """One item Selection ranked but did not admit into the package, and
    the specific budget dimension responsible."""

    item: ContextItem
    reason: BudgetCategory


@dataclass(frozen=True, slots=True)
class BudgetConsumption:
    """How much of one budget dimension was requested, accepted, and
    discarded - always derived, never asserted independently of the
    admission decisions that produced it."""

    category: BudgetCategory
    requested: int
    accepted: int
    discarded: int
    limit: int
    utilization: float


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """The full budget report for one ``ContextPackage``: the policy in
    effect, per-dimension consumption, and whether any dimension was
    exceeded (``discarded > 0`` for at least one ``BudgetConsumption``)."""

    policy: BudgetPolicy
    consumption: tuple[BudgetConsumption, ...]
    exceeded: bool


@dataclass(frozen=True, slots=True)
class ContextSection:
    """A named, bounded slice of admitted items sharing one
    ``GovernedResultKind`` - the Aggregation stage's own grouping unit,
    kept internal to ``ContextAssemblyResult``; the final
    ``ContextPackage`` exposes the same data through its own
    kind-specific fields rather than duplicating it a second time."""

    kind: GovernedResultKind
    items: tuple[ContextItem, ...]
    item_count: int


@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    """The Selection stage's full, inspectable output: which items were
    admitted, which were discarded and why, and the raw budget
    consumption for the item-count and per-kind dimensions."""

    selected: tuple[ContextItem, ...]
    discarded: tuple[DiscardedItem, ...]
    consumption: tuple[BudgetConsumption, ...]


@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    """The Aggregation stage's output: Selection's admitted items,
    grouped into ``ContextSection``s by kind and also exposed as the
    three kind-specific tuples ``ContextPackage`` itself carries -
    computed once, here, and threaded through unchanged."""

    selected_items: tuple[ContextItem, ...]
    sections: tuple[ContextSection, ...]
    selected_assets: tuple[ContextItem, ...]
    selected_quantities: tuple[ContextItem, ...]
    selected_relationships: tuple[ContextItem, ...]


@dataclass(frozen=True, slots=True)
class GovernedQuerySummary:
    """
    One governed query's outcome, echoed rather than recomputed.

    Kept per query so ambiguity cannot be averaged away: a context
    assembled from a unique match and an ambiguous one is not "somewhat
    ambiguous", it is a context in which one specific question had more
    than one governed answer.
    """

    query_type: GovernedQueryType
    outcome: GovernedMatchOutcome
    scope: RetrievalScope
    normalized_query: str | None
    matched_before_limit: int
    returned_count: int


@dataclass(frozen=True, slots=True)
class RetrievalSummary:
    """
    A compact, honest echo of the governed results Context Assembly
    received - never recomputed, reinterpreted, or used to second-guess
    retrieval's own ordering. Retrieval remains Governed Structured
    Retrieval's exclusive responsibility.
    """

    retrieved_item_count: int
    total_before_limit: int
    retrieved_asset_count: int
    retrieved_quantity_count: int
    retrieved_relationship_count: int
    queries: tuple[GovernedQuerySummary, ...]

    @property
    def any_ambiguous(self) -> bool:
        return any(
            query.outcome is GovernedMatchOutcome.MULTIPLE_MATCHES
            for query in self.queries
        )

    @property
    def all_no_match(self) -> bool:
        return bool(self.queries) and all(
            query.outcome is GovernedMatchOutcome.NO_MATCH
            for query in self.queries
        )


@dataclass(frozen=True, slots=True)
class CoverageMetric:
    """One named coverage measurement: how much of what was available
    (``available_count``) was actually selected (``selected_count``).
    ``ratio`` is a selection-completeness fraction, **never** an
    engineering confidence score - Context Assembly does not, and must
    not, invent certainty about the underlying knowledge."""

    category: CoverageCategory
    selected_count: int
    available_count: int
    ratio: float


@dataclass(frozen=True, slots=True)
class CoverageReport:
    metrics: tuple[CoverageMetric, ...]
    overall_completeness: float


@dataclass(frozen=True, slots=True)
class ContextWarning:
    """One structured, machine-readable warning. ``item_id`` is
    populated only when the warning concerns one specific governed item
    (e.g. a discard); left ``None`` for package-wide warnings (e.g.
    partial coverage or an ambiguous retrieval)."""

    category: ContextWarningCategory
    message: str
    item_id: str | None = None


@dataclass(frozen=True, slots=True)
class ContextStatistics:
    selected_item_count: int
    discarded_item_count: int
    asset_count: int
    quantity_count: int
    relationship_count: int
    coverage_summary: CoverageReport
    budget_summary: ContextBudget


@dataclass(frozen=True, slots=True)
class ContextMetadata:
    context_assembly_version: str
    assembled_at: datetime
    selection_policy_version: str
    budget_policy_version: str
    retrieval_normalization_version: str | None
    retrieval_matching_policy_version: str | None
    graph_generation_number: int | None
    entries: tuple[ContextMetadataEntry, ...]


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """
    The bounded, structured, explainable artifact Context Assembly
    produces - the contract between governed knowledge and every
    reasoning capability downstream. Suitable for Prompt Builder,
    frontend inspection, API export, engineering audit and debugging.
    Carries no ORM object, no persistence model, and no free-text prompt
    of any kind.

    **Every item carries governed provenance**, structurally: an item
    holds a ``GovernedRetrievalItem``, whose ``provenance`` has no
    default and no ``| None``. There is no path by which a governed
    context loses the review that authorised its content.
    """

    project_id: int
    retrieval_summary: RetrievalSummary
    selected_assets: tuple[ContextItem, ...]
    selected_quantities: tuple[ContextItem, ...]
    selected_relationships: tuple[ContextItem, ...]
    selected_items: tuple[ContextItem, ...]
    coverage: CoverageReport
    statistics: ContextStatistics
    warnings: tuple[ContextWarning, ...]
    budget: ContextBudget
    metadata: ContextMetadata

    @property
    def is_ambiguous(self) -> bool:
        """Whether any governed query that fed this context matched more
        than one governed object. Downstream code must be able to ask
        this without re-deriving it from item counts."""

        return self.retrieval_summary.any_ambiguous


@dataclass(frozen=True, slots=True)
class ContextBuildRequest:
    """
    A fully validated request to assemble one ``ContextPackage``. Never
    constructed directly - always via
    ``ContextBuildRequestFactory.create``, which enforces every
    invariant (positive project id, budget policy bounds, non-blank
    metadata entry keys) at construction time.

    The input is a tuple of **governed retrieval results**, in the order
    the caller executed them. Context Assembly reads nothing else: it
    issues no query of its own, and cannot reach knowledge outside what
    retrieval already returned under its own scope and authorization.
    """

    project_id: int
    results: tuple[GovernedRetrievalResult, ...]
    configuration: ContextAssemblyConfiguration
    metadata_entries: tuple[ContextMetadataEntry, ...]


@dataclass(frozen=True, slots=True)
class ContextBuilderResult:
    """The full envelope one Context Assembly execution returns - the
    request's own project id and configuration, paired with the
    resulting ``ContextPackage``."""

    project_id: int
    configuration: ContextAssemblyConfiguration
    package: ContextPackage
