# ADR-0012: Prompt Builder Foundation

## Status

Accepted.

## Context

By Milestone 14 (Context Builder Foundation, ADR-0011), the governed
knowledge pipeline can turn a ranked `KnowledgeCandidateCollection`
into a bounded, provenance-aware, budget-enforced `ContextPackage` -
deterministic, structured, and explainable. Nothing yet turns "I have a
bounded package of governed knowledge" into "I have something an LLM
adapter can actually send to a model" - the shape a future LLM Provider
Abstraction Layer will need before this project has ever called an AI
provider for anything but interpretation/presentation (ADR-0006).

Two temptations existed and were rejected before writing any code:

1. **Let a future LLM Provider Abstraction Layer consume `ContextPackage`
   directly and format it into each provider's request shape itself.**
   Rejected: every provider adapter would duplicate its own section
   ordering, constraint/instruction wording, and token-budgeting logic,
   with no shared, testable, explainable contract between "governed
   knowledge, bounded" and "text sent to a specific model." Formatting
   *which* provider's message structure is a serialization concern; the
   content and structure of the prompt itself is not, and conflating
   the two would put engineering decisions about prompt composition
   behind whichever adapter happened to be written first.
2. **Serialize directly to a specific provider's message format now**
   (e.g. an OpenAI `messages` array or an Anthropic `system`/`messages`
   split), since a real LLM call is the eventual goal. Rejected for the
   same reason ADR-0010 rejected embeddings before a deterministic
   retrieval baseline existed, and ADR-0011 rejected folding budget
   logic into Structured Retrieval: introducing a provider-specific
   shape before a provider-independent one exists means every future
   provider adapter re-derives the same composition decisions
   independently, with no shared baseline to validate against.

## Decision

### 1. Prompt Builder is a new bounded context, `app/domain/prompt_builder/**`, that owns composition - never serialization, never an LLM call

Prompt Builder's input is exactly one type: Context Builder's own
`ContextPackage` (`app.domain.context_builder.context_builder_models`),
consumed the same way Context Builder consumes Structured Retrieval's
`KnowledgeCandidateCollection` - as a shared, stable, already-built
artifact, never re-derived. Prompt Builder never calls Graph Query,
Structured Retrieval, or Context Builder, never queries a database,
never imports a provider SDK (`anthropic`, `openai`, `ollama`, Azure
OpenAI), and never formats a provider-specific message list - its own
architecture tests
(`tests/architecture/test_bounded_context_dependencies.py::test_prompt_builder_does_not_import_forbidden_modules`/
`test_prompt_builder_surface_has_no_ai_or_provider_dependency`) enforce
this the same way Milestones 13-14's tests enforce their own
boundaries. Its output, `PromptPackage`, is a structured, typed,
inspectable artifact - nine fixed-order `PromptSection`s, typed
`PromptConstraint`/`PromptInstruction` lists, typed
`PromptEvidenceReference`s - never a raw string, never a provider
payload.

### 2. Composition is section-by-section, deterministic, and never free-form string concatenation

Every `PromptSectionType` (`SYSTEM_CONTEXT`, `ENGINEERING_CONTEXT`,
`SELECTED_KNOWLEDGE`, `EVIDENCE_REFERENCES`, `CONSTRAINTS`,
`FORMATTING_RULES`, `EXPECTED_OUTPUT`, `WARNINGS`, `METADATA`) has
exactly one small, named, pure builder function
(`prompt_composition.py`), each producing a tuple of discrete lines -
never an ad hoc joined string. `PromptPackage.sections` always has this
same nine-section shape, in this same canonical order, regardless of
input: a section with nothing meaningful to contribute (e.g. no
candidates were selected, or Context Builder reported no warnings) is
still constructed, in its fixed position, with empty content and
`enabled=False`, rather than omitted - a consumer can always rely on
the same shape.

### 3. Constraints and instructions are a fixed, versioned policy - never derived from package content

`composition_policy.py`'s `CONSTRAINTS` (five fixed behavioral
guardrails: use only supplied evidence, do not invent facts, report
uncertainty, preserve engineering terminology, cite supporting
evidence) and `INSTRUCTIONS` (three fixed formatting rules, distinct
from constraints - formatting governs output structure, constraints
govern truthfulness) are always present, unconditionally, for every
`PromptPackage`, the same "fixed, documented policy table" convention
`scoring_policy.py` and `budget_policy.py` already established.
Changing either set requires a documented rationale and a
`COMPOSITION_POLICY_VERSION` bump, echoed in `PromptMetadata`/
`PromptVersion` so a caller can tell which policy produced a given
package.

### 4. Token estimation is a documented, deliberately approximate, provider-independent heuristic

`token_estimation.py`'s `~4 characters per token` estimate is a widely
used rough approximation for English text - never a real tokenizer.
Every real tokenizer (`tiktoken` for OpenAI, Anthropic's own
tokenizer, ...) is provider-specific; depending on one here would
violate this milestone's "no provider SDK" boundary before an LLM
Provider Abstraction Layer even exists to justify the dependency. The
estimate is explicitly documented as approximate, never presented as
precise.

