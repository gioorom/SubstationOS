"""
Shared, non-collected fakes for Engineering Engine tests (Milestone
23A). Every external dependency is faked or in-memory - **no real
provider is ever called.**
"""

from __future__ import annotations

import random
from datetime import datetime

from app.application.models.llm_invocation import LLMRuntimeConfiguration
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineExecutionRequest,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentType,
)
from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_models import GraphNodeView
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeLLMProviderAdapter,
)
from app.services.engineering_engine.composition import (
    build_engineering_engine,
)

NOW = datetime(2026, 1, 1, 5, 0, 0)


class FakeGraphQueryRepository:
    """An empty project. Retrieval finds nothing, which is a valid
    outcome the whole pipeline handles - no candidates simply yields an
    EngineeringResponse with an INSUFFICIENT_EVIDENCE warning."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.list_nodes_calls = 0
        self.list_nodes_by_type_calls = 0

    def _maybe_raise(self) -> None:
        if self._raises is not None:
            raise self._raises

    @property
    def read_calls(self) -> int:
        """Every graph read this fake was asked for, whichever shape -
        so a test can assert "the graph was consulted" without having to
        know which retrieval mode the request happened to select."""

        return self.list_nodes_calls + self.list_nodes_by_type_calls

    def list_nodes(self, project_id):
        self.list_nodes_calls += 1
        self._maybe_raise()
        return []

    def list_relationships(self, project_id):
        self._maybe_raise()
        return []

    def list_nodes_by_type(self, project_id, entity_type):
        self.list_nodes_by_type_calls += 1
        self._maybe_raise()
        return []

    def list_nodes_with_attribute(self, project_id, attribute):
        self._maybe_raise()
        return []

    def get_node(self, project_id, graph_entity_id):
        self._maybe_raise()
        return None

    def list_outgoing_relationships(self, project_id, graph_entity_id):
        self._maybe_raise()
        return []

    def list_incoming_relationships(self, project_id, graph_entity_id):
        self._maybe_raise()
        return []


class PopulatedFakeGraphQueryRepository(FakeGraphQueryRepository):
    """A project containing real nodes, so retrieval finds candidates and
    the context package is non-empty.

    Needed by the verification tests: with an empty project every
    verification is structurally bounded to ``INSUFFICIENT_EVIDENCE``
    (correctly), so proving the other three outcomes requires evidence to
    actually exist.
    """

    def __init__(
        self,
        canonical_ids: tuple[str, ...] = ("87T",),
        *,
        entity_type: str = "RELAY",
        raises: Exception | None = None,
    ) -> None:
        super().__init__(raises=raises)
        self._entity_type = entity_type
        self._nodes = tuple(
            GraphNodeView(
                project_id=1,
                graph_entity_id=GraphEntityId(
                    project_id=1,
                    entity_type=entity_type,
                    canonical_id=canonical_id,
                ),
                entity_type=entity_type,
                canonical_id=canonical_id,
                properties={},
                created_at=NOW,
                updated_at=NOW,
            )
            for canonical_id in canonical_ids
        )

    def list_nodes(self, project_id):
        self.list_nodes_calls += 1
        self._maybe_raise()
        return list(self._nodes)

    def list_nodes_by_type(self, project_id, entity_type):
        self.list_nodes_by_type_calls += 1
        self._maybe_raise()
        return [
            node for node in self._nodes if node.entity_type == entity_type
        ]


class FakeEngineeringIndexRepository:
    """Only the one read the document-lookup workflow performs is
    implemented - ``search_by_identifier`` - matching case-insensitively
    on a substring, exactly as the real SQLAlchemy adapter does. The write
    side of ``EngineeringIndexRepository`` is deliberately absent: the
    workflow never writes."""

    def __init__(self, entries=(), *, raises: Exception | None = None) -> None:
        self._entries = tuple(entries)
        self._raises = raises
        self.search_calls = 0

    def search_by_identifier(self, project_id: int, identifier: str):
        self.search_calls += 1

        if self._raises is not None:
            raise self._raises

        needle = identifier.casefold()

        return [
            entry
            for entry in self._entries
            if entry.project_id == project_id
            and needle in entry.identifier.casefold()
        ]


class FakeDocumentMetadataPort:
    def __init__(self, records=()) -> None:
        self._records = tuple(records)
        self.find_many_calls = 0

    def find_many(self, document_ids: tuple[int, ...]):
        self.find_many_calls += 1

        return tuple(
            record
            for record in self._records
            if record.document_id in document_ids
        )


async def no_op_sleeper(_seconds: float) -> None:
    return None


def runtime_configuration(**overrides) -> LLMRuntimeConfiguration:
    defaults = dict(
        enabled=True,
        provider_id="fake",
        model_identifier="fake-model",
        connect_timeout_seconds=5.0,
        read_timeout_seconds=30.0,
        total_deadline_seconds=60.0,
        max_attempts=3,
        retry_base_delay_seconds=0.01,
        retry_max_delay_seconds=0.05,
        retry_jitter_enabled=False,
        default_max_output_tokens=1024,
        default_temperature=None,
    )
    defaults.update(overrides)
    return LLMRuntimeConfiguration(**defaults)


def provider_registry(outcomes=()) -> LLMProviderRegistry:
    registry = LLMProviderRegistry()
    registry.register("fake", FakeLLMProviderAdapter(outcomes=outcomes))
    return registry


def build_test_engine(
    *,
    outcomes=(),
    graph_query_repository=None,
    credential_present: bool = True,
    runtime_config: LLMRuntimeConfiguration | None = None,
    engineering_index_repository=None,
    document_metadata_port=None,
    register_document_lookup_handlers: bool = True,
):
    """``register_document_lookup_handlers=False`` composes an engine that
    registers the DOCUMENT_LOOKUP *workflow* but none of its handlers -
    the "capability not wired" case."""

    if register_document_lookup_handlers:
        engineering_index_repository = (
            engineering_index_repository or FakeEngineeringIndexRepository()
        )
        document_metadata_port = (
            document_metadata_port or FakeDocumentMetadataPort()
        )
    else:
        engineering_index_repository = None
        document_metadata_port = None

    return build_engineering_engine(
        graph_query_repository=(
            graph_query_repository or FakeGraphQueryRepository()
        ),
        engineering_index_repository=engineering_index_repository,
        document_metadata_port=document_metadata_port,
        provider_registry=provider_registry(outcomes),
        runtime_configuration=runtime_config or runtime_configuration(),
        credential_present=credential_present,
        credential_environment_variable_name="FAKE_API_KEY",
        clock=lambda: NOW,
        sleeper=no_op_sleeper,
        random_source=random.Random(1),
    )


def execution_request(**overrides) -> EngineeringEngineExecutionRequest:
    defaults = dict(
        project_id=1,
        engineering_session_id="sess-1",
        conversation_id="conv-1",
        turn_id="turn-1",
        request_text="Quale TA è installato sul montante T2?",
        engineering_intent_id="conv-1:turn-1:1.0",
        intent_type=EngineeringIntentType.KNOWLEDGE_QUERY,
        executed_at=NOW,
        retrieval_entity_type="CABLE",
        provider_id="fake",
        model_identifier="fake-model",
    )
    defaults.update(overrides)
    return EngineeringEngineExecutionRequest(**defaults)
