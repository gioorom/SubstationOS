# Engineering Response

**Status:** As-built reference, Milestone 18 (Engineering Response
Foundation). Describes the `engineering_response` bounded context as
implemented - for the decision record (why this is a genuine domain
bounded context despite consuming an application-layer artifact, why
uncertainty is not confidence, why evidence preservation is mandatory,
why warnings are structured), see
[ADR-0015](adr/0015-engineering-response-foundation.md). For where this
context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md),
[llm_invocation_runtime.md](llm_invocation_runtime.md), and
[prompt_builder.md](prompt_builder.md).

## Pipeline

```
ContextPackage + PromptPackage + LLMResponseEnvelope
        |
   Translation           (app/services/engineering_response_service.py -
        |                 the ONLY file allowed to import both
        |                 LLMResponseEnvelope and this domain)
        |
   EngineeringResponseSourceEnvelope   (domain-owned restatement)
        |
   Composition            (engineering_response_composition.py - pure, no I/O)
        |
   Statistics              (engineering_response_statistics.py)
        |
   Metadata/Versioning     (engineering_response_metadata.py)
        |
   Validation              (engineering_response_validation.py)
   EngineeringResponseBuilderResult
```

`app/services/engineering_response_service.py` translates a real
`LLMResponseEnvelope` into `EngineeringResponseSourceEnvelope`, then
delegates to the pure domain pipeline
(`engineering_response_assembler.assemble_engineering_response`);
nothing in `app/domain/engineering_response/**` performs I/O, calls an
AI provider, or imports anything under `app/application/**`.

## The Dependency Rule boundary (read this first)

`LLMResponseEnvelope` is defined in
`app/application/models/llm_invocation.py` - an application-layer type,
not a domain type. CLAUDE.md's Dependency Rule forbids any
`app/domain/**` module from importing it. Engineering Response is
nonetheless a genuine domain bounded context (this milestone's own
instruction - it models engineering communication, not a request/response
transport detail). The two requirements are reconciled by **restatement,
not exception**:

- `app/domain/engineering_response/engineering_response_models.py`
  defines its own `EngineeringResponseSourceEnvelope`/
  `EngineeringResponseSourceContent`/`EngineeringSourceFinishReason` -
  independent dataclasses/enums whose value sets match
  `LLMResponseEnvelope`'s own by convention, never by import.
- `app/services/engineering_response_service.py` is the **one** seam
  in the codebase allowed to import both `LLMResponseEnvelope`
  (application) and `app.domain.engineering_response` (domain),
  performing the translation exactly once before ever calling the pure
  domain assembler.
- `tests/architecture/test_bounded_context_dependencies.py`'s
  `test_engineering_response_domain_never_imports_the_application_layer`
  (plus the broader `test_engineering_response_domain_does_not_import_forbidden_modules`,
  which also forbids `app.application`, provider SDKs, and the LLM
  Invocation Runtime module) enforces this as a hard architecture test,
  not merely a documented convention.

Only a **successful** invocation ever reaches this builder:
`LLMInvocationResult`'s own invariant (Milestone 17) guarantees an
`envelope` exists only when the overall invocation status is
`SUCCEEDED` - so `EngineeringResponseSourceEnvelope` carries no
`status` field at all. Presenting a failed or cancelled invocation to
an engineer is out of this milestone's scope.

## Domain model

`app/domain/engineering_response/engineering_response_models.py`:
`EngineeringResponse`, `EngineeringResponseStatus`
(`COMPLETE`/`PARTIAL`/`UNSUPPORTED`/`EMPTY` - an engineering-native
completeness assessment, never a copy of `LLMInvocationStatus`),
`EngineeringResponseSection`/`EngineeringSectionType` (nine fixed
types), `EngineeringEvidenceReference`, `EngineeringWarning`/
`EngineeringWarningCategory`, `EngineeringUncertainty`/
`EngineeringUncertaintyLevel`, `EngineeringResponsePolicy`,
`EngineeringResponseMetadata`/`EngineeringResponseVersion`,
`EngineeringResponseStatistics`, `EngineeringResponseValidationResult`,
`EngineeringResponseBuilderResult`, `EngineeringResponseBuildRequest`,
and the source-restatement types above. All frozen, slotted
dataclasses.

## Sections

Nine `EngineeringSectionType`s, always present in this fixed, canonical
order (`ENGINEERING_RESPONSE_SECTION_ORDER` in
`engineering_response_composition.py`):