### 5. Validation is a self-check, not a gate

`prompt_validation.py`'s `PromptValidationResult` proves, after
assembly, that a `PromptPackage` satisfies every structural invariant
this milestone requires (required sections exist in canonical order,
constraints and instructions are present, metadata is complete,
statistics are internally consistent with the assembled sections).
Prompt Builder always produces a structurally valid package by
construction - this is an inspectable, testable proof of that fact,
returned alongside the package in `PromptBuildResult`, never a
condition a caller must satisfy or an exception Prompt Builder might
raise over its own output.

### 6. LLM Provider Abstraction Layer, and every future provider adapter, are infrastructure - never Prompt Builder's own concern

```
Structured Retrieval   = ranked, explainable KnowledgeCandidates from structured criteria
Context Builder        = bounded, provenance-aware ContextPackage from ranked candidates
Prompt Builder          = deterministic, provider-independent PromptPackage from a ContextPackage
LLM Provider Abstraction Layer = (future) translates PromptPackage into a specific provider's request format
AI Assistant            = (future) consumer, not owner, of engineering truth
```

The next milestone (LLM Provider Abstraction Layer) is expected to
consume `PromptPackage` the same way Prompt Builder consumes
`ContextPackage`: one new responsibility (serializing a
provider-specific request), never re-deriving section content,
constraints, or token estimates this milestone already decided. A
provider adapter that reformats `PromptSection.content` into its own
wording, or invents its own constraints, would silently diverge from
the package a caller already inspected - exactly the duplicated,
inconsistent logic ADR-0011's own "Prompt Builder must not duplicate
this logic" principle warned against one layer earlier. This is also
why provider serialization belongs in `app/infrastructure/**`, per
CLAUDE.md's dependency rule, once it exists: an adapter around a
domain-owned port, never a hard dependency the domain carries.

## Consequences

**Easier:**
- Every future LLM Provider Abstraction Layer adapter (OpenAI,
  Anthropic, Ollama, Azure OpenAI, or any future provider) has one
  shared, tested, explainable `PromptPackage` contract to serialize,
  instead of hand-rolled composition logic duplicated per provider.
- A `PromptPackage` is independently inspectable - by a test, by an
  engineer auditing prompt content, or by a future frontend - without
  executing any retrieval, any assembly, or any AI call.
- Composition, constraints, and token estimates are all versioned;
  a regression or an intentional policy change is always attributable
  to a specific version bump, never a silent behavior change.

**Harder / deferred:**
- Prompt Builder cannot itself call Context Builder - a caller must
  assemble a `ContextPackage` first and pass it in explicitly. Solving
  that orchestration (e.g. a single endpoint that retrieves, assembles,
  and composes in one call) is out of this milestone's scope, the same
  deferral ADR-0011 already made for Structured Retrieval -> Context
  Builder.
- Token counts are estimates, not exact provider-specific counts. A
  caller relying on `PromptStatistics.estimated_total_tokens` for a
  hard provider limit must treat it as approximate headroom, not an
  exact budget - precise counting is squarely the LLM Provider
  Abstraction Layer's job once it exists (it can hold a real,
  provider-specific tokenizer; Prompt Builder must not).
- `PromptSection` content is English prose, fixed at composition time -
  no localization, no per-provider prompt-style variation (e.g. XML
  tags vs. markdown headers) exists yet. Both are legitimate future
  extensions once a real need is demonstrated, not designed
  speculatively here (CLAUDE.md SS12, YAGNI).

## Rejected Alternatives

- **Let a future LLM Provider Abstraction Layer consume `ContextPackage`
  directly, composing its own prompt per provider.** Rejected:
  duplicates composition logic per provider adapter, with no shared,
  testable contract and no consistent constraint/instruction wording
  across providers.
- **Serialize directly to a specific provider's message format as part
  of this milestone.** Rejected: commits to one provider's shape before
  a provider-independent baseline exists to validate every future
  adapter against - the same sequencing discipline ADR-0010 and
  ADR-0011 already established for their own layers.
- **Use a real tokenizer for token estimation.** Rejected: every real
  tokenizer is provider-specific; depending on one here would
  contradict this milestone's own "no provider SDK" requirement before
  an LLM Provider Abstraction Layer exists to justify the dependency.
- **Persist `PromptPackage`.** Rejected, for the same reason ADR-0011
  rejected persisting `ContextPackage`: no requirement demonstrated a
  need for it, and a package is cheaply recomputable from its own
  input (a `ContextPackage`) - persisting it would be a second,
  potentially stale copy of derived data with no clear owner.
- **Make `PromptValidationResult` a hard gate that raises on
  failure.** Rejected: Prompt Builder always produces a structurally
  valid package by construction (every section is built by the same
  fixed, tested composition functions); introducing an exception path
  for a condition that cannot occur under normal operation would be
  speculative error handling for a scenario this milestone's own tests
  prove does not happen (CLAUDE.md SS15, "do not add error handling for
  scenarios that can't happen").
