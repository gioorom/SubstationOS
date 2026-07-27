"""
Deterministic performance baseline for the Project Knowledge Graph
execution path, the Graph Query read model (Milestone 12, Workstream
6), Structured Retrieval (Milestone 13), Context Builder (Milestone
14), Prompt Builder (Milestone 15), the LLM Provider Abstraction Layer
and LLM Invocation Runtime (Milestones 16-17), and Engineering Response
(Milestone 18).

This is a *measurement* script, not a correctness test and not a
performance-optimization milestone. It generates synthetic, non-
confidential fixtures at two fixed sizes and times: node upsert,
relationship upsert, a medium GraphOperationBatch execution, list
nodes, list relationships, statistics, orphan detection, attribute
filtering, a 1-hop neighborhood query (Milestone 12), exact entity
lookup, entity-type, relationship-type, lexical, combined, and
neighborhood-enriched Structured Retrieval (Milestone 13), Context
Builder assembly over a combined-mode KnowledgeCandidateCollection,
both within budget and under a tight budget that forces discards
(Milestone 14), and Prompt Builder composition over the resulting
ContextPackage (Milestone 15).

Run directly for a full report (small + medium):

    python -m scripts.benchmarks.graph_performance_benchmark

Results are printed, not asserted - there is no pass/fail threshold
here, only recorded methodology and numbers (see
docs/architecture/performance_baseline.md for the last recorded run).
The pytest smoke test (tests/benchmarks/test_graph_performance_benchmark_smoke.py)
exercises the small dataset only, asserting the code runs and produces
sane row counts - never a wall-clock threshold, per the milestone's
"no flaky wall-clock assertions in the normal suite" rule.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base

# Imported for their side effect of registering every table/relationship
# with the ORM mapper before Base.metadata.create_all() runs - the same
# reason app/main.py imports this exact module set (see the comment
# there). Without this, only the models this script directly touches
# would be mapped, and create_all() would fail resolving foreign keys
# into tables (e.g. graph_operations -> canonical_facts) that were
# never imported.
from app.models import (  # noqa: F401
    canonicalization,
    document,
    engineering_index,
    graph_builder,
    knowledge_graph,
    project,
    project_knowledge_graph,
    proposed_claims,
    review_workflow,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperationBatch,
    GraphOperationBatchScope,
    GraphOperationBatchSource,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
    GraphRelationshipType,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
    LexicalMatchMode,
    RetrievalMode,
)
from app.domain.context_builder.context_builder_factory import (
    ContextBuildRequestFactory,
)
from app.domain.context_builder.context_package_assembler import (
    assemble_context_package,
)
from app.domain.prompt_builder.prompt_builder_factory import (
    PromptBuildRequestFactory,
)
from app.domain.prompt_builder.prompt_package_assembler import (
    assemble_prompt_package,
)
from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
)
from app.application.models.llm_capabilities import LLMCapability
from app.application.services.prompt_package_to_llm_request_mapper import (
    map_prompt_package_to_llm_request,
)
from app.infrastructure.llm.anthropic.anthropic_adapter import AnthropicAdapter
from app.infrastructure.llm.anthropic.anthropic_response_mapper import (
    map_content,
    map_finish_reason,
    map_usage,
)
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeInvocationOutcome,
    FakeLLMProviderAdapter,
)
from app.application.models.llm_invocation import (
    LLMInvocationPolicy,
    LLMProviderErrorCategory,
    LLMRetryPolicy,
    LLMTimeoutPolicy,
)
from app.application.services.llm_runtime import run_invocation
from app.domain.engineering_response.engineering_response_assembler import (
    assemble_engineering_response,
)
from app.domain.engineering_response.engineering_response_factory import (
    EngineeringResponseBuildRequestFactory,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    EngineeringSourceFinishReason,
)
from app.domain.engineering_session.engineering_session_builder import (
    append_engineering_response,
    build_initial_session,
    change_session_state,
)
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionStatus,
)
from app.infrastructure.graph_builder.sqlalchemy_graph_operation_batch_repository import (
    SqlAlchemyGraphOperationBatchRepository,
)
from app.infrastructure.graph_query.sqlalchemy_graph_query_repository import (
    SqlAlchemyGraphQueryRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_execution_repository import (
    SqlAlchemyGraphExecutionRepository,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store import (
    SqlAlchemyGraphStore,
)
from app.infrastructure.project_knowledge_graph.sqlalchemy_graph_unit_of_work import (
    SqlAlchemyGraphUnitOfWork,
)
from app.services import (
    graph_execution_service,
    graph_query_service,
    structured_retrieval_service,
)

NOW = datetime(2026, 1, 1, 12, 0, 0)

# Fixed, domain-realistic entity/relationship vocabulary for synthetic
# fixtures - not tied to any real project's data.
ENTITY_TYPES = (
    "CABLE",
    "TRANSFORMER",
    "CIRCUIT_BREAKER",
    "BUSBAR",
    "DISCONNECTOR",
)
RELATIONSHIP_TYPES = ("CONNECTED_TO", "FEEDS", "PROTECTED_BY")
# Only these entity types receive an attribute - keeps attribute
# filtering meaningfully selective rather than matching every node.
ATTRIBUTE_BEARING_TYPES = ("CABLE", "TRANSFORMER")
ATTRIBUTE_NAME = "rated_voltage"
ATTRIBUTE_VALUE = "132kV"
ORPHAN_FRACTION = 0.05


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    name: str
    node_count: int
    relationship_count: int


SMALL_DATASET = DatasetSpec(name="small", node_count=100, relationship_count=200)
MEDIUM_DATASET = DatasetSpec(
    name="medium", node_count=5_000, relationship_count=10_000
)


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    operation: str
    dataset: str
    unit_count: int
    seconds: float

    @property
    def seconds_per_unit(self) -> float:
        return self.seconds / self.unit_count if self.unit_count else self.seconds


def _timed(
    operation: str, dataset: str, unit_count: int, action
) -> BenchmarkMeasurement:
    start = time.perf_counter()
    action()
    elapsed = time.perf_counter() - start

    return BenchmarkMeasurement(
        operation=operation,
        dataset=dataset,
        unit_count=unit_count,
        seconds=elapsed,
    )


def _new_engine_and_session() -> tuple[Engine, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return engine, session_factory()


def _create_project(session: Session, name: str, code: str) -> int:
    project_repository = SqlAlchemyProjectRepository(session)
    project = project_repository.save(
        ProjectFactory.create(
            name=name,
            code=code,
            customer="Synthetic Benchmark Fixture",
            created_at=NOW,
        )
    )

    return project.id  # type: ignore[return-value]


def _generate_dataset(
    project_id: int, spec: DatasetSpec, seed: int
) -> tuple[list[GraphEntityId], list[tuple[GraphEntityId, str, GraphEntityId]]]:
    """
    Builds `spec.node_count` unique node ids across a fixed rotation of
    entity types, then `spec.relationship_count` relationships wired
    between a subset of them - `ORPHAN_FRACTION` of nodes are
    deliberately left unconnected so orphan detection has something
    real to find. Deterministic for a given seed (CLAUDE.md §16,
    Reproducibility): the same spec/seed always produces the same graph
    shape.
    """

    rng = random.Random(seed)

    node_ids = [
        GraphEntityId(
            project_id=project_id,
            entity_type=ENTITY_TYPES[index % len(ENTITY_TYPES)],
            canonical_id=f"N-{index:06d}",
        )
        for index in range(spec.node_count)
    ]

    orphan_count = max(1, int(spec.node_count * ORPHAN_FRACTION))
    connectable_ids = node_ids[: spec.node_count - orphan_count] or node_ids

    relationships: list[tuple[GraphEntityId, str, GraphEntityId]] = []
    attempts = 0
    while len(relationships) < spec.relationship_count and attempts < spec.relationship_count * 4:
        attempts += 1
        source = rng.choice(connectable_ids)
        target = rng.choice(connectable_ids)

        if source == target:
            continue

        relationship_type = RELATIONSHIP_TYPES[
            len(relationships) % len(RELATIONSHIP_TYPES)
        ]
        relationships.append((source, relationship_type, target))

    return node_ids, relationships


def _busiest_node(
    node_ids: list[GraphEntityId],
    relationships: list[tuple[GraphEntityId, str, GraphEntityId]],
) -> GraphEntityId:
    degree: Counter[GraphEntityId] = Counter()

    for source, _relationship_type, target in relationships:
        degree[source] += 1
        degree[target] += 1

    if not degree:
        return node_ids[0]

    return degree.most_common(1)[0][0]


def run_store_level_and_read_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures raw GraphStore write cost (node upsert, attribute merge,
    relationship upsert - each issued as individual calls, matching
    exactly how graph_execution_service._execute_operation drives the
    store one operation at a time) and every Graph Query read
    operation named in the milestone, against one populated project.
    """

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session, f"Benchmark {spec.name}", f"BENCH-STORE-{spec.name.upper()}"
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)
        graph_store = SqlAlchemyGraphStore(session)

        def _upsert_nodes() -> None:
            for entity_id in node_ids:
                graph_store.upsert_node(
                    graph_entity_id=entity_id, execution_id=1, now=NOW
                )
            session.flush()

        measurements.append(
            _timed("node_upsert", spec.name, len(node_ids), _upsert_nodes)
        )

        attribute_targets = [
            entity_id
            for entity_id in node_ids
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES
        ]

        def _merge_attributes() -> None:
            for entity_id in attribute_targets:
                graph_store.merge_node_property(
                    graph_entity_id=entity_id,
                    attribute=ATTRIBUTE_NAME,
                    value=ATTRIBUTE_VALUE,
                    execution_id=1,
                    now=NOW,
                )
            session.flush()

        measurements.append(
            _timed(
                "attribute_merge",
                spec.name,
                len(attribute_targets),
                _merge_attributes,
            )
        )

        def _upsert_relationships() -> None:
            for source, relationship_type, target in relationships:
                graph_store.upsert_relationship(
                    source_entity_id=source,
                    relationship_type=GraphRelationshipType(value=relationship_type),
                    target_entity_id=target,
                    execution_id=1,
                    now=NOW,
                )
            session.flush()

        measurements.append(
            _timed(
                "relationship_upsert",
                spec.name,
                len(relationships),
                _upsert_relationships,
            )
        )

        session.commit()

        query_repository = SqlAlchemyGraphQueryRepository(session)

        measurements.append(
            _timed(
                "list_nodes",
                spec.name,
                len(node_ids),
                lambda: query_repository.list_nodes(project_id),
            )
        )
        measurements.append(
            _timed(
                "list_relationships",
                spec.name,
                len(relationships),
                lambda: query_repository.list_relationships(project_id),
            )
        )
        measurements.append(
            _timed(
                "statistics",
                spec.name,
                len(node_ids) + len(relationships),
                lambda: graph_query_service.get_statistics(
                    query_repository, project_id=project_id, now=NOW
                ),
            )
        )
        measurements.append(
            _timed(
                "orphan_detection",
                spec.name,
                len(node_ids),
                lambda: graph_query_service.list_orphans(
                    query_repository, project_id=project_id, now=NOW
                ),
            )
        )
        measurements.append(
            _timed(
                "attribute_filtering",
                spec.name,
                len(node_ids),
                lambda: graph_query_service.list_entities(
                    query_repository,
                    project_id=project_id,
                    has_attribute=ATTRIBUTE_NAME,
                    now=NOW,
                ),
            )
        )

        hub = _busiest_node(node_ids, relationships)
        measurements.append(
            _timed(
                "one_hop_neighborhood",
                spec.name,
                1,
                lambda: graph_query_service.get_neighborhood(
                    query_repository,
                    project_id=project_id,
                    graph_entity_id=hub,
                    depth=1,
                    now=NOW,
                ),
            )
        )
    finally:
        session.close()
        engine.dispose()

    return measurements


