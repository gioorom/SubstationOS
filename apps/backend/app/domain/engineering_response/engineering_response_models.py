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
``ContextPackage`` one layer upstream. Since Milestone 23B.1 it also
imports ``app.domain.engineering_index``'s own document-retrieval read
models for the same reason: a DOCUMENT_LOOKUP response's evidence *is* a
``DocumentReference``, and Engineering Index sits upstream in the
pipeline, so reusing its type is the same shared-vocabulary reuse rather
than a new backward dependency.

**Not every ``EngineeringResponse`` comes from an LLM.** Since Milestone
23B.1 an ``EngineeringResponseOrigin`` states plainly which production
path built a given response: ``LLM_INVOCATION`` (Milestone 18's original
path, unchanged) or ``DETERMINISTIC_RETRIEVAL`` (a response composed
entirely from governed repository state, with no provider involved at
all). Provider fields are ``None`` for the latter - never filled in with
a placeholder that would imply a model produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_index.document_retrieval_models import (
    DocumentReference,
    DocumentRetrievalResult,
)
from app.domain.engineering_reasoning.reasoning_models import (
    ReasoningResult,
)
from app.domain.engineering_reasoning.reasoning_vocabulary import (
    ReasoningDiagnosticCode,
    ReasoningOutcome,
    ReasoningRuleFamily,
)
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


class EngineeringResponseOrigin(str, Enum):
    """
    Which production path built this response - a structural fact, never
    a quality judgement.

    ``LLM_INVOCATION`` is Milestone 18's original path: a provider
    returned text, and this builder normalized it.
    ``DETERMINISTIC_RETRIEVAL`` is a response composed entirely from
    governed repository state (Milestone 23B.1's DOCUMENT_LOOKUP
    workflow): no prompt was built, no provider was called, and every
    line of every section is derived from data a repository already held.
    A consumer can therefore tell, without inspecting prose, whether a
    model was involved at all.
    """

    LLM_INVOCATION = "llm_invocation"
    DETERMINISTIC_RETRIEVAL = "deterministic_retrieval"


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

    #: A governed question had more than one governed answer. Added by
    #: EPIC 31.3: retrieval preserves ambiguity, Context Assembly
    #: preserves it and the prompt states it, so a response that dropped
    #: it here would be the one place in the chain that hid it.
    AMBIGUOUS_KNOWLEDGE = "ambiguous_knowledge"

    #: Governed knowledge itself disagrees. Added by EPIC 32.1: a
    #: deterministic rule found two different governed values for the
    #: same governed quantity of the same equipment. This is not the
    #: model being unsure and not the evidence being thin - it is a
    #: conflict inside reviewed, approved knowledge, which somebody has
    #: to resolve at the source.
    CONFLICTING_KNOWLEDGE = "conflicting_knowledge"

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


class VerificationOutcome(str, Enum):
    """
    The verdict of one engineering verification - a **closed** set of
    exactly the four outcomes a verification can have. No fifth value is
    added, and in particular there is no "unknown" member: a response
    where no verdict could be read carries ``verification.outcome = None``,
    which is a different and honest state from any of these four.

    ``NOT_SUPPORTED`` means the project's evidence **positively
    contradicts** the statement. ``INSUFFICIENT_EVIDENCE`` means the
    evidence does not cover it. Keeping those apart is the whole point:
    "the evidence does not show a differential protection on T1" and "T1
    has no differential protection" are different findings, and in this
    domain treating the first as the second is how a real installation
    gets signed off on a gap nobody looked for.
    """

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


@dataclass(frozen=True, slots=True)
class VerificationAssessment:
    """
    The machine-readable result of a verification, carried alongside the
    prose that justifies it.

    ``outcome`` is ``None`` when no verdict could be established - the
    model did not open its answer with one of the declared verdict tokens,
    and this builder does **not** infer one from the surrounding prose.
    Guessing a verdict would be inventing an engineering finding, which is
    the one thing this system never does.

    ``stated_by_model`` records whether a verdict token was actually read.
    ``evidence_bounded`` records the one case where this builder overrides
    the model: when **no** project evidence was retrieved, the outcome is
    ``INSUFFICIENT_EVIDENCE`` regardless of what the model wrote, because
    by construction there was nothing to support or contradict the
    statement with. That is a structural fact, not an interpretation - and
    it is the reason a verification cannot come back ``SUPPORTED`` from an
    empty project.

    ``evidence_reference_count`` is the number of evidence references the
    answer was built from, so a reader can see how much the verdict rests
    on without re-deriving it.
    """

    outcome: VerificationOutcome | None
    stated_by_model: bool
    evidence_bounded: bool
    evidence_reference_count: int


