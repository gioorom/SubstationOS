"""
Value objects for Context Builder (EPIC 4, Milestone 14). Every type
here is immutable and deterministic: the same
``KnowledgeCandidateCollection`` and the same ``ContextBuilderConfiguration``
always produce the same ``ContextPackage``, including selection order,
coverage, statistics, and warnings. Context Builder consumes Structured
Retrieval's own output type (``KnowledgeCandidateCollection``,
``KnowledgeCandidate``) as its shared, stable input vocabulary - the
same "reuse the upstream read-oriented type" pattern Structured
Retrieval itself established for Graph Query's ``GraphNodeView``/
``GraphRelationshipView``. No type in this module performs I/O, calls
an AI provider, or interprets natural language - assembly is bounded,
provenance-aware selection and reporting over already-retrieved,
already-scored knowledge, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateCollection,
    KnowledgeCandidateKind,
)


class BudgetCategory(str, Enum):
    """Every dimension Context Builder's budget bounds - a closed,
    exhaustive set, never an open-ended free-form category."""

    CANDIDATES = "candidates"
    ENTITIES = "entities"
    RELATIONSHIPS = "relationships"
    ATTRIBUTES = "attributes"
    METADATA_ENTRIES = "metadata_entries"
    WARNINGS = "warnings"


class CoverageCategory(str, Enum):
    ENTITY_COVERAGE = "entity_coverage"
    RELATIONSHIP_COVERAGE = "relationship_coverage"
    ATTRIBUTE_COVERAGE = "attribute_coverage"
    CANDIDATE_UTILIZATION = "candidate_utilization"
    CONTEXT_COMPLETENESS = "context_completeness"


class ContextWarningCategory(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    CANDIDATE_DISCARDED = "candidate_discarded"
    MISSING_PROVENANCE = "missing_provenance"
    MISSING_ATTRIBUTES = "missing_attributes"
    MISSING_RELATIONSHIPS = "missing_relationships"
    PARTIAL_COVERAGE = "partial_coverage"


@dataclass(frozen=True, slots=True)
class ContextSelectionPolicy:
    """The versioned, documented selection ordering Context Builder
    applies - never random, never heuristic. Candidates are ordered by
    (highest score, candidate kind priority, entity/natural identity,
    candidate identity), the same convention Structured Retrieval's own
    ``KnowledgeCandidate.sort_key`` documents (see
    ``docs/architecture/structured_retrieval.md``'s "Result Ordering"),
    computed independently here from public ``KnowledgeCandidate``
    fields rather than trusting an upstream-computed ``sort_key`` that
    the API wire format does not even carry (see ``candidate_selection.py``)."""

    version: str


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """The fixed, configurable limits Context Builder enforces while
    assembling one ``ContextPackage``. A caller may narrow these limits
    per request; Context Builder never widens them beyond the
    documented bounds in ``context_builder_validator.py``."""

    version: str
    max_candidates: int
    max_entities: int
    max_relationships: int
    max_attributes: int
    max_metadata_entries: int
    max_warnings: int


@dataclass(frozen=True, slots=True)
class ContextBuilderConfiguration:
    """Everything about *how* one assembly run behaves - never *what*
    it assembles (that is ``ContextBuildRequest.candidates``)."""

    budget_policy: BudgetPolicy
    selection_policy: ContextSelectionPolicy
    context_builder_version: str


@dataclass(frozen=True, slots=True)
class ContextMetadataEntry:
    """One caller-supplied, budget-capped supplementary metadata
    entry - e.g. an echo of the originating Structured Retrieval
    request's mode, for audit/debugging. Never used to carry secrets."""

    key: str
    value: str


@dataclass(frozen=True, slots=True)
class DiscardedCandidate:
    """One candidate Selection ranked but did not admit into the
    package, and the specific budget dimension responsible."""

    candidate: KnowledgeCandidate
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
    """A named, bounded slice of admitted candidates sharing one
    ``KnowledgeCandidateKind`` - the Aggregation stage's own grouping
    unit, kept internal to ``ContextAssemblyResult`` (the final
    ``ContextPackage`` exposes the same data through its own
    kind-specific fields, per Milestone 14's explicit contract, rather
    than duplicating it a second time as stored ``ContextPackage``
    fields)."""

    kind: KnowledgeCandidateKind
    candidates: tuple[KnowledgeCandidate, ...]
    candidate_count: int


@dataclass(frozen=True, slots=True)
class SelectionOutcome:
    """The Selection stage's full, inspectable output: which candidates
    were admitted, which were discarded and why, and the raw budget
    consumption for the candidate-count and per-kind dimensions."""

    selected: tuple[KnowledgeCandidate, ...]
    discarded: tuple[DiscardedCandidate, ...]
    consumption: tuple[BudgetConsumption, ...]


@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    """The Aggregation stage's output: Selection's admitted candidates,
    grouped into ``ContextSection``s by kind and also exposed as the
    three kind-specific tuples ``ContextPackage`` itself carries -
    computed once, here, and threaded through unchanged."""

    selected_candidates: tuple[KnowledgeCandidate, ...]
    sections: tuple[ContextSection, ...]
    selected_entities: tuple[KnowledgeCandidate, ...]
    selected_relationships: tuple[KnowledgeCandidate, ...]
    selected_attributes: tuple[KnowledgeCandidate, ...]


@dataclass(frozen=True, slots=True)
class RetrievalSummary:
    """A compact, honest echo of the ``KnowledgeCandidateCollection``
    Context Builder received - never recomputed, reinterpreted, or used
    to second-guess Structured Retrieval's own ranking. Retrieval
    itself remains Structured Retrieval's exclusive responsibility."""

    retrieved_candidate_count: int
    total_before_limit: int
    applied_limit: int
    retrieved_entity_count: int
    retrieved_relationship_count: int
    retrieved_attribute_count: int


@dataclass(frozen=True, slots=True)
class CoverageMetric:
    """One named coverage measurement: how much of what was available
    (``available_count``) was actually selected (``selected_count``).
    ``ratio`` is a selection-completeness fraction, never an engineering
    confidence score - Context Builder does not, and must not, invent
    certainty about the underlying facts."""

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
    """One structured, machine-readable warning. ``candidate_id`` is
    populated only when the warning concerns one specific candidate
    (e.g. a discard or a missing-provenance note); left ``None`` for
    package-wide warnings (e.g. partial coverage)."""

    category: ContextWarningCategory
    message: str
    candidate_id: str | None = None


@dataclass(frozen=True, slots=True)
class ContextStatistics:
    selected_candidate_count: int
    discarded_candidate_count: int
    entity_count: int
    relationship_count: int
    attribute_count: int
    coverage_summary: CoverageReport
    budget_summary: ContextBudget


@dataclass(frozen=True, slots=True)
class ContextMetadata:
    context_builder_version: str
    assembled_at: datetime
    selection_policy_version: str
    budget_policy_version: str
    retrieval_policy_version: str | None
    entries: tuple[ContextMetadataEntry, ...]


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """
    The bounded, structured, explainable artifact Context Builder
    produces - the official contract between the deterministic
    knowledge platform and every future AI capability. Suitable for a
    future Prompt Builder, frontend inspection, API export, engineering
    audit, and debugging, exactly as Milestone 14 requires. Carries no
    ORM object, no persistence model, and no free-text prompt of any
    kind.
    """

    project_id: int
    retrieval_summary: RetrievalSummary
    selected_entities: tuple[KnowledgeCandidate, ...]
    selected_relationships: tuple[KnowledgeCandidate, ...]
    selected_attributes: tuple[KnowledgeCandidate, ...]
    selected_candidates: tuple[KnowledgeCandidate, ...]
    coverage: CoverageReport
    statistics: ContextStatistics
    warnings: tuple[ContextWarning, ...]
    budget: ContextBudget
    metadata: ContextMetadata


@dataclass(frozen=True, slots=True)
class ContextBuildRequest:
    """
    A fully validated request to assemble one ``ContextPackage``. Never
    constructed directly - always via
    ``ContextBuildRequestFactory.create``, which enforces every
    invariant (positive project id, budget policy bounds, non-blank
    metadata entry keys) at construction time.
    """

    project_id: int
    candidates: KnowledgeCandidateCollection
    configuration: ContextBuilderConfiguration
    metadata_entries: tuple[ContextMetadataEntry, ...]
    retrieval_policy_version: str | None


@dataclass(frozen=True, slots=True)
class ContextBuilderResult:
    """The full envelope one Context Builder execution returns - the
    request's own project id and configuration, paired with the
    resulting ``ContextPackage``."""

    project_id: int
    configuration: ContextBuilderConfiguration
    package: ContextPackage
