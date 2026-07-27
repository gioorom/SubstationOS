"""
Value objects for Engineering Response (EPIC 5, Milestone 18). Every
type here is immutable and deterministic: the same
``EngineeringResponseBuildRequest`` and the same ``now`` always produce
the same ``EngineeringResponse``, including section ordering, content,
warnings, uncertainty declarations, and statistics.

Engineering Response is the first genuine ``app/domain/**`` bounded
context downstream of the LLM Invocation Runtime (Milestone 17) - see
``docs/architecture/adr/0015-engineering-response-foundation.md`` for
why it belongs in the domain rather than the application layer.
Consequently it deliberately does **not** import
``app.application.models.llm_invocation.LLMResponseEnvelope`` (an
application-layer type) or anything else under ``app/application/**``:
CLAUDE.md's Dependency Rule holds here exactly as it does for every
other domain bounded context ("domain depends on nothing"). Instead,
``EngineeringResponseSourceEnvelope``/``EngineeringResponseSourceContent``
below are this domain's own restatement of exactly the fields it needs
from an ``LLMResponseEnvelope`` - constructed only by
``app.services.engineering_response_service`` (the one seam allowed to
see both the application layer and this domain), never by the domain
itself. ``EngineeringSourceFinishReason``'s values are kept in sync
with ``LLMFinishReason``'s by convention (both are plain ``str, Enum``
value sets), not by a shared import.

This context freely imports ``app.domain.context_builder`` and
``app.domain.prompt_builder`` directly - both are domain bounded
contexts, and this is the same "shared, stable type reused across
contexts" pattern Prompt Builder already established for
``ContextPackage`` one layer upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


class EngineeringResponseStatus(str, Enum):
    """An engineering-native assessment of how complete a response is -
    never a copy of ``LLMInvocationStatus`` (which only ever describes
    provider-call success/failure, not engineering usefulness). Derived
    entirely from structural signals on the source envelope - never
    from reading or interpreting the response's own prose."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    EMPTY = "empty"


class EngineeringSectionType(str, Enum):
    """Every kind of section an ``EngineeringResponse`` can contain - a
    closed, exhaustive, fixed-order set, never an open-ended free-form
    section kind. Order here is the canonical, deterministic section
    order (``ENGINEERING_RESPONSE_SECTION_ORDER`` in
    ``engineering_response_composition.py``)."""

    SUMMARY = "summary"
    DIRECT_ANSWER = "direct_answer"
    TECHNICAL_EXPLANATION = "technical_explanation"
    ASSUMPTIONS = "assumptions"
    WARNINGS = "warnings"
    LIMITATIONS = "limitations"
    NEXT_ACTIONS = "next_actions"
    REFERENCES = "references"
    UNKNOWN = "unknown"


class EngineeringUncertaintyLevel(str, Enum):
    """How much this response explicitly depends on assumptions or
    missing evidence - **never** model confidence (no provider ever
    reports, and this builder never estimates, how "sure" a model is of
    its own text). ``UNKNOWN`` means this builder had no basis to judge
    at all (e.g. no response content exists to assess), which is a
    distinct, honest state from ``LOW``/``MEDIUM``/``HIGH``, not a
    default."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class EngineeringWarningCategory(str, Enum):
    """A closed, exhaustive set of structured warning categories - never
    a free-text warning string standing alone."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    PARTIAL_CONTEXT = "partial_context"
    PROVIDER_WARNING = "provider_warning"
    UNKNOWN_CONTENT = "unknown_content"
    LIMITED_RESPONSE = "limited_response"
    UNSUPPORTED_RESPONSE = "unsupported_response"


class EngineeringSourceFinishReason(str, Enum):
    """This domain's own restatement of ``LLMFinishReason`` - value-set
    identical by convention, never by import (see module docstring)."""

    COMPLETED = "completed"
    MAXIMUM_OUTPUT_REACHED = "maximum_output_reached"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_REQUEST = "tool_request"
    REFUSAL = "refusal"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EngineeringResponseSourceContent:
    """This domain's own restatement of one ``LLMResponseContent``
    block. ``is_supported_text`` restates
    ``LLMResponseContentType.TEXT`` versus ``.UNSUPPORTED`` as a plain
    boolean, avoiding any dependency on the application-layer enum
    itself."""

    sequence_index: int
    is_supported_text: bool
    text: str
    provider_block_type: str | None