def run_batch_execution_benchmark(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures the full, atomic GraphOperationBatch execution path
    (persist batch -> execute_batch -> one GraphUnitOfWork.commit()) on
    a fresh project, mirroring exactly how a real document ingestion
    would apply a large deterministic mutation plan in one transaction.
    """

    engine, session = _new_engine_and_session()

    try:
        project_id = _create_project(
            session, f"Benchmark batch {spec.name}", f"BENCH-BATCH-{spec.name.upper()}"
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)

        attribute_targets = [
            entity_id
            for entity_id in node_ids
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES
        ]

        # Operation order matters: every CREATE_NODE must precede any
        # UPDATE_NODE/CREATE_RELATIONSHIP that references it, or the
        # store raises GraphNodeNotFoundError mid-batch.
        operations: list[GraphNodeOperation | GraphRelationshipOperation] = [
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=entity_id,
                attribute=None,
                value=None,
                source_fact_id=1,
            )
            for entity_id in node_ids
        ]
        operations.extend(
            GraphNodeOperation(
                kind=GraphNodeOperationKind.UPDATE_NODE,
                entity_id=entity_id,
                attribute=ATTRIBUTE_NAME,
                value=ATTRIBUTE_VALUE,
                source_fact_id=1,
            )
            for entity_id in attribute_targets
        )
        operations.extend(
            GraphRelationshipOperation(
                kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
                subject_id=source,
                relationship_type=GraphRelationshipType(value=relationship_type),
                object_id=target,
                source_fact_id=1,
            )
            for source, relationship_type, target in relationships
        )

        batch_repository = SqlAlchemyGraphOperationBatchRepository(session)
        batch = batch_repository.save(
            GraphOperationBatch(
                id=None,
                project_id=project_id,
                source=GraphOperationBatchSource(
                    scope=GraphOperationBatchScope.PROJECT,
                    scope_id=project_id,
                ),
                operations=tuple(operations),
                created_at=NOW,
            )
        )

        execution_repository = SqlAlchemyGraphExecutionRepository(session)
        graph_store = SqlAlchemyGraphStore(session)
        project_repository = SqlAlchemyProjectRepository(session)
        unit_of_work = SqlAlchemyGraphUnitOfWork(session)

        result_holder: dict[str, object] = {}

        def _execute() -> None:
            result_holder["result"] = graph_execution_service.execute_batch(
                batch_repository,
                execution_repository,
                graph_store,
                project_repository,
                unit_of_work,
                batch_id=batch.id,  # type: ignore[arg-type]
                now=NOW,
            )

        measurement = _timed(
            "batch_execution", spec.name, len(operations), _execute
        )
    finally:
        session.close()
        engine.dispose()

    return [measurement]


def run_structured_retrieval_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures the six Structured Retrieval modes named in Milestone 13:
    exact entity lookup, entity-type retrieval, relationship-type
    retrieval, lexical retrieval, combined retrieval, and retrieval
    with 1-hop enrichment - each against the same populated project a
    fresh ``SqlAlchemyGraphQueryRepository`` reads through, exactly the
    path the real API uses (never ``GraphStore``).
    """

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session,
            f"Benchmark retrieval {spec.name}",
            f"BENCH-RETRIEVE-{spec.name.upper()}",
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)
        graph_store = SqlAlchemyGraphStore(session)

        for entity_id in node_ids:
            graph_store.upsert_node(
                graph_entity_id=entity_id, execution_id=1, now=NOW
            )
        for entity_id in node_ids:
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES:
                graph_store.merge_node_property(
                    graph_entity_id=entity_id,
                    attribute=ATTRIBUTE_NAME,
                    value=ATTRIBUTE_VALUE,
                    execution_id=1,
                    now=NOW,
                )
        for source, relationship_type, target in relationships:
            graph_store.upsert_relationship(
                source_entity_id=source,
                relationship_type=GraphRelationshipType(value=relationship_type),
                target_entity_id=target,
                execution_id=1,
                now=NOW,
            )
        session.commit()

        repository = SqlAlchemyGraphQueryRepository(session)
        hub = _busiest_node(node_ids, relationships)
        hub_reference = f"{hub.entity_type}:{hub.canonical_id}"

        entity_lookup_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.ENTITY_LOOKUP,
            limit=20,
            include_neighborhood=False,
            neighborhood_depth=0,
            canonical_entity_id=hub_reference,
        )
        measurements.append(
            _timed(
                "retrieval_entity_lookup",
                spec.name,
                1,
                lambda: structured_retrieval_service.retrieve(
                    repository, entity_lookup_request, now=NOW
                ),
            )
        )

        entity_type_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.ENTITY_TYPE_SEARCH,
            limit=20,
            include_neighborhood=False,
            neighborhood_depth=0,
            entity_type=ENTITY_TYPES[0],
        )
        measurements.append(
            _timed(
                "retrieval_entity_type",
                spec.name,
                len(node_ids) // len(ENTITY_TYPES),
                lambda: structured_retrieval_service.retrieve(
                    repository, entity_type_request, now=NOW
                ),
            )
        )

        relationship_type_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.RELATIONSHIP_SEARCH,
            limit=20,
            include_neighborhood=False,
            neighborhood_depth=0,
            relationship_type=RELATIONSHIP_TYPES[0],
        )
        measurements.append(
            _timed(
                "retrieval_relationship_type",
                spec.name,
                len(relationships) // len(RELATIONSHIP_TYPES),
                lambda: structured_retrieval_service.retrieve(
                    repository, relationship_type_request, now=NOW
                ),
            )
        )

        lexical_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.LEXICAL_SEARCH,
            limit=20,
            include_neighborhood=False,
            neighborhood_depth=0,
            lexical_match_mode=LexicalMatchMode.ANY,
            lexical_terms=(hub.canonical_id, ENTITY_TYPES[1]),
        )
        measurements.append(
            _timed(
                "retrieval_lexical",
                spec.name,
                len(node_ids) + len(relationships),
                lambda: structured_retrieval_service.retrieve(
                    repository, lexical_request, now=NOW
                ),
            )
        )

        combined_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.COMBINED,
            limit=20,
            include_neighborhood=False,
            neighborhood_depth=0,
            entity_type=ENTITY_TYPES[0],
            attribute_name=ATTRIBUTE_NAME,
        )
        measurements.append(
            _timed(
                "retrieval_combined",
                spec.name,
                len(node_ids) // len(ENTITY_TYPES),
                lambda: structured_retrieval_service.retrieve(
                    repository, combined_request, now=NOW
                ),
            )
        )

        neighborhood_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.ENTITY_LOOKUP,
            limit=20,
            include_neighborhood=True,
            neighborhood_depth=1,
            canonical_entity_id=hub_reference,
        )
        measurements.append(
            _timed(
                "retrieval_with_neighborhood_enrichment",
                spec.name,
                1,
                lambda: structured_retrieval_service.retrieve(
                    repository, neighborhood_request, now=NOW
                ),
            )
        )
    finally:
        session.close()
        engine.dispose()

    return measurements


