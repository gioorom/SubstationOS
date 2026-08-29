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
from app.infrastructure.llm.base.fake_llm_provider_adapter import (
    FakeLLMProviderAdapter,
)
from app.services.engineering_engine.composition import (
    build_engineering_engine,
)
from tests._governed_graph_builder import governed_asset_with_quantity

NOW = datetime(2026, 1, 1, 5, 0, 0)


class FakeGovernedKnowledgeReader:
    """
    An installation whose governed graph is empty.

    Retrieval finds nothing, which is a valid outcome the whole pipeline
    handles - no candidates simply yields an ``EngineeringResponse``
    with an ``INSUFFICIENT_EVIDENCE`` warning.

    Implements ``GovernedKnowledgeReader`` structurally rather than by
    inheritance so a missing method is a loud ``AttributeError`` in the
    test that needs it, not a silently inherited stub.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.node_reads = 0
        self.edge_reads = 0

    def _maybe_raise(self) -> None:
        if self._raises is not None:
            raise self._raises

    @property
    def read_calls(self) -> int:
        """Every governed read this fake was asked for, whichever shape -
        so a test can assert "the governed graph was consulted" without
        having to know which query the request happened to produce."""

        return self.node_reads + self.edge_reads

    def find_node(self, node_id):
        self.node_reads += 1
        self._maybe_raise()
        return None

    def find_edge(self, edge_id):
        self.edge_reads += 1
        self._maybe_raise()
        return None

    def nodes(self, *, states, kind=None, project_id=None, document_id=None):
        self.node_reads += 1
        self._maybe_raise()
        return ()

    def nodes_by_identity(self, node_ids):
        self._maybe_raise()
        return ()

    def edges(self, *, states, kind=None, project_id=None, document_id=None):
        self.edge_reads += 1
        self._maybe_raise()
        return ()

    def edges_from_subjects(self, subject_node_ids, *, states, kind=None):
        self.edge_reads += 1
        self._maybe_raise()
        return ()

    def latest_generation(self):
        return None


class PopulatedFakeGovernedKnowledgeReader(FakeGovernedKnowledgeReader):
    """
    An installation holding real governed knowledge: one approved asset
    per designation, each with a rated-power quantity.

    Needed by the verification and comparison tests: with an empty
    governed graph every verification is structurally bounded to
    ``INSUFFICIENT_EVIDENCE`` (correctly), so proving the other outcomes
    requires knowledge to actually exist.
    """

    def __init__(
        self,
        designations: tuple[str, ...] = ("87T",),
        *,
        project_id: int = 1,
        raises: Exception | None = None,
    ) -> None:
        super().__init__(raises=raises)

        self._nodes = {}
        self._edges = {}

        for index, designation in enumerate(designations, start=1):
            asset, quantity, edge = governed_asset_with_quantity(
                designation=designation,
                document_id=index,
                project_id=project_id,
                created_at=NOW,
            )
            self._nodes[asset.node_id.value] = asset
            self._nodes[quantity.node_id.value] = quantity
            self._edges[edge.edge_id.value] = edge

    def _in_states(self, items, states):
        return tuple(
            item
            for item in sorted(items, key=lambda item: _identity(item))
            if item.state in states
        )

    def find_node(self, node_id):
        self.node_reads += 1
        self._maybe_raise()
        return self._nodes.get(node_id)

    def find_edge(self, edge_id):
        self.edge_reads += 1
        self._maybe_raise()
        return self._edges.get(edge_id)

    def nodes(self, *, states, kind=None, project_id=None, document_id=None):
        self.node_reads += 1
        self._maybe_raise()

        return tuple(
            node
            for node in self._in_states(self._nodes.values(), states)
            if (kind is None or node.kind is kind)
            and (
                project_id is None
                or node.provenance.project_id == project_id
            )
            and (
                document_id is None
                or node.provenance.document_id == document_id
            )
        )

    def nodes_by_identity(self, node_ids):
        self._maybe_raise()
        wanted = set(node_ids)

        return tuple(
            node
            for node in sorted(
                self._nodes.values(), key=lambda node: node.node_id.value
            )
            if node.node_id.value in wanted
        )

    def edges(self, *, states, kind=None, project_id=None, document_id=None):
        self.edge_reads += 1
        self._maybe_raise()

        return tuple(
            edge
            for edge in self._in_states(self._edges.values(), states)
            if (kind is None or edge.kind is kind)
            and (
                project_id is None
                or edge.provenance.project_id == project_id
            )
            and (
                document_id is None
                or edge.provenance.document_id == document_id
            )
        )

    def edges_from_subjects(self, subject_node_ids, *, states, kind=None):
        self.edge_reads += 1
        self._maybe_raise()
        wanted = set(subject_node_ids)

        return tuple(
            edge
            for edge in self._in_states(self._edges.values(), states)
            if edge.subject_node_id in wanted
            and (kind is None or edge.kind is kind)
        )


def _identity(item) -> str:
    return getattr(item, "node_id", None) and item.node_id.value or (
        item.edge_id.value
    )


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
    governed_knowledge_reader=None,
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
        governed_knowledge_reader=(
            governed_knowledge_reader or FakeGovernedKnowledgeReader()
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
        # A designation the request text actually names. Governed
        # retrieval resolves designations, so a default of
        # `retrieval_entity_type` (which the governed graph has no
        # counterpart for) would make every engine test exercise the
        # "nothing to ask" path rather than the retrieval path.
        retrieval_lexical_terms=("T2",),
        provider_id="fake",
        model_identifier="fake-model",
    )
    defaults.update(overrides)
    return EngineeringEngineExecutionRequest(**defaults)
