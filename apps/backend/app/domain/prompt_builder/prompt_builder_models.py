"""
Value objects for Prompt Builder (EPIC 4, Milestone 15). Every type
here is immutable and deterministic: the same ``ContextPackage`` and
the same ``PromptBuilderConfiguration`` always produce the same
``PromptPackage``, including section ordering, content, token
estimates, and statistics. Prompt Builder consumes Context Builder's
own output type (``ContextPackage``) as its shared, stable input
vocabulary - the same "reuse the upstream artifact" pattern Context
Assembly itself follows for Governed Structured Retrieval's
``GovernedRetrievalResult``. No type in this module performs I/O,
calls an LLM, imports a provider SDK, or serializes a provider-specific
payload - a ``PromptPackage`` is a structured, provider-independent
artifact; formatting it into an OpenAI/Anthropic/any other provider's
request shape is explicitly out of this bounded context's scope (a
future infrastructure-layer adapter's job, never Prompt Builder's).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.context_builder.context_builder_models import ContextPackage


class PromptObjective(str, Enum):
    """
    What kind of answer the assembled prompt asks for - the *only* thing
    a caller may vary about a ``PromptPackage``'s composition, and the
    minimum addition Milestone 23B.2 needed to support explanation-style
    responses.

    Deliberately **not** a free-form prompt, a template, a persona, or a
    caller-supplied instruction string: it selects between fixed,
    versioned instruction and expected-output sets declared in
    ``composition_policy.py``, so every prompt this system can produce is
    still enumerable and reviewable.

    ``DIRECT_ANSWER`` answers the question asked, as briefly as the
    evidence allows (the KNOWLEDGE_QUERY workflow's shape, and the
    default - a package built without naming an objective is
    byte-identical to one built before this enum existed).
    ``ENGINEERING_EXPLANATION`` asks instead for the function, role and
    behaviour of the retrieved equipment to be set out for an engineer.
    ``ENGINEERING_VERIFICATION`` asks a different kind of question
    altogether: not "tell me about this" but "does the project's own
    evidence support this statement?" - and it requires a machine-readable
    verdict, because a verification whose answer a system cannot read is a
    verification nobody can act on.
    ``ENGINEERING_COMPARISON`` asks about **two** subjects at once, and is
    the only objective whose evidence arrives as two labelled groups that
    must never be conflated: "what changed between the left and the
    right?" is unanswerable if the prompt cannot say which evidence is
    which, and answering it backwards is worse than not answering.

    **The objective never varies the truthfulness constraints.** Every
    objective carries exactly the same ``CONSTRAINTS``: an explanation is
    held to the same "never invent an engineering fact" rule as a direct
    answer, because a longer answer is a larger opportunity to invent
    one, not a licence to - and a verification is held to it most of all,
    since the whole value of a verification is that it reports what the
    evidence says rather than what the equipment type usually does.
    """

    DIRECT_ANSWER = "direct_answer"
    ENGINEERING_EXPLANATION = "engineering_explanation"
    ENGINEERING_VERIFICATION = "engineering_verification"
    ENGINEERING_COMPARISON = "engineering_comparison"


class PromptSectionType(str, Enum):
    """Every kind of section a ``PromptPackage`` can contain - a closed,
    exhaustive, fixed-order set, never an open-ended free-form section
    kind. Order here is the canonical, deterministic section order
    (``PROMPT_SECTION_ORDER`` in ``prompt_composition.py``)."""

    SYSTEM_CONTEXT = "system_context"
    ENGINEERING_CONTEXT = "engineering_context"
    SELECTED_KNOWLEDGE = "selected_knowledge"
    # The two comparison sides (Milestone 24.2). They exist as distinct
    # section types, rather than as labelled lines inside
    # SELECTED_KNOWLEDGE, because a comparison prompt that cannot say
    # which evidence is which is unanswerable - and a flattened rendering
    # would let a formatting change silently swap the sides. Like every
    # other section, they are always constructed: empty and disabled for
    # every objective that is not a comparison.
    LEFT_KNOWLEDGE = "left_knowledge"
    RIGHT_KNOWLEDGE = "right_knowledge"
    EVIDENCE_REFERENCES = "evidence_references"
    CONSTRAINTS = "constraints"
    FORMATTING_RULES = "formatting_rules"
    EXPECTED_OUTPUT = "expected_output"
    WARNINGS = "warnings"
    METADATA = "metadata"


@dataclass(frozen=True, slots=True)
class PromptSection:
    """
    One structured, typed slice of a ``PromptPackage``. ``content`` is
    always a tuple of discrete, deterministically constructed lines -
    never a single free-form concatenated string - built by exactly one
    small, named, pure function per ``PromptSectionType``
    (``prompt_composition.py``). ``enabled`` is ``False`` when a section
    has nothing meaningful to contribute (e.g. no candidates were
    selected, or no warnings were reported) - the section object still
    exists, in its fixed position, with empty ``content``, so
    ``PromptPackage.sections`` always has the same shape regardless of
    input.
    """

    section_type: PromptSectionType
    priority: int
    content: tuple[str, ...]
    estimated_token_count: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class PromptConstraint:
    """A fixed, versioned behavioral guardrail - never derived from
    ``ContextPackage`` content, always the same set for a given
    ``PromptCompositionPolicy`` version (``composition_policy.py``)."""

    identifier: str
    description: str


@dataclass(frozen=True, slots=True)
class PromptInstruction:
    """A fixed, versioned formatting/structural instruction for how the
    expected output should be produced - distinct from
    ``PromptConstraint``, which governs truthfulness, not formatting."""

    identifier: str
    description: str


@dataclass(frozen=True, slots=True)
class PromptEvidenceReference:
    """
    One deterministic, citable pointer to the governed knowledge that
    justified including one context item - never a copy of engineering
    content, only the identities a consumer needs to trace a claim back
    to the review that authorised it.

    ``statement_key`` and ``review_id`` are what make the citation
    governed rather than merely structural: a node id says *which object*,
    and those two say *which approved statement, approved by whom*. The
    chain from here is

    ``statement_key -> review_id -> support_fingerprint -> document_id``,

    each addressing an artefact that already has its own API, which is
    why none of them is copied into the prompt.
    """

    item_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    statement_key: str
    review_id: int
    document_id: int


@dataclass(frozen=True, slots=True)
class PromptCompositionPolicy:
    """The versioned, documented composition policy Prompt Builder
    applies - which fixed constraints/instructions are in force, and
    the token-estimation convention - never a per-request, ad hoc
    choice."""

    version: str


@dataclass(frozen=True, slots=True)
class PromptBuilderConfiguration:
    """Everything about *how* one assembly run behaves - never *what*
    it assembles (that is ``PromptBuildRequest.context_package``)."""

    composition_policy: PromptCompositionPolicy
    prompt_builder_version: str


@dataclass(frozen=True, slots=True)
class PromptBuildRequest:
    """
    A fully validated request to assemble one ``PromptPackage``. Never
    constructed directly - always via
    ``PromptBuildRequestFactory.create``, which enforces every
    invariant (positive project id, the request's own project id
    matching ``context_package.project_id``) at construction time.

    ``objective`` defaults to ``DIRECT_ANSWER`` so a request built before
    Milestone 23B.2 keeps exactly the meaning it already had.
    """

    project_id: int
    context_package: ContextPackage
    configuration: PromptBuilderConfiguration
    objective: PromptObjective = PromptObjective.DIRECT_ANSWER


@dataclass(frozen=True, slots=True)
class PromptAssemblyResult:
    """The Composition stage's full output: every section, in
    canonical order, plus the four sections and the reference tuple
    ``PromptPackage`` itself exposes by name - computed once, here, and
    threaded through unchanged."""

    sections: tuple[PromptSection, ...]
    system_context: PromptSection
    engineering_context: PromptSection
    retrieved_knowledge: PromptSection
    expected_output: PromptSection
    constraints: tuple[PromptConstraint, ...]
    instructions: tuple[PromptInstruction, ...]
    references: tuple[PromptEvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class PromptVersion:
    """The full version identity of one ``PromptPackage`` - echoed again,
    for convenient single-place inspection, inside ``PromptMetadata``
    (the same "versioned field plus a metadata echo" pattern
    ``BudgetPolicy.version``/``ContextMetadata.budget_policy_version``
    already established in Context Builder)."""

    prompt_builder_version: str
    composition_policy_version: str
    context_assembly_version: str | None
    package_version: str


@dataclass(frozen=True, slots=True)
class PromptMetadata:
    prompt_builder_version: str
    composition_policy_version: str
    context_assembly_version: str | None
    assembled_at: datetime
    package_version: str


@dataclass(frozen=True, slots=True)
class PromptStatistics:
    section_count: int
    estimated_total_tokens: int
    enabled_section_count: int
    disabled_section_count: int
    knowledge_item_count: int
    reference_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptValidationResult:
    """
    The Validation stage's output: whether the just-assembled
    ``PromptPackage`` satisfies every structural invariant Milestone 15
    requires (required sections exist, ordering is canonical,
    constraints are present, metadata is complete, statistics are
    internally consistent). Never causes assembly to raise - Prompt
    Builder always produces a structurally valid package by
    construction; this result is an inspectable, testable proof of
    that, not a gate a caller must pass.
    """

    valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptPackage:
    """
    The bounded, deterministic, provider-independent artifact Prompt
    Builder produces - the official contract every future LLM adapter
    consumes. Carries no provider-specific payload, no serialized
    message list, and no free-form concatenated prompt string; only
    strongly typed, inspectable sections and their supporting objects.

    ``objective`` records which fixed instruction/expected-output set
    produced this package. Together with
    ``version.composition_policy_version`` it is the full reproduction
    key: the same context package, objective and policy version always
    yield the same package. It defaults to ``DIRECT_ANSWER`` so every
    package built before Milestone 23B.2 keeps exactly the meaning it
    already had.
    """

    project_id: int
    system_context: PromptSection
    engineering_context: PromptSection
    retrieved_knowledge: PromptSection
    constraints: tuple[PromptConstraint, ...]
    instructions: tuple[PromptInstruction, ...]
    expected_output: PromptSection
    references: tuple[PromptEvidenceReference, ...]
    sections: tuple[PromptSection, ...]
    metadata: PromptMetadata
    statistics: PromptStatistics
    version: PromptVersion
    objective: PromptObjective = PromptObjective.DIRECT_ANSWER


@dataclass(frozen=True, slots=True)
class PromptBuildResult:
    """The full envelope one Prompt Builder execution returns - the
    request's own project id and configuration, paired with the
    resulting ``PromptPackage`` and its self-validation result."""

    project_id: int
    configuration: PromptBuilderConfiguration
    package: PromptPackage
    validation: PromptValidationResult