def run_context_builder_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures Context Builder assembly (Milestone 14) over the
    ``COMBINED``-mode ``KnowledgeCandidateCollection`` Structured
    Retrieval itself produces for the same populated project -
    Selection, Aggregation, Coverage Analysis, and Budget Enforcement
    together, both within a generous budget (nothing discarded) and
    under a tight budget (forcing discards, warnings, and partial
    coverage) - proving assembly cost scales with candidate count, not
    with graph size, since Context Builder never touches Graph Query or
    the database itself.
    """

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session,
            f"Benchmark context builder {spec.name}",
            f"BENCH-CONTEXT-{spec.name.upper()}",
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)
        graph_store = SqlAlchemyGraphStore(session)

        for entity_id in node_ids:
            graph_store.upsert_node(
                graph_entity_id=entity_id, execution_id=1, now=NOW
            )
        for entity_id in node_ids:
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES:
                graph_store.merge_node_property(
                    graph_entity_id=entity_id,
                    attribute=ATTRIBUTE_NAME,
                    value=ATTRIBUTE_VALUE,
                    execution_id=1,
                    now=NOW,
                )
        for source, relationship_type, target in relationships:
            graph_store.upsert_relationship(
                source_entity_id=source,
                relationship_type=GraphRelationshipType(value=relationship_type),
                target_entity_id=target,
                execution_id=1,
                now=NOW,
            )
        session.commit()

        repository = SqlAlchemyGraphQueryRepository(session)
        combined_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.COMBINED,
            limit=200,
            include_neighborhood=False,
            neighborhood_depth=0,
            entity_type=ENTITY_TYPES[0],
            attribute_name=ATTRIBUTE_NAME,
        )
        retrieval_result = structured_retrieval_service.retrieve(
            repository, combined_request, now=NOW
        )
        candidates = retrieval_result.candidates

        within_budget_request = ContextBuildRequestFactory.create(
            project_id=project_id,
            candidates=candidates,
            max_candidates=len(candidates.candidates) or 1,
            max_entities=len(candidates.candidates) or 1,
            max_attributes=len(candidates.candidates) or 1,
        )
        measurements.append(
            _timed(
                "context_builder_within_budget",
                spec.name,
                len(candidates.candidates),
                lambda: assemble_context_package(
                    within_budget_request, now=NOW
                ),
            )
        )

        tight_budget_request = ContextBuildRequestFactory.create(
            project_id=project_id,
            candidates=candidates,
            max_candidates=max(1, len(candidates.candidates) // 4),
            max_entities=max(1, len(candidates.candidates) // 8),
        )
        measurements.append(
            _timed(
                "context_builder_tight_budget",
                spec.name,
                len(candidates.candidates),
                lambda: assemble_context_package(
                    tight_budget_request, now=NOW
                ),
            )
        )
    finally:
        session.close()
        engine.dispose()

    return measurements


def run_prompt_builder_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures Prompt Builder composition (Milestone 15) over the
    ``ContextPackage`` Context Builder itself produces for the same
    populated project's ``COMBINED``-mode retrieval - Composition,
    Statistics, Metadata/Versioning, and Validation together. Prompt
    Builder never touches Graph Query, Structured Retrieval, or the
    database itself, so assembly cost scales only with the size of the
    input ``ContextPackage``, never with graph size.
    """

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session,
            f"Benchmark prompt builder {spec.name}",
            f"BENCH-PROMPT-{spec.name.upper()}",
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)
        graph_store = SqlAlchemyGraphStore(session)

        for entity_id in node_ids:
            graph_store.upsert_node(
                graph_entity_id=entity_id, execution_id=1, now=NOW
            )
        for entity_id in node_ids:
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES:
                graph_store.merge_node_property(
                    graph_entity_id=entity_id,
                    attribute=ATTRIBUTE_NAME,
                    value=ATTRIBUTE_VALUE,
                    execution_id=1,
                    now=NOW,
                )
        for source, relationship_type, target in relationships:
            graph_store.upsert_relationship(
                source_entity_id=source,
                relationship_type=GraphRelationshipType(value=relationship_type),
                target_entity_id=target,
                execution_id=1,
                now=NOW,
            )
        session.commit()

        repository = SqlAlchemyGraphQueryRepository(session)
        combined_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.COMBINED,
            limit=200,
            include_neighborhood=False,
            neighborhood_depth=0,
            entity_type=ENTITY_TYPES[0],
            attribute_name=ATTRIBUTE_NAME,
        )
        retrieval_result = structured_retrieval_service.retrieve(
            repository, combined_request, now=NOW
        )

        context_request = ContextBuildRequestFactory.create(
            project_id=project_id,
            candidates=retrieval_result.candidates,
            max_candidates=len(retrieval_result.candidates.candidates) or 1,
            max_entities=len(retrieval_result.candidates.candidates) or 1,
            max_attributes=len(retrieval_result.candidates.candidates) or 1,
        )
        context_package = assemble_context_package(context_request, now=NOW)

        prompt_request = PromptBuildRequestFactory.create(
            project_id=project_id, context_package=context_package
        )
        measurements.append(
            _timed(
                "prompt_builder_composition",
                spec.name,
                len(context_package.selected_candidates),
                lambda: assemble_prompt_package(prompt_request, now=NOW),
            )
        )
    finally:
        session.close()
        engine.dispose()

    return measurements