@dataclass(frozen=True, slots=True)
class EngineeringResponseSourceEnvelope:
    """
    A domain-owned restatement of exactly the ``LLMResponseEnvelope``
    fields the Engineering Response Builder needs - never the
    application-layer type itself (see module docstring). Constructed
    only by ``app.services.engineering_response_service``.

    Only a **successful** invocation ever reaches this builder: per
    ``LLMInvocationResult``'s own invariant, an envelope exists only
    when the invocation's overall status is ``SUCCEEDED`` - so no
    ``status`` field is restated here at all (it would always carry
    the same single value). Presenting a failed or cancelled invocation
    to an engineer is deliberately out of this milestone's scope (see
    ADR-0015's Rejected Alternatives).
    """

    provider_id: str
    configured_model_identifier: str
    returned_model_identifier: str | None
    content: tuple[EngineeringResponseSourceContent, ...]
    finish_reason: EngineeringSourceFinishReason
    request_correlation_id: str
    attempt_count: int
    warnings: tuple[str, ...]
    input_tokens: int | None
    output_tokens: int | None
    runtime_version: str
    adapter_version: str
    request_preparation_policy_version: str


@dataclass(frozen=True, slots=True)
class EngineeringResponseSection:
    """
    One structured, typed slice of an ``EngineeringResponse``. ``body``
    is always a tuple of discrete, deterministically constructed lines
    - never a single free-form concatenated string - built by exactly
    one small, named, pure function per ``EngineeringSectionType``
    (``engineering_response_composition.py``). A section with nothing
    meaningful to contribute is still constructed, in its fixed
    position, with empty ``body`` and ``enabled=False`` - every
    ``EngineeringResponse.sections`` tuple always has this same
    nine-section shape regardless of input (the same "always the full
    fixed shape" convention Prompt Builder established for
    ``PromptPackage.sections``).

    ``SUMMARY``/``TECHNICAL_EXPLANATION``/``ASSUMPTIONS``/
    ``NEXT_ACTIONS`` are always constructed disabled and empty: this
    builder performs no AI usage and no semantic parsing of the
    provider's own prose, so it has no honest, non-invented way to
    split free text into "this part is a summary" versus "this part is
    an assumption." These four section types exist, in their fixed
    canonical position, so a future capability that *can* honestly
    populate them (e.g. a provider emitting genuinely structured,
    machine-parseable output) can do so without changing this shape -
    never populated by guessing here.
    """

    section_type: EngineeringSectionType
    title: str
    body: tuple[str, ...]
    sequence: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class EngineeringEvidenceReference:
    """One deterministic, citable pointer to the governed graph state
    that justified this response - a direct restatement of Prompt
    Builder's own ``PromptEvidenceReference``, preserved unchanged so
    no provenance is lost between the prompt that was sent and the
    response that was produced from it."""

    candidate_id: str
    graph_node_ids: tuple[str, ...]
    graph_relationship_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringWarning:
    """One structured, machine-readable warning - never a free-text
    string standing alone."""

    category: EngineeringWarningCategory
    message: str


@dataclass(frozen=True, slots=True)
class EngineeringUncertainty:
    """One structured uncertainty declaration - a specific, named
    reason this response should be trusted less than fully, never a
    single opaque number. Multiple declarations may exist on one
    response; ``EngineeringResponse.overall_uncertainty`` is the worst
    (highest) level among them (see ``engineering_response_policy.py``'s
    ``overall_uncertainty_from``)."""

    level: EngineeringUncertaintyLevel
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringResponsePolicy:
    """The versioned, documented response-composition policy Engineering
    Response applies - which structural signals produce which warnings
    and uncertainty declarations, never a per-request, ad hoc choice."""

    version: str


@dataclass(frozen=True, slots=True)
class EngineeringResponseConfiguration:
    """Everything about *how* one build run behaves - never *what* it
    builds (that is ``EngineeringResponseBuildRequest``'s own
    ``context_package``/``prompt_package``/``source``)."""

    response_policy: EngineeringResponsePolicy
    engineering_response_version: str


