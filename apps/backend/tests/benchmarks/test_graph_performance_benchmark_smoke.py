"""
Smoke coverage for scripts/benchmarks/graph_performance_benchmark.py
(Milestone 12, Workstream 6; extended for Structured Retrieval in
Milestone 13). Proves the benchmark code itself runs against the small
synthetic dataset without error and produces sane row counts - it
deliberately asserts nothing about wall-clock time, so it cannot become
flaky under CI load (per the milestone's "no flaky wall-clock
assertions in the normal suite" rule). The medium dataset (~5,000
nodes/~10,000 relationships) is exercised only by running the script
directly, never by the normal pytest suite.
"""

from __future__ import annotations

from scripts.benchmarks.graph_performance_benchmark import (
    SMALL_DATASET,
    run_batch_execution_benchmark,
    run_store_level_and_read_benchmarks,
    run_structured_retrieval_benchmarks,
)

_EXPECTED_STORE_AND_READ_OPERATIONS = {
    "node_upsert",
    "attribute_merge",
    "relationship_upsert",
    "list_nodes",
    "list_relationships",
    "statistics",
    "orphan_detection",
    "attribute_filtering",
    "one_hop_neighborhood",
}

_EXPECTED_STRUCTURED_RETRIEVAL_OPERATIONS = {
    "retrieval_entity_lookup",
    "retrieval_entity_type",
    "retrieval_relationship_type",
    "retrieval_lexical",
    "retrieval_combined",
    "retrieval_with_neighborhood_enrichment",
}


def test_store_level_and_read_benchmarks_run_on_the_small_dataset() -> None:
    measurements = run_store_level_and_read_benchmarks(SMALL_DATASET)

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_STORE_AND_READ_OPERATIONS

    by_operation = {
        measurement.operation: measurement for measurement in measurements
    }
    assert by_operation["node_upsert"].unit_count == SMALL_DATASET.node_count
    assert (
        by_operation["relationship_upsert"].unit_count
        == SMALL_DATASET.relationship_count
    )
    assert by_operation["list_nodes"].unit_count == SMALL_DATASET.node_count
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_batch_execution_benchmark_runs_on_the_small_dataset() -> None:
    measurements = run_batch_execution_benchmark(SMALL_DATASET)

    assert len(measurements) == 1
    measurement = measurements[0]

    assert measurement.operation == "batch_execution"
    # Every node CREATE_NODE, plus at least every relationship
    # CREATE_RELATIONSHIP, must be present in the executed batch.
    assert measurement.unit_count > (
        SMALL_DATASET.node_count + SMALL_DATASET.relationship_count
    )
    assert measurement.seconds >= 0


def test_structured_retrieval_benchmarks_run_on_the_small_dataset() -> None:
    measurements = run_structured_retrieval_benchmarks(SMALL_DATASET)

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_STRUCTURED_RETRIEVAL_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)