| Order | Section | Populated from | Always enabled? |
|---:|---|---|---|
| 0 | `SUMMARY` | Never - see below | No, always disabled |
| 1 | `DIRECT_ANSWER` | Every supported-text content block, verbatim | Only if the provider returned usable text |
| 2 | `TECHNICAL_EXPLANATION` | Never - see below | No, always disabled |
| 3 | `ASSUMPTIONS` | Never - see below | No, always disabled |
| 4 | `WARNINGS` | One line per structured `EngineeringWarning` | Only if any warning fired |
| 5 | `LIMITATIONS` | Structural signals (truncation, unsupported content, incomplete coverage) | Only if any limitation applies |
| 6 | `NEXT_ACTIONS` | Never - see below | No, always disabled |
| 7 | `REFERENCES` | `PromptPackage.references`, restated verbatim | Only if any reference exists |
| 8 | `UNKNOWN` | One line per unsupported provider content block | Only if any unsupported block exists |

**Why `SUMMARY`/`TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`NEXT_ACTIONS`
are always empty:** this builder performs no AI usage and no semantic
parsing of the provider's own returned text. Splitting free text into
"this sentence is a summary" versus "this sentence is an assumption"
without genuine language understanding would itself be inventing
engineering structure that was never actually there - the same
"never invent engineering facts" rule this milestone states, applied to
structure rather than only to content. These four section types exist,
in their fixed canonical position, so a future capability that *can*
honestly populate them (e.g. a provider emitting genuinely structured,
machine-parseable output) can do so without changing this shape.

## Status derivation

`EngineeringResponseStatus` is derived entirely from structural
signals, never from reading the response's own prose:

- **`EMPTY`** - the envelope carried zero content blocks at all.
- **`UNSUPPORTED`** - at least one content block exists, but none is
  supported text (e.g. only tool-use/thinking blocks).
- **`PARTIAL`** - usable text exists, but either an unsupported block
  is also present, or the finish reason indicates truncation
  (`MAXIMUM_OUTPUT_REACHED`/`STOP_SEQUENCE`).
- **`COMPLETE`** - usable text exists, no unsupported content, and the
  finish reason indicates genuine completion.

## Warnings

`EngineeringWarningCategory`: `INSUFFICIENT_EVIDENCE` (zero candidates
retrieved), `PARTIAL_CONTEXT` (retrieved but selection completeness
`< 1.0`), `PROVIDER_WARNING` (one per structural warning the LLM
Invocation Runtime itself raised, echoed verbatim - never
re-interpreted), `UNKNOWN_CONTENT` (any unsupported content block
present), `LIMITED_RESPONSE` (a truncating finish reason), and
`UNSUPPORTED_RESPONSE` (status is `UNSUPPORTED` - no usable text at
all). Every warning is a structured `(category, message)` pair, never a
free-text string standing alone.

`AMBIGUOUS_KNOWLEDGE` was added in EPIC 31.3 (a governed question had
more than one governed answer) and `CONFLICTING_KNOWLEDGE` in EPIC 32.1.

`CONFLICTING_KNOWLEDGE` is not the model being unsure and not the
evidence being thin: it is a conflict **inside reviewed, approved
knowledge**, found by a deterministic rule. It cannot be resolved by
retrieving better or asking the model again - somebody has to fix the
source.

### Derived reasoning (EPIC 32.1, extended by EPIC 32.2)

`EngineeringResponse.derived_reasoning` carries a
`DerivedReasoningAssessment` when the workflow ran a reasoning step, and
`None` otherwise - a different and honest state from a `CONSISTENT`
nobody derived.

**Two families, one field, discriminated by `rule_family`.** A
quantity-consistency conclusion carries `ReasoningOutcome`; a structural
relationship conclusion (EPIC 32.2) carries `StructuralReasoningOutcome`
plus a typed `SharedStructuralLocationReport` naming the derived
relationship, the shared governed location **identity**, and the ordered
governed path the conclusion rests on. A consumer switches on the family
and gets a static type - never a dictionary, and never prose it has to
parse.

The structural family has no negative outcome. There is no
`NOT_SHARED`, because the governed graph is partial and location identity
is document-scoped, so "we cannot establish that they share a location"
is never "they are in different places". The
`INSUFFICIENT_KNOWLEDGE` warning says so in words, because a reader given
only the word *insufficient* will conclude separation.
`CONFLICTING_KNOWLEDGE` is never raised for a structural conclusion - two
assets in different governed locations are not statements that
contradict each other.

It is a **field of its own, deliberately not an evidence reference**. To
every downstream consumer, an entry in `references` reads as one more
governed fact supporting the answer; a conclusion is a statement *about*
those facts, not one of them (AF-REASON-001).

Three of the four outcomes also raise a warning, in three separate
categories, because collapsing them would erase exactly the distinction
the four-valued outcome exists to preserve:

| Outcome | Warning |
|---|---|
| `INCONSISTENT` | `CONFLICTING_KNOWLEDGE` |
| `AMBIGUOUS` | `AMBIGUOUS_KNOWLEDGE` |
| `INSUFFICIENT_KNOWLEDGE` | `INSUFFICIENT_EVIDENCE` |
| `CONSISTENT` | *(none)* |

`engineering_response_reasoning.py` does **no reasoning**: it reads a
result a versioned rule already produced and restates it in this
context's vocabulary. See
[engineering_reasoning.md](engineering_reasoning.md).

## Uncertainty

`EngineeringUncertainty` is **not model confidence** - no provider
reports, and this builder never estimates, how "sure" a model is of its
own text. It represents how much this response explicitly depends on
assumptions or missing evidence, derived from measurable facts already
available before this builder ever runs:

| Signal | Level |
|---|---|
| Status is `EMPTY` | `UNKNOWN` (no basis to judge at all) |
| Zero candidates retrieved | `HIGH` |
| Selection completeness `< 0.5` | `HIGH` |
| Selection completeness `< 1.0` | `MEDIUM` |
| Status is `UNSUPPORTED` | `HIGH` |
| Status is `PARTIAL` | `MEDIUM` |
| None of the above | `LOW` (at least one declaration always exists) |

`EngineeringResponse.overall_uncertainty` is the worst (highest-ranked)
level among every declaration
(`engineering_response_policy.py`'s `overall_uncertainty_from`, rank
order `LOW < MEDIUM < UNKNOWN < HIGH`, fixed and version-stamped like
every other policy table in this codebase).

## Evidence preservation

`EngineeringResponse.references` restates `PromptPackage.references`
(`PromptEvidenceReference`) verbatim as `EngineeringEvidenceReference` -
candidate id, graph node ids, graph relationship ids, unchanged.
`EngineeringResponseMetadata`/`EngineeringResponseVersion` echo
`prompt_package_version`/`context_builder_version`/
`prompt_builder_version`/`request_preparation_policy_version`/
`runtime_version` - the full version chain from Context Builder through
the LLM Invocation Runtime is inspectable from the final response
alone, no provenance lost at any stage.

## Validation

`engineering_response_validation.py`'s `validate_response` (wrapped by
the milestone-named `EngineeringResponseValidator` class) proves,
after building, that an `EngineeringResponse` satisfies every
structural invariant: canonical section order, no duplicate sections,
complete metadata, version fields consistent with metadata, and every
statistic (reference/warning/uncertainty/section counts, enabled/
disabled counts, character count) internally consistent with the
assembled response. At least one uncertainty declaration is required.
Returned as `EngineeringResponseBuilderResult.validation` - an
inspectable, testable proof, never a gate; building always produces a
structurally valid response by construction.

## Statistics

`EngineeringResponseStatistics`: `section_count`, `enabled_section_count`,
`disabled_section_count`, `warning_count`, `uncertainty_count`,
`reference_count`, `character_count` (summed across every section's
body lines). Deliberately no token count - that remains Prompt
Builder's own approximate, provider-independent responsibility one
layer upstream.

## API

```
POST /projects/{project_id}/engineering-response/build
```

`project_id` in the path is authoritative; the request body's
`context_package`/`prompt_package`/`llm_response_envelope` fields are
exactly the objects the prior `/context-builder/build`,
`/prompt-builder/build`, and `/llm/invoke` calls returned. **Performs
no AI invocation of its own** - it never calls Context Builder, Prompt
Builder, or the LLM Invocation Runtime itself. Response: an
`EngineeringResponseBuilderResultRead` (the request's own project id,
the resulting `EngineeringResponseRead`, and the self-validation
result).

### Errors

Every `EngineeringResponseError` subtype (invalid project id, a project
id that disagrees with the supplied `ContextPackage` or `PromptPackage`)
maps to `422 Unprocessable Entity`.

## Determinism

Identical `(ContextPackage, PromptPackage, LLMResponseEnvelope)` inputs
always produce an identical `EngineeringResponse`, proven by dedicated
tests (`tests/domain/test_engineering_response_assembler.py::test_identical_inputs_produce_an_identical_response`,
and the API-level `tests/api/test_engineering_response_api.py::test_determinism_across_repeated_calls`).
`now` is always supplied by the caller, never read from the wall clock
inside the domain layer (CLAUDE.md SS16, Reproducibility).

## Performance

Building is O(n) in the number of content blocks, references, and
warnings on the input - a small, constant number of linear passes over
already-materialized data, independent of graph size (Engineering
Response performs no database query and no AI invocation of its own).
See [performance_baseline.md](performance_baseline.md) for the recorded
`engineering_response_build` benchmark operation.

## What this milestone deliberately does not do

- No conversation history, chat sessions, or assistant memory.
- No autonomous agents or tool use.
- No drawing generation or automatic engineering approval.
- No persistence of `EngineeringResponse` objects - every artifact is
  cheaply reconstructable from its own inputs.
- No frontend chat UI.
- No semantic segmentation of the provider's prose into `SUMMARY`/
  `TECHNICAL_EXPLANATION`/`ASSUMPTIONS`/`NEXT_ACTIONS` - see the
  Sections table above.

These are Milestone 19's (Engineering Conversation Foundation) and
later EPIC 5 milestones' concern, not this one's.