@dataclass(frozen=True, slots=True)
class EngineeringResponseBuildRequest:
    """
    A fully validated request to build one ``EngineeringResponse``.
    Never constructed directly - always via
    ``EngineeringResponseBuildRequestFactory.create``, which enforces
    every invariant (positive project id, the request's own project id
    matching both ``context_package.project_id`` and
    ``prompt_package.project_id``) at construction time.
    """

    project_id: int
    context_package: ContextPackage
    prompt_package: PromptPackage
    source: EngineeringResponseSourceEnvelope
    configuration: EngineeringResponseConfiguration


@dataclass(frozen=True, slots=True)
class EngineeringResponseCompositionResult:
    """The Composition stage's full output: every section, in canonical
    order, plus the fields ``EngineeringResponse`` itself exposes by
    name and the engineering-native status/uncertainty this stage
    derives - computed once, here, and threaded through unchanged."""

    sections: tuple[EngineeringResponseSection, ...]
    summary: EngineeringResponseSection
    direct_answer: EngineeringResponseSection
    references: tuple[EngineeringEvidenceReference, ...]
    warnings: tuple[EngineeringWarning, ...]
    uncertainties: tuple[EngineeringUncertainty, ...]
    overall_uncertainty: EngineeringUncertaintyLevel
    status: EngineeringResponseStatus


@dataclass(frozen=True, slots=True)
class EngineeringResponseVersion:
    """The full version identity of one ``EngineeringResponse`` - echoed
    again, for convenient single-place inspection, inside
    ``EngineeringResponseMetadata`` (the same "versioned field plus a
    metadata echo" pattern ``PromptVersion``/``PromptMetadata`` already
    established one layer upstream)."""

    engineering_response_version: str
    response_policy_version: str
    prompt_builder_version: str | None
    context_builder_version: str | None
    request_preparation_policy_version: str | None
    runtime_version: str | None
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringResponseMetadata:
    engineering_response_version: str
    response_policy_version: str
    assembled_at: datetime
    project_id: int
    provider_id: str
    configured_model_identifier: str
    returned_model_identifier: str | None
    request_correlation_id: str
    prompt_package_version: str | None
    context_builder_version: str | None
    prompt_builder_version: str | None
    package_version: str


@dataclass(frozen=True, slots=True)
class EngineeringResponseStatistics:
    section_count: int
    enabled_section_count: int
    disabled_section_count: int
    warning_count: int
    uncertainty_count: int
    reference_count: int
    character_count: int


@dataclass(frozen=True, slots=True)
class EngineeringResponseValidationResult:
    """
    The Validation stage's output: whether the just-built
    ``EngineeringResponse`` satisfies every structural invariant this
    milestone requires (required sections exist in canonical order, no
    duplicate sections, metadata is complete, statistics are internally
    consistent, at least one uncertainty declaration exists). Never
    causes building to raise - Engineering Response always produces a
    structurally valid response by construction; this result is an
    inspectable, testable proof of that, not a gate a caller must pass.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringResponse:
    """
    The bounded, structured, traceable artifact Engineering Response
    produces - the canonical output contract of the AI layer. Every
    future assistant, conversation, and engineering workflow consumes
    this, never a provider SDK response, an ``LLMResponseEnvelope``, or
    a raw prompt/response string.
    """

    project_id: int
    status: EngineeringResponseStatus
    sections: tuple[EngineeringResponseSection, ...]
    summary: EngineeringResponseSection
    direct_answer: EngineeringResponseSection
    references: tuple[EngineeringEvidenceReference, ...]
    warnings: tuple[EngineeringWarning, ...]
    uncertainties: tuple[EngineeringUncertainty, ...]
    overall_uncertainty: EngineeringUncertaintyLevel
    metadata: EngineeringResponseMetadata
    statistics: EngineeringResponseStatistics
    version: EngineeringResponseVersion


@dataclass(frozen=True, slots=True)
class EngineeringResponseBuilderResult:
    """The full envelope one Engineering Response Builder execution
    returns - the request's own project id, paired with the resulting
    ``EngineeringResponse`` and its self-validation result."""

    project_id: int
    response: EngineeringResponse
    validation: EngineeringResponseValidationResult
