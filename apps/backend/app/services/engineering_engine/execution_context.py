"""
The typed workflow execution context (Milestone 23A).

**Not an untyped dict, and not one giant mutable object.** It is a
frozen dataclass with explicitly typed optional artifact fields;
producing an artifact returns a *new* context via ``with_artifact``.
Steps declare which artifacts they require and produce
(``WorkflowStepDefinition``), and ``missing_artifacts`` reports any
required artifact the context does not yet carry, so a missing
dependency fails deterministically rather than surfacing as an
``AttributeError`` deep inside a handler.

This lives in the application layer because its artifact *types* come
from Structured Retrieval, Context Builder, Prompt Builder, the LLM
Runtime, and Engineering Response. The engine domain knows only the
``WorkflowArtifactKey`` enum, never these types.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.models.llm_invocation import LLMResponseEnvelope
from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_engine.engineering_engine_models import (
    ConversationUpdateProposal,
    EngineeringEngineExecutionRequest,
    SessionUpdateProposal,
    WorkflowArtifactKey,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
    EngineeringResponseValidationResult,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage
from app.domain.structured_retrieval.structured_retrieval_models import (
    StructuredRetrievalRequest,
    StructuredRetrievalResult,
)


@dataclass(frozen=True, slots=True)
class WorkflowExecutionContext:
    """Immutable; every ``with_artifact`` call returns a new context."""

    execution_request: EngineeringEngineExecutionRequest
    retrieval_request: StructuredRetrievalRequest | None = None
    retrieval_result: StructuredRetrievalResult | None = None
    context_package: ContextPackage | None = None
    prompt_package: PromptPackage | None = None
    llm_response_envelope: LLMResponseEnvelope | None = None
    engineering_response: EngineeringResponse | None = None
    engineering_response_validation: (
        EngineeringResponseValidationResult | None
    ) = None
    conversation_update_proposal: ConversationUpdateProposal | None = None
    session_update_proposal: SessionUpdateProposal | None = None

    _FIELD_BY_KEY = {
        WorkflowArtifactKey.EXECUTION_REQUEST: "execution_request",
        WorkflowArtifactKey.RETRIEVAL_REQUEST: "retrieval_request",
        WorkflowArtifactKey.RETRIEVAL_RESULT: "retrieval_result",
        WorkflowArtifactKey.CONTEXT_PACKAGE: "context_package",
        WorkflowArtifactKey.PROMPT_PACKAGE: "prompt_package",
        WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE: "llm_response_envelope",
        WorkflowArtifactKey.ENGINEERING_RESPONSE: "engineering_response",
        WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION: (
            "engineering_response_validation"
        ),
        WorkflowArtifactKey.CONVERSATION_UPDATE_PROPOSAL: (
            "conversation_update_proposal"
        ),
        WorkflowArtifactKey.SESSION_UPDATE_PROPOSAL: "session_update_proposal",
    }

    def has_artifact(self, key: WorkflowArtifactKey) -> bool:
        return getattr(self, self._FIELD_BY_KEY[key]) is not None

    def get_artifact(self, key: WorkflowArtifactKey):
        return getattr(self, self._FIELD_BY_KEY[key])

    def with_artifact(
        self, key: WorkflowArtifactKey, value
    ) -> "WorkflowExecutionContext":
        return replace(self, **{self._FIELD_BY_KEY[key]: value})

    def missing_artifacts(
        self, required: tuple[WorkflowArtifactKey, ...]
    ) -> tuple[WorkflowArtifactKey, ...]:
        return tuple(key for key in required if not self.has_artifact(key))
