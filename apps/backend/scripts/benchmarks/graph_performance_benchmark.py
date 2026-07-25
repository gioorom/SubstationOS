"""
Deterministic performance baseline for the Project Knowledge Graph
execution path, the Graph Query read model (Milestone 12, Workstream
6), and Structured Retrieval (Milestone 13).

This is a *measurement* script, not a correctness test and not a
performance-optimization milestone. It generates synthetic, non-
confidential fixtures at two fixed sizes and times: node upsert,
relationship upsert, a medium GraphOperationBatch execution, list
nodes, list relationships, statistics, orphan detection, attribute
filtering, a 1-hop neighborhood query (Milestone 12), and exact entity
lookup, entity-type, relationship-type, lexical, combined, and
neighborhood-enriched Structured Retrieval (Milestone 13).

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
    LexicalMatchMode,
    RetrievalMode,
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


def run_all(specs: tuple[DatasetSpec, ...]) -> list[BenchmarkMeasurement]:
    measurements: list[BenchmarkMeasurement] = []

    for spec in specs:
        measurements.extend(run_store_level_and_read_benchmarks(spec))
        measurements.extend(run_batch_execution_benchmark(spec))
        measurements.extend(run_structured_retrieval_benchmarks(spec))

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
