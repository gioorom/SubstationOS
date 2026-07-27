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

NOW = datetime(2026, 1, 1, 5, 0, 0)


class FakeGraphQueryRepository:
    """An empty project. Retrieval finds nothing, which is a valid
    outcome the whole pipeline handles - no candidates simply yields an
    EngineeringResponse with an INSUFFICIENT_EVIDENCE warning."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.list_nodes_calls = 0

    def _maybe_raise(self) -> None:
        if self._raises is not None:
            raise self._raises

    def list_nodes(self, project_id):
        self.list_nodes_calls += 1
        self._maybe_raise()
        return []

    def list_relationships(self, project_id):
        self._maybe_raise()
        return []

    def list_nodes_by_type(self, project_id, entity_type):
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
):
    return build_engineering_engine(
        graph_query_repository=(
            graph_query_repository or FakeGraphQueryRepository()
        ),
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