class ComparisonOutcome(str, Enum):
    """
    The outcome of one engineering comparison - a **closed** set of three
    values answering "could these two sides be compared on this evidence
    at all?".

    Deliberately **not** "same" versus "different". A real comparison of
    two montanti almost always contains both changed and unchanged
    aspects, so a top-level same/different verdict would force a false
    choice and lose the very detail an engineer needs. The changed and
    unchanged findings themselves live in the response body, under the
    headings the prompt asks for.

    ``INSUFFICIENT_EVIDENCE`` covers the case that matters most here: one
    or both sides carry too little evidence to compare. It is structurally
    forced whenever a side retrieved nothing, because "the project holds
    no evidence for T2" can never honestly become "T2 lacks what T1 has".
    """

    COMPARABLE = "comparable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


@dataclass(frozen=True, slots=True)
class ComparisonAssessment:
    """
    The machine-readable outcome of a comparison, carried alongside the
    prose that details it.

    ``outcome`` is ``None`` when the model did not open its answer with
    one of the declared outcome tokens - never one inferred from its
    prose, for the same reason a verification verdict is never inferred.

    ``evidence_bounded`` records the structural override: when **either**
    side retrieved no evidence, the outcome is ``INSUFFICIENT_EVIDENCE``
    whatever the model wrote. A one-sided comparison has no honest
    difference to report - the absent side's silence is a gap in the
    project's reviewed knowledge, not a finding about the equipment.

    **There are deliberately no structured ADDED/REMOVED/MODIFIED/
    UNCHANGED findings on this model.** The prompt asks the model to group
    its prose under those headings, but extracting them into typed data
    would mean parsing arbitrary prose to manufacture engineering
    findings - precisely what this system refuses to do. Until the runtime
    can return genuinely structured output, the findings remain readable
    prose in the response body and only the outcome is machine-readable.
    """

    outcome: ComparisonOutcome | None
    stated_by_model: bool
    evidence_bounded: bool
    left_evidence_count: int
    right_evidence_count: int

    @property
    def has_both_sides(self) -> bool:
        return self.left_evidence_count > 0 and self.right_evidence_count > 0


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
    """
    One deterministic, citable pointer to the governed knowledge that
    justified this response - a direct restatement of Prompt Builder's
    own ``PromptEvidenceReference``, preserved field for field so no
    provenance is lost between the prompt that was sent and the response
    produced from it.

    A citation names **which approved statement, approved in which
    review, out of which document**. It never says the answer is
    correct: it says an engineer approved the knowledge the answer was
    built from, which is a different and much narrower claim.
    """

    item_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    statement_key: str
    review_id: int
    document_id: int


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
class DerivedReasoningSupport:
    """
    One governed fact a derived conclusion was drawn from.

    Every field here is **read off governed knowledge**, never computed
    by reasoning: the governed node and edge, the Semantic Statement, the
    Human Review that approved it, and the document the evidence came
    from. That is what makes a conclusion traceable - a reader can walk
    from the conclusion back to the approved statement without trusting
    the reasoner (AF-REASON-002).

    ``value`` is the declared governed value as text and ``unit`` its
    declared unit. Rendered as text rather than as a number because this
    is a *report* of what the graph said, and a governed quantity is
    reported exactly as governed, never re-scaled or re-rounded.
    """

    node_id: str
    edge_id: str
    label: str
    value: str | None
    unit: str | None
    statement_key: str
    review_id: int
    reviewer_display_name: str
    document_id: int


@dataclass(frozen=True, slots=True)
class DerivedReasoningAssessment:
    """
    The machine-readable result of one deterministic reasoning rule
    (EPIC 32.1) - a **derived conclusion**, never governed knowledge.

    That distinction is the whole reason this is a separate field rather
    than an extra evidence reference or an extra context item. Nothing
    here was reviewed by a human, nothing here is promoted back into the
    graph, and nothing downstream may treat it as if it had been
    (AF-REASON-001, AF-REASON-003). ``supports`` names the governed facts
    the conclusion was drawn *from*; the conclusion itself is not one of
    them.

    ``outcome`` is one of four values, never a boolean and never a score.
    "The governed values agree", "they disagree", "the graph does not say"
    and "the question named more than one piece of equipment" are four
    different engineering findings, and collapsing the last three into
    "not consistent" is how a real installation gets signed off on a gap
    nobody looked for.

    ``rule_id``/``rule_version`` identify what concluded it, so a change
    in what the platform concludes is always a version change somebody
    can point at. ``diagnostic_code`` states *why* the rule reached this
    outcome, from a closed vocabulary - never free prose. ``result_id``
    is the deterministic identity of the conclusion: the same governed
    facts and the same rule version always produce the same identifier.
    """

    outcome: ReasoningOutcome
    rule_id: str
    rule_version: str
    rule_family: ReasoningRuleFamily
    diagnostic_code: ReasoningDiagnosticCode
    question: str
    result_id: str
    reasoning_policy_version: str
    supports: tuple[DerivedReasoningSupport, ...]

    @property
    def is_governed_knowledge(self) -> bool:
        """Always ``False``. Present so that any caller tempted to treat
        a conclusion as a governed fact has to read the word ``False``
        while doing it."""

        return False


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

    #: The deterministic conclusion this answer was accompanied by, when
    #: the workflow ran a reasoning step. ``None`` for every workflow
    #: that does not reason - which is all of them but engineering
    #: verification - and the response then simply carries no derived
    #: reasoning. Optional on purpose: reasoning is a capability a
    #: workflow opts into, not a precondition of answering.
    reasoning: ReasoningResult | None = None


