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
from Structured Retrieval, Document Retrieval, Context Builder, Prompt
Builder, the LLM Runtime, and Engineering Response. The engine domain
knows only the ``WorkflowArtifactKey`` enum, never these types.

One context serves every registered workflow. A workflow simply leaves
the artifacts it never produces as ``None``: the knowledge-query workflow
carries no document retrieval result, the document-lookup workflow
carries no prompt package or response envelope. This is why a new
workflow adds *fields* here and changes no logic - and why the plan
executor's artifact checks catch a workflow that forgets to produce
something it declared, without knowing which workflow is running.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.models.llm_invocation import LLMResponseEnvelope
from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
)
from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalRequest,
    DocumentRetrievalResult,
)
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
    document_retrieval_request: DocumentRetrievalRequest | None = None
    document_retrieval_result: DocumentRetrievalResult | None = None
    # The two comparison sides, kept distinct end to end (Milestone 24.2).
    # Named fields rather than a keyed collection: there is no index to
    # transpose, so no code path can silently swap left for right.
    left_retrieval_request: StructuredRetrievalRequest | None = None
    right_retrieval_request: StructuredRetrievalRequest | None = None
    left_retrieval_result: StructuredRetrievalResult | None = None
    right_retrieval_result: StructuredRetrievalResult | None = None
    comparison_context: ComparisonContextPackage | None = None
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
        WorkflowArtifactKey.DOCUMENT_RETRIEVAL_REQUEST: (
            "document_retrieval_request"
        ),
        WorkflowArtifactKey.DOCUMENT_RETRIEVAL_RESULT: (
            "document_retrieval_result"
        ),
        WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST: "left_retrieval_request",
        WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST: (
            "right_retrieval_request"
        ),
        WorkflowArtifactKey.LEFT_RETRIEVAL_RESULT: "left_retrieval_result",
        WorkflowArtifactKey.RIGHT_RETRIEVAL_RESULT: "right_retrieval_result",
        WorkflowArtifactKey.COMPARISON_CONTEXT: "comparison_context",
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
