# ADR-0015: Engineering Response Foundation

## Status

Accepted.

## Context

By Milestone 17 (LLM Invocation Runtime, ADR-0014), a real Anthropic
call produces an `LLMResponseEnvelope` - a provider-neutral, but still
fundamentally *provider-shaped*, artifact: content blocks, a finish
reason, usage counters, an attempt history. Nothing yet exists that
represents "what an engineer should understand from this response" -
every future consumer (a conversational assistant, a review workflow,
an audit report) would otherwise have to interpret `LLMResponseEnvelope`
directly, coupling every future capability to the exact shape the LLM
Invocation Runtime happens to produce today.

This milestone is explicitly **not** the conversational assistant
(that is the still-future AI Assistant, EPIC 5's own later milestone).
It is the layer in between: a deterministic transform from
`LLMResponseEnvelope` into `EngineeringResponse`, the first
domain-oriented representation of an AI answer, and the object every
future AI-facing capability will consume instead of the envelope
itself.

A genuine design tension had to be resolved before writing any code.
This milestone's own brief instructs that `EngineeringResponse` "belongs
to the engineering domain" and lives under `app/domain/engineering_response/`
- unlike the LLM Runtime, which CLAUDE.md and ADR-0013/0014 deliberately
kept *out* of `app/domain/**`. But `LLMResponseEnvelope` itself is
defined in `app/application/models/llm_invocation.py` - an
application-layer type. CLAUDE.md's Dependency Rule states plainly that
the domain layer "may import: only the standard library and other
domain modules." Taken literally, "Engineering Response is a domain
context that consumes `LLMResponseEnvelope`" is a contradiction: no
domain module may import an application-layer type, ever, regardless of
how reasonable the consumption sounds.

## Decision

### 1. Engineering Response is a genuine domain bounded context

`app/domain/engineering_response/**` follows the exact same reference
pattern every other domain context in this pipeline follows (models,
policy, composition, statistics, metadata, validation, assembler,
factory, exceptions - the same file-per-concept shape Prompt Builder
and Context Builder already established). This is domain knowledge:
what an engineer should understand from a response - status, sections,
warnings, uncertainty - is a permanent, engineering-facing concept, not
an incidental detail of how one particular provider happened to shape
its output. It belongs in `app/domain/**` for the same reason
`ContextPackage` and `PromptPackage` do.

### 2. The Dependency Rule is resolved by restatement, not by exception

`app/domain/engineering_response/**` **never** imports
`app.application.**`. Instead, it defines its own domain-owned
restatement of exactly the fields it needs -
`EngineeringResponseSourceEnvelope`/`EngineeringResponseSourceContent`/
`EngineeringSourceFinishReason` (`engineering_response_models.py`) -
independent dataclasses and enums whose value sets happen to match
`LLMResponseEnvelope`'s own by convention, never by import. A single
new file, `app/services/engineering_response_service.py`, is the
**one** seam in the entire codebase allowed to import both
`LLMResponseEnvelope` (application) and `app.domain.engineering_response`
(domain), translating the former into the latter's restatement before
ever calling the pure domain assembler. This is not a special case
carved out of the Dependency Rule - it is the same rule, applied
consistently: `app/services/**` (CLAUDE.md's "Application / Services"
layer) is documented to depend on "Domain + infrastructure contracts,"
and `app/application/**`'s own capabilities are exactly that kind of
contract from this layer's point of view. The domain itself still
depends on nothing but other domain modules, exactly as CLAUDE.md
requires - verified by a dedicated architecture test
(`test_engineering_response_domain_never_imports_the_application_layer`),
not merely asserted in this document.

### 3. Only a successful invocation ever reaches this builder

`LLMInvocationResult`'s own invariant (ADR-0014, Milestone 17) already
guarantees an `envelope` exists only when the invocation's overall
status is `SUCCEEDED`. `EngineeringResponseSourceEnvelope` therefore
carries no `status` field at all - it would always hold the same single
value, carrying no information. Presenting a *failed* or *cancelled*
invocation to an engineer is deliberately out of this milestone's
scope; it is the future conversational layer's responsibility to decide
how a `terminal_error` becomes something a user sees.

### 4. Sections are typed and fixed-shape, but not all are populated from prose

`EngineeringResponse` carries nine fixed `EngineeringSectionType`
sections, in canonical order, always present regardless of input - the
same "always the full fixed shape, disabled and empty when there is
nothing to contribute" convention Prompt Builder established for
`PromptPackage.sections`. Critically, this milestone's own instruction
is "no AI usage... never invent engineering facts," and this builder
takes that literally: `SUMMARY`, `TECHNICAL_EXPLANATION`, `ASSUMPTIONS`,
and `NEXT_ACTIONS` are **always** constructed disabled and empty,
because this builder has no honest way to split a provider's raw prose
into "this sentence is a summary" versus "this sentence is an
assumption" without actually reading and interpreting that prose - and
doing so would be inventing engineering *structure* that was never
actually there, exactly the kind of fabrication the milestone forbids.
`DIRECT_ANSWER` (the provider's own returned text, verbatim),
`WARNINGS`, `LIMITATIONS`, `REFERENCES`, and `UNKNOWN` are populated
entirely from *structural* signals (content-block types, finish reason,
coverage ratios, retrieved-candidate counts) - never by reading or
interpreting the model's own words.

### 5. Uncertainty is a structural judgment, never model confidence

`EngineeringUncertainty` declarations (`LOW`/`MEDIUM`/`HIGH`/`UNKNOWN`)
are derived exclusively from measurable facts already available before
this builder ever runs: how much of the retrieved knowledge context was
actually selected (`ContextPackage.coverage.overall_completeness`),
whether any candidates were retrieved at all, and whether the response
itself is complete, partial, or contains unsupported content. No
provider ever reports, and this builder never estimates, how "sure" a
model is of its own text - that number does not exist and inventing one
would violate the same "never fabricate certainty" principle Context
Builder's own `CoverageReport` already established one layer upstream.
`UNKNOWN` is a distinct, honest state (this builder had no basis to
judge at all - e.g. no response content exists to assess), never a
default filled in when a real judgment could have been made.

### 6. Warnings are structured data, never a free-text string standing alone

Every `EngineeringWarning` carries a closed `EngineeringWarningCategory`
plus a message - `INSUFFICIENT_EVIDENCE`, `PARTIAL_CONTEXT`,
`PROVIDER_WARNING` (an echo of the runtime's own structural warnings,
never re-derived), `UNKNOWN_CONTENT`, `LIMITED_RESPONSE`, and
`UNSUPPORTED_RESPONSE` - so a future consumer can act on the category
programmatically, never by parsing prose.

## Consequences

**Easier:**

- Every future AI-facing capability (the conversational assistant,
  audit tooling, a review workflow) consumes one stable, engineering-
  native contract - `EngineeringResponse` - never a provider-shaped
  envelope. Swapping the underlying provider, or even adding a second
  one, changes nothing above this layer, the same replaceability
  guarantee ADR-0013 established for request preparation.
- The translation seam is exactly one file
  (`engineering_response_service.py`), making "does this respect the
  Dependency Rule" a single, small, reviewable surface rather than a
  distributed concern.
- `EngineeringResponse`'s full attempt/warning/uncertainty history is
  inspectable after the fact, the same "why did this happen" auditability
  ADR-0014 established for invocation attempts.

**Harder / deferred:**

- `SUMMARY`/`TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`NEXT_ACTIONS`
  currently carry no content from any real invocation, since populating
  them honestly requires either genuine NLP/semantic segmentation (out
  of scope - no AI usage in this builder) or a future provider
  capability that emits genuinely structured, machine-parseable output.
  This is a known, documented limitation, not an oversight - see
  `engineering_response.md`'s own note.
- Failed and cancelled invocations produce no `EngineeringResponse` at
  all this milestone; a future milestone must decide how
  `LLMInvocationResult.terminal_error` is ever shown to an engineer.
- This is the first bounded context in the pipeline whose primary input
  originates one layer *below* `app/domain/**` (the application layer)
  rather than from an upstream domain context - a genuinely new shape
  of dependency this codebase had not needed to resolve before. Any
  future domain context with a similar need should follow the same
  "restate, translate once in the service layer" pattern established
  here, not invent a new one.

## Rejected Alternatives

- **Let `app/domain/engineering_response/**` import `LLMResponseEnvelope`
  directly.** Rejected outright: it would be a direct, literal violation
  of CLAUDE.md's Dependency Rule ("domain depends on nothing" beyond
  other domain modules) - the exact rule this manual states wins over
  any milestone brief's convenience. No amount of "it's just one type"
  justifies it once it is permitted even once.
- **Keep Engineering Response in `app/application/**` alongside the LLM
  Runtime, rather than in `app/domain/**`.** Rejected per this
  milestone's own explicit instruction, and on the merits: what an
  engineer should understand from a response (status, structured
  warnings, uncertainty) is permanent engineering-domain knowledge, not
  an application/infrastructure capability like retry policy or
  timeout handling - it deserves the full domain reference pattern
  (factory, validator, versioned policy), not the lighter-weight
  service-module shape Milestones 16-17 used.
- **Attempt semantic segmentation of the provider's prose into
  SUMMARY/TECHNICAL_EXPLANATION/ASSUMPTIONS/NEXT_ACTIONS using simple
  heuristics (e.g. splitting on paragraph breaks or keyword markers).**
  Rejected: any such heuristic would be guessing at structure the
  provider's own free text does not actually declare, indistinguishable
  in practice from inventing engineering facts - exactly what this
  milestone's own "never invent engineering facts" rule forbids applied
  to structure, not only content.
- **Report a single overall confidence score instead of structured
  uncertainty declarations.** Rejected: a single number invites
  treating it as the model's own self-assessed confidence (which does
  not exist and cannot be honestly computed), and collapses multiple,
  independently meaningful concerns (missing evidence vs. an incomplete
  response) into one figure a consumer cannot act on distinctly.
- **Persist `EngineeringResponse` objects.** Rejected, for the same
  reason ADR-0011/0012/0013/0014 rejected persisting their own
  artifacts: no requirement demonstrated a need for it this milestone,
  and every artifact here is cheaply reconstructable from its own
  inputs - persisting it would be a second, potentially stale copy of
  derived data with no clear owner.