@dataclass(frozen=True, slots=True)
class EngineeringResponseDocumentLookupBuildRequest:
    """
    A fully validated request to build one ``EngineeringResponse`` from an
    already-executed document lookup - the ``DETERMINISTIC_RETRIEVAL``
    counterpart to ``EngineeringResponseBuildRequest``. Never constructed
    directly; always via
    ``EngineeringResponseDocumentLookupBuildRequestFactory.create``.

    Carries **no** ``ContextPackage``, ``PromptPackage`` or source
    envelope: the DOCUMENT_LOOKUP workflow builds none of them, and
    demanding them here would force a caller to fabricate a prompt that
    was never sent and a provider response that never happened.
    ``request_correlation_id`` is the caller's own correlation identifier
    - it correlates one engine execution, and implies no provider call.
    """

    project_id: int
    retrieval_result: DocumentRetrievalResult
    request_correlation_id: str
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
    document_references: tuple[DocumentReference, ...] = ()
    verification: VerificationAssessment | None = None
    comparison: ComparisonAssessment | None = None

    #: A derived conclusion (EPIC 32.1), or ``None`` when this workflow
    #: did not reason. Deliberately a field of its own rather than an
    #: entry in ``references``: ``references`` are governed evidence,
    #: and a conclusion is not evidence.
    derived_reasoning: DerivedReasoningAssessment | None = None


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
    context_assembly_version: str | None
    request_preparation_policy_version: str | None
    runtime_version: str | None
    package_version: str
    # Populated only for DETERMINISTIC_RETRIEVAL responses - the
    # provenance of the deterministic capability that produced the
    # evidence, exactly as ``runtime_version`` records the LLM runtime's
    # for an LLM_INVOCATION response.
    document_retrieval_version: str | None = None
    document_relevance_policy_version: str | None = None


@dataclass(frozen=True, slots=True)
class EngineeringResponseMetadata:
    """``provider_id``/``configured_model_identifier`` are ``None``
    exactly when ``EngineeringResponse.origin`` is
    ``DETERMINISTIC_RETRIEVAL``: no provider and no model were involved,
    so naming one would be a fabrication. Validation enforces that
    correspondence in both directions."""

    engineering_response_version: str
    response_policy_version: str
    assembled_at: datetime
    project_id: int
    provider_id: str | None
    configured_model_identifier: str | None
    returned_model_identifier: str | None
    request_correlation_id: str
    prompt_package_version: str | None
    context_assembly_version: str | None
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
    document_reference_count: int = 0


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
    produces - the canonical output contract of the engineering answer
    layer. Every future assistant, conversation, and engineering workflow
    consumes this, never a provider SDK response, an
    ``LLMResponseEnvelope``, or a raw prompt/response string.

    ``origin`` defaults to ``LLM_INVOCATION`` so every response built
    before Milestone 23B.1 keeps exactly the meaning it already had.
    ``document_references`` is populated only by the DOCUMENT_LOOKUP
    workflow; ``references`` (graph evidence) stays empty for it, since
    that workflow retrieves documents rather than graph facts - the two
    reference kinds are deliberately not conflated.

    ``verification`` is populated only for a response built from a
    verification prompt (Milestone 24.1). It is a **new field rather than
    a reuse of ``status``** deliberately: ``EngineeringResponseStatus``
    already means "how complete is this response" - its ``UNSUPPORTED``
    member means "the provider returned no usable text" - and overloading
    it to also mean "the evidence does not support the statement" would
    make two entirely different findings indistinguishable. Warnings and
    uncertainty declarations cannot express ``SUPPORTED`` at all.
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
    origin: EngineeringResponseOrigin = EngineeringResponseOrigin.LLM_INVOCATION
    document_references: tuple[DocumentReference, ...] = ()
    verification: VerificationAssessment | None = None
    comparison: ComparisonAssessment | None = None

    #: A derived conclusion (EPIC 32.1), or ``None`` when this workflow
    #: did not reason. Deliberately a field of its own rather than an
    #: entry in ``references``: ``references`` are governed evidence,
    #: and a conclusion is not evidence.
    derived_reasoning: DerivedReasoningAssessment | None = None


@dataclass(frozen=True, slots=True)
class EngineeringResponseBuilderResult:
    """The full envelope one Engineering Response Builder execution
    returns - the request's own project id, paired with the resulting
    ``EngineeringResponse`` and its self-validation result."""

    project_id: int
    response: EngineeringResponse
    validation: EngineeringResponseValidationResult
