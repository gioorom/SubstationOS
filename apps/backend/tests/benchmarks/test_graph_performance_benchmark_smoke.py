"""
Smoke coverage for scripts/benchmarks/graph_performance_benchmark.py
(Milestone 12, Workstream 6; extended for Structured Retrieval in
Milestone 13, Context Builder in Milestone 14, Prompt Builder in
Milestone 15, the LLM Provider Abstraction Layer in Milestone 16, the
LLM Invocation Runtime in Milestone 17, Engineering Response in
Milestone 18, Engineering Session in Milestone 19, Conversation in
Milestone 20, and Working Memory in Milestone 21). Proves the
benchmark code itself runs against the small
synthetic dataset without error and produces sane row counts - it
deliberately asserts nothing about wall-clock time, so it cannot become
flaky under CI load (per the milestone's "no flaky wall-clock
assertions in the normal suite" rule). The medium dataset (~5,000
nodes/~10,000 relationships) is exercised only by running the script
directly, never by the normal pytest suite. Milestones 17 and 18's own
benchmarks never touch the live provider API and never sleep a real
wall-clock delay - an injected, no-op sleeper stands in for retry
backoff.
"""

from __future__ import annotations

from scripts.benchmarks.graph_performance_benchmark import (
    SMALL_DATASET,
    run_context_builder_benchmarks,
    run_conversation_benchmarks,
    run_engineering_response_benchmarks,
    run_engineering_session_benchmarks,
    run_governed_retrieval_benchmarks,
    run_llm_invocation_runtime_benchmarks,
    run_llm_provider_benchmarks,
    run_prompt_builder_benchmarks,
    run_working_memory_benchmarks,
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

_EXPECTED_CONTEXT_BUILDER_OPERATIONS = {
    "context_builder_within_budget",
    "context_builder_tight_budget",
}

_EXPECTED_PROMPT_BUILDER_OPERATIONS = {
    "prompt_builder_composition",
}

_EXPECTED_LLM_PROVIDER_OPERATIONS = {
    "llm_request_mapping",
    "llm_anthropic_request_preparation",
}

_EXPECTED_LLM_INVOCATION_RUNTIME_OPERATIONS = {
    "llm_invocation_fake_success",
    "llm_invocation_transient_then_success",
    "anthropic_response_normalization",
}

_EXPECTED_ENGINEERING_RESPONSE_OPERATIONS = {
    "engineering_response_build",
}

_EXPECTED_ENGINEERING_SESSION_OPERATIONS = {
    "engineering_session_lifecycle",
}

_EXPECTED_CONVERSATION_OPERATIONS = {
    "conversation_turn_lifecycle",
}

_EXPECTED_WORKING_MEMORY_OPERATIONS = {
    "working_memory_build",
}


def test_context_builder_benchmarks_run_on_the_small_dataset() -> None:
    measurements = run_context_builder_benchmarks(SMALL_DATASET)

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_CONTEXT_BUILDER_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)

    by_operation = {
        measurement.operation: measurement for measurement in measurements
    }
    # The tight-budget run discards at least as many candidates as the
    # within-budget run (same input collection, a stricter cap) - both
    # measure the same unit_count (the full retrieved candidate count),
    # never a post-discard count, so assembly cost is comparable across
    # budgets.
    assert (
        by_operation["context_builder_within_budget"].unit_count
        == by_operation["context_builder_tight_budget"].unit_count
    )


def test_prompt_builder_benchmarks_run_on_the_small_dataset() -> None:
    measurements = run_prompt_builder_benchmarks(SMALL_DATASET)

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_PROMPT_BUILDER_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_llm_provider_benchmarks_run_on_the_small_dataset() -> None:
    measurements = run_llm_provider_benchmarks(SMALL_DATASET)

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_LLM_PROVIDER_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_llm_invocation_runtime_benchmarks_run() -> None:
    measurements = run_llm_invocation_runtime_benchmarks()

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_LLM_INVOCATION_RUNTIME_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)

    by_operation = {
        measurement.operation: measurement for measurement in measurements
    }
    assert by_operation["llm_invocation_transient_then_success"].unit_count == 2
    assert by_operation["llm_invocation_fake_success"].unit_count == 1


def test_engineering_response_benchmarks_run() -> None:
    measurements = run_engineering_response_benchmarks()

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_ENGINEERING_RESPONSE_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_engineering_session_benchmarks_run() -> None:
    measurements = run_engineering_session_benchmarks()

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_ENGINEERING_SESSION_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_conversation_benchmarks_run() -> None:
    measurements = run_conversation_benchmarks()

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_CONVERSATION_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


def test_working_memory_benchmarks_run() -> None:
    measurements = run_working_memory_benchmarks()

    operations = {measurement.operation for measurement in measurements}
    assert operations == _EXPECTED_WORKING_MEMORY_OPERATIONS
    assert all(measurement.seconds >= 0 for measurement in measurements)


_EXPECTED_GOVERNED_RETRIEVAL_OPERATIONS = {
    "governed_designation_lookup",
    "governed_quantity_traversal",
    "governed_relationship_lookup",
    "governed_document_knowledge",
    "governed_provenance_by_identity",
}


def test_the_governed_retrieval_benchmark_runs_and_measures_every_operation() -> (
    None
):
    """
    EPIC 31.2's five representative governed operations, measured against
    the same synthetic dataset size the legacy retrieval benchmark uses -
    so the two are comparable rather than merely both present.

    Asserts nothing about wall-clock time, per the suite's standing rule
    against flaky timing assertions under CI load.
    """

    measurements = run_governed_retrieval_benchmarks(SMALL_DATASET)

    assert {
        measurement.operation for measurement in measurements
    } == _EXPECTED_GOVERNED_RETRIEVAL_OPERATIONS
    assert all(
        measurement.dataset == SMALL_DATASET.name
        for measurement in measurements
    )
    assert all(measurement.unit_count > 0 for measurement in measurements)