def run_llm_provider_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures the LLM Provider Abstraction Layer (Milestone 16): mapping
    a ``PromptPackage`` into a neutral ``LLMRequest``, then translating
    that request into a local ``AnthropicPreparedRequest`` - over the
    same ``PromptPackage`` Prompt Builder itself produces for the
    populated project's ``COMBINED``-mode retrieval. No network I/O of
    any kind; cost scales only with the size of the input
    ``PromptPackage``, never with graph size or an external API call.
    """

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session,
            f"Benchmark llm provider {spec.name}",
            f"BENCH-LLM-{spec.name.upper()}",
        )
        node_ids, relationships = _generate_dataset(project_id, spec, seed)
        graph_store = SqlAlchemyGraphStore(session)

        for entity_id in node_ids:
            graph_store.upsert_node(
                graph_entity_id=entity_id, execution_id=1, now=NOW
            )
        for entity_id in node_ids:
            if entity_id.entity_type in ATTRIBUTE_BEARING_TYPES:
                graph_store.merge_node_property(
                    graph_entity_id=entity_id,
                    attribute=ATTRIBUTE_NAME,
                    value=ATTRIBUTE_VALUE,
                    execution_id=1,
                    now=NOW,
                )
        for source, relationship_type, target in relationships:
            graph_store.upsert_relationship(
                source_entity_id=source,
                relationship_type=GraphRelationshipType(value=relationship_type),
                target_entity_id=target,
                execution_id=1,
                now=NOW,
            )
        session.commit()

        repository = SqlAlchemyGraphQueryRepository(session)
        combined_request = StructuredRetrievalRequestFactory.create(
            project_id=project_id,
            mode=RetrievalMode.COMBINED,
            limit=200,
            include_neighborhood=False,
            neighborhood_depth=0,
            entity_type=ENTITY_TYPES[0],
            attribute_name=ATTRIBUTE_NAME,
        )
        retrieval_result = structured_retrieval_service.retrieve(
            repository, combined_request, now=NOW
        )

        context_request = ContextBuildRequestFactory.create(
            project_id=project_id,
            candidates=retrieval_result.candidates,
            max_candidates=len(retrieval_result.candidates.candidates) or 1,
            max_entities=len(retrieval_result.candidates.candidates) or 1,
            max_attributes=len(retrieval_result.candidates.candidates) or 1,
        )
        context_package = assemble_context_package(context_request, now=NOW)

        prompt_request = PromptBuildRequestFactory.create(
            project_id=project_id, context_package=context_package
        )
        prompt_result = assemble_prompt_package(prompt_request, now=NOW)

        provider_selection = LLMProviderSelection(provider_id="anthropic")
        model_selection = LLMModelSelection(model_identifier="benchmark-model")
        generation_parameters = LLMGenerationParameters(max_output_tokens=1024)
        capability_requirements = LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        )

        llm_request_holder: dict[str, object] = {}

        def _map() -> None:
            llm_request_holder["request"] = map_prompt_package_to_llm_request(
                prompt_result.package,
                provider_selection=provider_selection,
                model_selection=model_selection,
                generation_parameters=generation_parameters,
                capability_requirements=capability_requirements,
                provider_abstraction_version="1.0",
                request_preparation_policy_version="1.0",
                request_correlation_id="benchmark-correlation-id",
                now=NOW,
            )

        measurements.append(
            _timed(
                "llm_request_mapping",
                spec.name,
                len(prompt_result.package.sections),
                _map,
            )
        )

        adapter = AnthropicAdapter(
            model_identifier="benchmark-model", default_max_output_tokens=1024
        )
        measurements.append(
            _timed(
                "llm_anthropic_request_preparation",
                spec.name,
                len(prompt_result.package.sections),
                lambda: adapter.prepare_request(llm_request_holder["request"]),
            )
        )
    finally:
        session.close()
        engine.dispose()

    return measurements


def _synthetic_llm_request():
    """A minimal, self-contained ``LLMRequest`` fixture for benchmarking
    the invocation runtime's own orchestration overhead - deliberately
    not built from a real ``PromptPackage`` (this benchmark measures
    the runtime loop, not composition), and never depends on any
    ``tests/**`` module (a production script must stand on its own)."""

    from app.application.models.llm_request import (
        LLMContentBlock,
        LLMContentType,
        LLMMessage,
        LLMMessageRole,
        LLMRequestMetadata,
        LLMRequestVersion,
    )

    metadata = LLMRequestMetadata(
        project_id=0,
        context_builder_version="1.0",
        prompt_builder_version="1.0",
        composition_policy_version="1.0",
        prompt_package_version="1.0",
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        provider_id="fake",
        model_identifier="benchmark-model",
        request_correlation_id="benchmark-corr",
        excluded_section_types=(),
        prepared_at=NOW,
    )
    return LLMRequest(
        project_id=0,
        provider_selection=LLMProviderSelection(provider_id="fake"),
        model_selection=LLMModelSelection(model_identifier="benchmark-model"),
        messages=(
            LLMMessage(
                role=LLMMessageRole.INSTRUCTION,
                section_type="system_context",
                content_blocks=(
                    LLMContentBlock(content_type=LLMContentType.TEXT, text="Be precise."),
                ),
            ),
            LLMMessage(
                role=LLMMessageRole.CONTEXT,
                section_type="engineering_context",
                content_blocks=(
                    LLMContentBlock(content_type=LLMContentType.TEXT, text="Project id: 0"),
                ),
            ),
        ),
        references=(),
        generation_parameters=LLMGenerationParameters(),
        capability_requirements=LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        ),
        metadata=metadata,
        version=LLMRequestVersion(
            provider_abstraction_version="1.0",
            request_preparation_policy_version="1.0",
        ),
    )


def _synthetic_anthropic_message(text: str = "Synthetic benchmark response."):
    """A local, in-memory ``anthropic.types.Message`` fixture - never a
    network call, never a mock of the SDK's own types (the same real
    SDK object used by ``tests/infrastructure/test_anthropic_response_mapper.py``)."""

    from anthropic.types import Message, TextBlock, Usage

    return Message(
        id="msg_benchmark",
        content=[TextBlock(type="text", text=text)],
        model="benchmark-model",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=50, output_tokens=20),
    )


def run_llm_invocation_runtime_benchmarks() -> list[BenchmarkMeasurement]:
    """
    Measures the LLM Invocation Runtime's own orchestration overhead
    (Milestone 17) - independent of graph size, since the runtime never
    queries the database: a successful fake-provider invocation
    (single attempt), one transient failure followed by a successful
    retry, and Anthropic response normalization from a local
    ``anthropic.types.Message`` fixture. Never benchmarks the live
    provider API and never sleeps a real wall-clock delay (an
    injected, no-op sleeper stands in for retry backoff).
    """

    measurements: list[BenchmarkMeasurement] = []

    async def _no_op_sleeper(_seconds: float) -> None:
        return None

    policy = LLMInvocationPolicy(
        retry_policy=LLMRetryPolicy(
            version="1.0",
            max_attempts=3,
            base_delay_seconds=0.01,
            max_delay_seconds=0.05,
            jitter_enabled=False,
        ),
        timeout_policy=LLMTimeoutPolicy(
            connect_timeout_seconds=5.0,
            read_timeout_seconds=30.0,
            total_deadline_seconds=60.0,
        ),
        runtime_version="1.0",
    )

    success_adapter = FakeLLMProviderAdapter(
        outcomes=(FakeInvocationOutcome(succeeds=True),)
    )
    success_request = _synthetic_llm_request()
    success_prepared = success_adapter.prepare_request(success_request)

    def _run_success() -> None:
        asyncio.run(
            run_invocation(
                adapter=success_adapter,
                request=success_request,
                prepared_request=success_prepared,
                policy=policy,
                request_correlation_id="benchmark-success",
                clock=lambda: NOW,
                sleeper=_no_op_sleeper,
                random_source=random.Random(1),
            )
        )

    measurements.append(
        _timed("llm_invocation_fake_success", "n/a", 1, _run_success)
    )

    retry_adapter = FakeLLMProviderAdapter(
        outcomes=(
            FakeInvocationOutcome(
                succeeds=False,
                error_category=LLMProviderErrorCategory.TRANSIENT_PROVIDER_FAILURE,
            ),
            FakeInvocationOutcome(succeeds=True),
        )
    )
    retry_prepared = retry_adapter.prepare_request(success_request)

    def _run_retry() -> None:
        asyncio.run(
            run_invocation(
                adapter=retry_adapter,
                request=success_request,
                prepared_request=retry_prepared,
                policy=policy,
                request_correlation_id="benchmark-retry",
                clock=lambda: NOW,
                sleeper=_no_op_sleeper,
                random_source=random.Random(1),
            )
        )

    measurements.append(
        _timed("llm_invocation_transient_then_success", "n/a", 2, _run_retry)
    )

    message = _synthetic_anthropic_message()

    def _run_response_normalization() -> None:
        map_content(message)
        map_finish_reason(message.stop_reason)
        map_usage(message)

    measurements.append(
        _timed(
            "anthropic_response_normalization",
            "n/a",
            len(message.content),
            _run_response_normalization,
        )
    )

    return measurements


def run_engineering_response_benchmarks() -> list[BenchmarkMeasurement]:
    """
    Measures Engineering Response Builder overhead (Milestone 18) -
    dataset-independent, since building never queries the database or
    calls a provider: it consumes an already-assembled
    ``ContextPackage``/``PromptPackage`` (built here from an empty
    ``KnowledgeCandidateCollection``, the cheapest legitimate input) and
    a synthetic ``EngineeringResponseSourceEnvelope`` fixture, never a
    real ``LLMResponseEnvelope`` or a real provider call.
    """

    measurements: list[BenchmarkMeasurement] = []

    empty_candidates = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_request = ContextBuildRequestFactory.create(
        project_id=1, candidates=empty_candidates
    )
    context_package = assemble_context_package(context_request, now=NOW)

    prompt_request = PromptBuildRequestFactory.create(
        project_id=1, context_package=context_package
    )
    prompt_result = assemble_prompt_package(prompt_request, now=NOW)

    source = EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="benchmark-model",
        returned_model_identifier="benchmark-model",
        content=(
            EngineeringResponseSourceContent(
                sequence_index=0,
                is_supported_text=True,
                text="Synthetic benchmark answer.",
                provider_block_type=None,
            ),
        ),
        finish_reason=EngineeringSourceFinishReason.COMPLETED,
        request_correlation_id="benchmark-engineering-response",
        attempt_count=1,
        warnings=(),
        input_tokens=50,
        output_tokens=20,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )

    request = EngineeringResponseBuildRequestFactory.create(
        project_id=1,
        context_package=context_package,
        prompt_package=prompt_result.package,
        source=source,
    )

    measurements.append(
        _timed(
            "engineering_response_build",
            "n/a",
            1,
            lambda: assemble_engineering_response(request, now=NOW),
        )
    )

    return measurements


def run_engineering_session_benchmarks() -> list[BenchmarkMeasurement]:
    """
    Measures Engineering Session Builder overhead (Milestone 19) -
    dataset-independent and provider-independent: creating a session,
    transitioning it to ACTIVE, and appending one already-built
    ``EngineeringResponse`` (reusing the same synthetic
    ContextPackage/PromptPackage fixture
    ``run_engineering_response_benchmarks`` builds) - never a real
    provider call, never a database query, never persistence of any
    kind.
    """

    measurements: list[BenchmarkMeasurement] = []

    empty_candidates = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_request = ContextBuildRequestFactory.create(
        project_id=1, candidates=empty_candidates
    )
    context_package = assemble_context_package(context_request, now=NOW)

    prompt_request = PromptBuildRequestFactory.create(
        project_id=1, context_package=context_package
    )
    prompt_result = assemble_prompt_package(prompt_request, now=NOW)

    source = EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="benchmark-model",
        returned_model_identifier="benchmark-model",
        content=(
            EngineeringResponseSourceContent(
                sequence_index=0,
                is_supported_text=True,
                text="Synthetic benchmark answer.",
                provider_block_type=None,
            ),
        ),
        finish_reason=EngineeringSourceFinishReason.COMPLETED,
        request_correlation_id="benchmark-engineering-session",
        attempt_count=1,
        warnings=(),
        input_tokens=50,
        output_tokens=20,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )
    engineering_response_request = EngineeringResponseBuildRequestFactory.create(
        project_id=1,
        context_package=context_package,
        prompt_package=prompt_result.package,
        source=source,
    )
    engineering_response = assemble_engineering_response(
        engineering_response_request, now=NOW
    ).response

    def _run_session_lifecycle() -> None:
        create_result = build_initial_session(
            project_id=1, session_id="benchmark-session", now=NOW
        )
        active_result = change_session_state(
            create_result.session, EngineeringSessionStatus.ACTIVE, now=NOW
        )
        append_engineering_response(
            active_result.session, engineering_response, now=NOW
        )

    measurements.append(
        _timed(
            "engineering_session_lifecycle",
            "n/a",
            1,
            _run_session_lifecycle,
        )
    )

    return measurements


def run_all(specs: tuple[DatasetSpec, ...]) -> list[BenchmarkMeasurement]:
    measurements: list[BenchmarkMeasurement] = []

    for spec in specs:
        measurements.extend(run_store_level_and_read_benchmarks(spec))
        measurements.extend(run_batch_execution_benchmark(spec))
        measurements.extend(run_structured_retrieval_benchmarks(spec))
        measurements.extend(run_context_builder_benchmarks(spec))
        measurements.extend(run_prompt_builder_benchmarks(spec))
        measurements.extend(run_llm_provider_benchmarks(spec))

    measurements.extend(run_llm_invocation_runtime_benchmarks())
    measurements.extend(run_engineering_response_benchmarks())
    measurements.extend(run_engineering_session_benchmarks())

    return measurements


def _print_report(measurements: list[BenchmarkMeasurement]) -> None:
    header = f"{'dataset':<8} {'operation':<22} {'units':>8} {'seconds':>10} {'sec/unit':>12}"
    print(header)
    print("-" * len(header))

    for measurement in measurements:
        print(
            f"{measurement.dataset:<8} {measurement.operation:<22} "
            f"{measurement.unit_count:>8} {measurement.seconds:>10.4f} "
            f"{measurement.seconds_per_unit:>12.6f}"
        )


def main() -> None:
    measurements = run_all((SMALL_DATASET, MEDIUM_DATASET))
    _print_report(measurements)


if __name__ == "__main__":
    main()
