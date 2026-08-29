"""
The provider-neutral request contract (EPIC 4, Milestone 16). Every
type here represents SubstationOS's own intent toward a language-model
provider - never a copy of one provider's API design. A
``PromptPackage`` (Prompt Builder's own artifact) maps deterministically
into an ``LLMRequest`` here (see
``app.application.services.prompt_package_to_llm_request_mapper``);
only a provider-specific infrastructure adapter (e.g.
``app.infrastructure.llm.anthropic``) may translate an ``LLMRequest``
further into that provider's own local, immutable representation. No
type in this module imports a provider SDK, performs I/O, or
serializes anything - request preparation is pure, deterministic data
transformation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from app.application.models.llm_capabilities import (
    LLMCapability,
    LLMCapabilityValidationResult,
    LLMProviderCapabilities,
)
from app.domain.prompt_builder.prompt_builder_models import PromptEvidenceReference


class LLMMessageRole(str, Enum):
    """Provider-neutral semantic roles - never a provider-native string
    exposed directly as this contract. Only ``INSTRUCTION`` and
    ``CONTEXT`` are produced by this milestone's PromptPackage mapper
    (no real end-user question or assistant turn exists yet); ``USER``/
    ``ASSISTANT``/``TOOL`` are declared for forward compatibility with
    Milestone 17 (LLM Invocation Runtime), which will introduce real
    conversational turns."""

    INSTRUCTION = "instruction"
    CONTEXT = "context"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMContentType(str, Enum):
    """A closed, extensible set of content block kinds. Only ``TEXT``
    and ``REFERENCE`` are produced this milestone; ``STRUCTURED_DATA``
    is declared for future extension (e.g. a typed payload a future
    provider capability could accept) without being implemented
    speculatively now."""

    TEXT = "text"
    STRUCTURED_DATA = "structured_data"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class LLMContentBlock:
    content_type: LLMContentType
    text: str


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """One provider-neutral message - one originating ``PromptSection``
    per message, in the section's own canonical order. ``section_type``
    preserves the originating ``PromptSectionType`` value for
    traceability; only sections Prompt Builder marked ``enabled`` ever
    become an ``LLMMessage`` (see the mapper's own "include only
    enabled sections" rule)."""

    role: LLMMessageRole
    section_type: str
    content_blocks: tuple[LLMContentBlock, ...]


@dataclass(frozen=True, slots=True)
class LLMGenerationParameters:
    """Portable generation intentions - never a provider-specific
    parameter. Not every provider supports every field; an adapter
    that cannot honor one reports it as a warning rather than silently
    translating or ignoring it (see
    ``llm_capabilities.LLMCapabilityValidationResult``)."""

    max_output_tokens: int | None = None
    temperature: float | None = None
    stop_sequences: tuple[str, ...] = ()
    deterministic_preference: bool = False


@dataclass(frozen=True, slots=True)
class LLMProviderSelection:
    """An opaque, runtime-configured provider identifier - never
    validated against a hardcoded set of "known" providers."""

    provider_id: str


@dataclass(frozen=True, slots=True)
class LLMModelSelection:
    """An opaque, runtime-configured model identifier - never a
    hardcoded Claude/GPT version, and never validated against a static
    model-name list. Structural validity (non-blank, bounded length) is
    the only check this layer performs."""

    model_identifier: str


@dataclass(frozen=True, slots=True)
class LLMCapabilityRequirements:
    required_capabilities: tuple[LLMCapability, ...]


@dataclass(frozen=True, slots=True)
class LLMRequestMetadata:
    """
    Operational metadata, never engineering knowledge and never a
    secret - traces one prepared request back to every policy version
    that produced it, and to the project it belongs to.
    ``excluded_section_types`` preserves which ``PromptSectionType``s
    were disabled and therefore excluded from ``LLMRequest.messages``,
    satisfying Milestone 16's "preserve enabled/disabled semantics"
    requirement without transmitting their (empty) content.
    """

    project_id: int
    context_assembly_version: str | None
    prompt_builder_version: str
    composition_policy_version: str
    prompt_package_version: str
    provider_abstraction_version: str
    request_preparation_policy_version: str
    provider_id: str
    model_identifier: str
    request_correlation_id: str
    excluded_section_types: tuple[str, ...]
    prepared_at: datetime


@dataclass(frozen=True, slots=True)
class LLMRequestVersion:
    provider_abstraction_version: str
    request_preparation_policy_version: str


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """
    The provider-neutral request - the one artifact every provider
    adapter's ``prepare_request`` consumes. Deterministic: the same
    ``PromptPackage`` and the same configuration (provider/model
    selection, generation parameters, capability requirements) always
    produce an identical ``LLMRequest``, given the same injected
    ``now``/``request_correlation_id`` (never read from the wall clock
    or generated internally - see the mapper).
    """

    project_id: int
    provider_selection: LLMProviderSelection
    model_selection: LLMModelSelection
    messages: tuple[LLMMessage, ...]
    references: tuple[PromptEvidenceReference, ...]
    generation_parameters: LLMGenerationParameters
    capability_requirements: LLMCapabilityRequirements
    metadata: LLMRequestMetadata
    version: LLMRequestVersion


@runtime_checkable
class PreparedProviderRequest(Protocol):
    """
    The structural shape every provider-native prepared request must
    satisfy - a local, immutable representation
    (``AnthropicPreparedRequest``, ``FakePreparedRequest``, ...), never
    a provider SDK object, never serialized, never sent over the
    network. A ``Protocol`` (not an ``ABC``) so each adapter's own
    frozen dataclass can satisfy this shape without inheriting from a
    shared base - the application layer only needs to know a prepared
    request can identify which provider produced it.
    """

    provider_id: str


@dataclass(frozen=True, slots=True)
class LLMRequestPreparationResult:
    """The full, inspectable output of one request-preparation run -
    returned by ``LLMRequestPreparationService``, never partially
    populated. ``warnings`` carries non-fatal, informational notices
    (e.g. an optional generation parameter the resolved provider does
    not support); a genuinely invalid input raises a typed exception
    instead (see ``llm_exceptions.py``) and never reaches this type."""

    request: LLMRequest
    provider_capabilities: LLMProviderCapabilities
    capability_validation: LLMCapabilityValidationResult
    prepared_request: PreparedProviderRequest
    warnings: tuple[str, ...]
