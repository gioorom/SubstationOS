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
    project,
    proposed_claims,
    review_workflow,
)
from app.domain.project.project_factory import ProjectFactory
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
from app.domain.conversation.conversation_builder import (
    append_message,
    attach_engineering_response,
    complete_turn,
    create_conversation,
    start_turn,
)
from app.domain.conversation.conversation_models import ConversationMessageRole
from app.domain.working_memory.working_memory_builder import build_working_memory
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
NOW = datetime(2026, 1, 1, 12, 0, 0)

# Fixed, domain-realistic entity/relationship vocabulary for synthetic
# fixtures - not tied to any real project's data.
# Only these entity types receive an attribute - keeps attribute
# filtering meaningfully selective rather than matching every node.

#: The governed retrieval result limit used for the list-shaped
#: benchmarks, so the measurement covers assembly of a full page rather
#: than of the default twenty.
MAX_BENCHMARK_LIMIT = 200


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


def run_governed_retrieval_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures the five governed retrieval operations named in EPIC 31.2 -
    designation lookup, quantity traversal, relationship lookup,
    document-scoped knowledge and provenance-by-identity - against a
    synthetic **governed** graph of the same size as the Canonical Facts
    dataset the legacy benchmarks use, so the two are comparable.

    The graph is written through the governed repository (the one
    promotion uses) and read through ``SqlAlchemyGovernedKnowledgeReader``
    - exactly the path the real API takes.

    ``designation_lookup`` is the one to watch: it filters by kind,
    state and project in SQL and folds designations in Python, which is
    a deliberate determinism-over-speed trade recorded in
    ``performance_baseline.md``. The number here is what makes the day
    that trade stops being affordable visible rather than theoretical.
    """

    from app.domain.governed_knowledge_graph.graph_lifecycle import (
        GraphObjectState,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
    )
    from app.domain.governed_retrieval.governed_retrieval_factory import (
        GovernedRetrievalQueryFactory,
    )
    from app.infrastructure.governed_knowledge_graph.sqlalchemy_governed_graph_repository import (  # noqa: E501
        SqlAlchemyGovernedGraphRepository,
    )
    from app.infrastructure.governed_retrieval.sqlalchemy_governed_knowledge_reader import (  # noqa: E501
        SqlAlchemyGovernedKnowledgeReader,
    )
    from app.services import governed_retrieval_service
    from tests._governed_graph_builder import governed_asset_with_quantity

    engine, session = _new_engine_and_session()
    measurements: list[BenchmarkMeasurement] = []

    try:
        project_id = _create_project(
            session,
            f"Benchmark governed retrieval {spec.name}",
            f"BENCH-GOVERNED-{spec.name.upper()}",
        )

        repository = SqlAlchemyGovernedGraphRepository(session)
        asset_count = spec.node_count // 2
        designations = [f"TR{index}" for index in range(asset_count)]

        for index, designation in enumerate(designations, start=1):
            asset, quantity, edge = governed_asset_with_quantity(
                designation=designation,
                document_id=index,
                project_id=1,
                created_at=NOW,
            )
            repository.upsert_node(asset)
            repository.upsert_node(quantity)
            repository.upsert_edge(edge)

        reader = SqlAlchemyGovernedKnowledgeReader(session)
        target = designations[len(designations) // 2]
        target_node = reader.nodes(
            states=(GraphObjectState.ACTIVE,),
        )[0]

        def _measure(operation: str, units: int, query) -> None:
            measurements.append(
                _timed(
                    operation,
                    spec.name,
                    units,
                    lambda: governed_retrieval_service.retrieve(
                        reader, query, now=NOW
                    ),
                )
            )

        _measure(
            "governed_designation_lookup",
            asset_count,
            GovernedRetrievalQueryFactory.asset_by_designation(
                designation=target, project_id=project_id
            ),
        )
        _measure(
            "governed_quantity_traversal",
            asset_count,
            GovernedRetrievalQueryFactory.quantity_for_asset(
                designation=target, project_id=project_id
            ),
        )
        _measure(
            "governed_relationship_lookup",
            asset_count,
            GovernedRetrievalQueryFactory.relationships(
                edge_kind=GraphEdgeKind.HAS_RATED_POWER,
                project_id=1,
                limit=MAX_BENCHMARK_LIMIT,
            ),
        )
        _measure(
            "governed_document_knowledge",
            asset_count,
            GovernedRetrievalQueryFactory.document_knowledge(
                document_id=1, project_id=project_id
            ),
        )
        _measure(
            "governed_provenance_by_identity",
            1,
            GovernedRetrievalQueryFactory.governed_identity(
                node_id=target_node.node_id.value
            ),
        )
    finally:
        session.close()
        engine.dispose()

    return measurements



#: Governed results the Context Assembly benchmarks assemble from.
#:
#: Generated in memory rather than retrieved, and that is the point:
#: Context Assembly performs **no I/O**, so its cost is a function of how
#: many governed results it was handed and of nothing else. Driving it
#: from a database read would measure the read.
def _governed_results(count: int) -> tuple:
    from app.domain.governed_knowledge_graph.graph_lifecycle import (
        GraphObjectState,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphNodeKind,
    )
    from app.domain.governed_retrieval.governed_match_policy import (
        precedence_of,
    )
    from app.domain.governed_retrieval.governed_result_identity import (
        node_result_id,
    )
    from app.domain.governed_retrieval.governed_retrieval_models import (
        AssetDesignationQuery,
        GovernedGraphVersion,
        GovernedMatchExplanation,
        GovernedNodeReference,
        GovernedProvenanceView,
        GovernedRetrievalDiagnostics,
        GovernedRetrievalItem,
        GovernedRetrievalResult,
    )
    from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
        GovernedMatchOutcome,
        GovernedMatchStrategy,
        GovernedResultKind,
        RetrievalScope,
    )

    strategy = GovernedMatchStrategy.EXACT_DESIGNATION
    results = []

    for index in range(count):
        designation = f"TR{index}"
        node_id = f"node-{index}"

        item = GovernedRetrievalItem(
            result_id=node_result_id(GovernedResultKind.ASSET, node_id),
            kind=GovernedResultKind.ASSET,
            node=GovernedNodeReference(
                node_id=node_id,
                kind=GraphNodeKind.ENGINEERING_ASSET,
                label=designation,
                normalized_value=designation.lower(),
                unit=None,
            ),
            relationship=None,
            state=GraphObjectState.ACTIVE,
            retirement_reason=None,
            match=GovernedMatchExplanation(
                strategy=strategy,
                matched_field="label",
                matched_value=designation,
                normalized_query=designation.lower(),
            ),
            provenance=GovernedProvenanceView(
                statement_key=f"statement-{index}",
                document_id=1,
                content_checksum="checksum",
                review_id=1,
                reviewer_user_id=1,
                reviewer_display_name="Benchmark Engineer",
                reviewed_at=NOW,
                semantic_rule_id="rule",
                semantic_rule_version="1.0",
                semantic_contract_version="1.0",
                resolution_policy_version="1.0",
                fact_policy_version="1.0",
                semantic_policy_version="1.0",
                support_fingerprint="fingerprint",
                project_id=1,
            ),
            sort_key=(
                precedence_of(strategy),
                designation.lower(),
                "",
                node_id,
            ),
        )

        query = AssetDesignationQuery(
            designation=designation,
            scope=RetrievalScope.CURRENT_ONLY,
            limit=200,
            project_id=1,
        )

        results.append(
            GovernedRetrievalResult(
                query=query,
                outcome=GovernedMatchOutcome.UNIQUE_MATCH,
                items=(item,),
                total_before_limit=1,
                applied_limit=200,
                diagnostics=GovernedRetrievalDiagnostics(
                    query_type=query.query_type,
                    scope=query.scope,
                    normalized_query=designation.lower(),
                    strategies_attempted=(strategy,),
                    candidates_examined=1,
                    matched_count=1,
                    returned_count=1,
                    ambiguous=False,
                    no_match=False,
                    normalization_version="1.0",
                    matching_policy_version="1.0",
                    graph_version=GovernedGraphVersion(
                        generation_number=1,
                        generation_created_at=NOW,
                        promotion_contract_version="1.0",
                    ),
                    duration_seconds=None,
                ),
                retrieved_at=NOW,
            )
        )

    return tuple(results)


def _benchmark_context_package(count: int):
    """One governed ``ContextPackage`` of ``count`` approved assets."""

    request = ContextBuildRequestFactory.create(
        project_id=1,
        results=_governed_results(count),
        max_items=max(count, 1),
        max_assets=max(count, 1),
    )

    return assemble_context_package(request, now=NOW)


def run_context_builder_benchmarks(
    spec: DatasetSpec, seed: int = 42
) -> list[BenchmarkMeasurement]:
    """
    Measures Governed Context Assembly (EPIC 31.3) over a generated set
    of governed retrieval results - Ingestion, Selection, Aggregation,
    Coverage Analysis and Budget Enforcement together, both within a
    generous budget (nothing discarded) and under a tight budget
    (forcing discards, warnings and partial coverage).

    **No database is touched**, and that is the measurement: Context
    Assembly transforms already-retrieved governed data, so its cost is
    a function of the number of governed results and of nothing else.
    Since EPIC 31.3 it cannot read for itself even if it wanted to - the
    only input it has is the results it was handed.
    """

    measurements: list[BenchmarkMeasurement] = []
    count = spec.node_count
    results = _governed_results(count)

    within_budget_request = ContextBuildRequestFactory.create(
        project_id=1,
        results=results,
        max_items=max(count, 1),
        max_assets=max(count, 1),
    )
    measurements.append(
        _timed(
            "context_builder_within_budget",
            spec.name,
            count,
            lambda: assemble_context_package(within_budget_request, now=NOW),
        )
    )

    tight_budget_request = ContextBuildRequestFactory.create(
        project_id=1,
        results=results,
        max_items=max(1, count // 4),
        max_assets=max(1, count // 8),
    )
    measurements.append(
        _timed(
            "context_builder_tight_budget",
            spec.name,
            count,
            lambda: assemble_context_package(tight_budget_request, now=NOW),
        )
    )

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

    measurements: list[BenchmarkMeasurement] = []

    # The governed context is generated rather than retrieved: these
    # benchmarks measure composition, and driving them through a
    # database read would measure the read instead. Since EPIC 31.4 they
    # open no session at all.
    context_package = _benchmark_context_package(spec.node_count)

    prompt_request = PromptBuildRequestFactory.create(
        project_id=1, context_package=context_package
    )
    measurements.append(
        _timed(
            "prompt_builder_composition",
            spec.name,
            len(context_package.selected_items),
            lambda: assemble_prompt_package(prompt_request, now=NOW),
        )
    )
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

    measurements: list[BenchmarkMeasurement] = []

    # The governed context is generated rather than retrieved: these
    # benchmarks measure composition, and driving them through a
    # database read would measure the read instead. Since EPIC 31.4 they
    # open no session at all.
    context_package = _benchmark_context_package(spec.node_count)

    prompt_request = PromptBuildRequestFactory.create(
        project_id=1, context_package=context_package
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
        context_assembly_version="1.0",
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

    context_package = _benchmark_context_package(0)

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

    context_package = _benchmark_context_package(0)

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


def run_conversation_benchmarks() -> list[BenchmarkMeasurement]:
    """
    Measures Conversation Builder overhead (Milestone 20) -
    dataset-independent and provider-independent: creating a
    conversation, starting a turn, appending a user message, attaching
    one already-built ``EngineeringResponse`` (reusing the same
    synthetic fixture ``run_engineering_response_benchmarks`` builds),
    appending an assistant message, and completing the turn - never a
    real provider call, never a database query, never persistence of
    any kind.
    """

    measurements: list[BenchmarkMeasurement] = []

    context_package = _benchmark_context_package(0)

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
        request_correlation_id="benchmark-conversation",
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

    def _run_conversation_lifecycle() -> None:
        conversation = create_conversation(
            project_id=1,
            session_id="benchmark-session",
            conversation_id="benchmark-conversation",
            now=NOW,
        ).conversation
        conversation = start_turn(conversation, "benchmark-turn", now=NOW).conversation
        conversation = append_message(
            conversation, ConversationMessageRole.USER, "Benchmark question?", now=NOW
        ).conversation
        conversation = attach_engineering_response(
            conversation, engineering_response, now=NOW
        ).conversation
        conversation = append_message(
            conversation,
            ConversationMessageRole.ASSISTANT,
            "Benchmark answer.",
            now=NOW,
        ).conversation
        complete_turn(conversation, now=NOW)

    measurements.append(
        _timed(
            "conversation_turn_lifecycle",
            "n/a",
            1,
            _run_conversation_lifecycle,
        )
    )

    return measurements


def run_working_memory_benchmarks() -> list[BenchmarkMeasurement]:
    """
    Measures Working Memory Builder overhead (Milestone 21) -
    dataset-independent and provider-independent: building
    WorkingMemory from a completed conversation turn (one attached
    EngineeringResponse, reusing the same synthetic fixture
    ``run_engineering_response_benchmarks`` builds) and its owning
    EngineeringSession - never a real provider call, never a database
    query, never persistence, never semantic interpretation of any
    kind.
    """

    measurements: list[BenchmarkMeasurement] = []

    context_package = _benchmark_context_package(0)

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
        request_correlation_id="benchmark-working-memory",
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

    session = build_initial_session(
        project_id=1, session_id="benchmark-session", now=NOW
    ).session

    conversation = create_conversation(
        project_id=1,
        session_id="benchmark-session",
        conversation_id="benchmark-conversation",
        now=NOW,
    ).conversation
    conversation = start_turn(conversation, "benchmark-turn", now=NOW).conversation
    conversation = append_message(
        conversation, ConversationMessageRole.USER, "Benchmark question?", now=NOW
    ).conversation
    conversation = attach_engineering_response(
        conversation, engineering_response, now=NOW
    ).conversation

    measurements.append(
        _timed(
            "working_memory_build",
            "n/a",
            1,
            lambda: build_working_memory(
                conversation=conversation, engineering_session=session, now=NOW
            ),
        )
    )

    return measurements


def run_all(specs: tuple[DatasetSpec, ...]) -> list[BenchmarkMeasurement]:
    measurements: list[BenchmarkMeasurement] = []

    for spec in specs:
        measurements.extend(run_governed_retrieval_benchmarks(spec))
        measurements.extend(run_context_builder_benchmarks(spec))
        measurements.extend(run_prompt_builder_benchmarks(spec))
        measurements.extend(run_llm_provider_benchmarks(spec))

    measurements.extend(run_llm_invocation_runtime_benchmarks())
    measurements.extend(run_engineering_response_benchmarks())
    measurements.extend(run_engineering_session_benchmarks())
    measurements.extend(run_conversation_benchmarks())
    measurements.extend(run_working_memory_benchmarks())

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
