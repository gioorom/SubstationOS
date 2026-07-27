# Prompt Builder

**Status:** As-built reference, Milestone 15 (Prompt Builder
Foundation). Describes the `prompt_builder` bounded context as
implemented - for the decision record (why a dedicated composition
layer, why provider serialization is excluded, why a future LLM
Provider Abstraction Layer must not duplicate this logic), see
[ADR-0012](adr/0012-prompt-builder-foundation.md). For where this
context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md) and
[context_builder.md](context_builder.md).

## Pipeline

```
ContextPackage
        |
   Composition           (prompt_composition.py - pure, no I/O)
        |
   Statistics             (prompt_statistics.py)
        |
   Metadata/Versioning     (prompt_metadata.py)
        |
   Validation              (prompt_validation.py)
   PromptBuildResult
```

`app/services/prompt_builder_service.py` validates the request through
`PromptBuildRequestFactory` and delegates assembly to
`app/domain/prompt_builder/prompt_package_assembler.py`; nothing in
`app/domain/prompt_builder/**` performs I/O, calls Graph Query,
Structured Retrieval, Context Builder, or an AI provider.

## Input

Prompt Builder's entire input is Context Builder's own `ContextPackage`
(`app.domain.context_builder.context_builder_models`), consumed as a
shared, stable artifact the same way Context Builder itself consumes
Structured Retrieval's `KnowledgeCandidateCollection`. Prompt Builder
never calls Context Builder - a caller assembles a context package
first, then passes it to `POST /projects/{project_id}/prompt-builder/build`
directly.

## Configuration

A `PromptBuildRequest` (built exclusively by
`PromptBuildRequestFactory.create`, which enforces every invariant
below at construction time) always has:

- `project_id` - mandatory, positive, and must match
  `context_package.project_id` (`ProjectIdMismatchError` otherwise -
  the path is authoritative, but a body naming a different project is
  a real inconsistency, never silently ignored).
- `context_package` - the input `ContextPackage`. An empty package
  (zero selected candidates, zero warnings) is valid, not an error - it
  produces a valid `PromptPackage` with the knowledge-dependent
  sections disabled.
- `configuration` - a `PromptBuilderConfiguration` bundling the
  `PromptCompositionPolicy` version and the Prompt Builder version
  itself.

## Sections

Nine `PromptSectionType`s, always present in this fixed, canonical
order (`PROMPT_SECTION_ORDER` in `prompt_composition.py`):

| Order | Section | Content | Always enabled? |
|---:|---|---|---|
| 0 | `SYSTEM_CONTEXT` | Fixed, versioned framing text | Yes |
| 1 | `ENGINEERING_CONTEXT` | Project id, retrieved/selected counts, coverage | Yes |
| 2 | `SELECTED_KNOWLEDGE` | One deterministically formatted line per selected candidate | Only if candidates were selected |
| 3 | `EVIDENCE_REFERENCES` | One citation line per selected candidate's provenance | Only if candidates were selected |
| 4 | `CONSTRAINTS` | The five fixed `PromptConstraint` descriptions | Yes |
| 5 | `FORMATTING_RULES` | The three fixed `PromptInstruction` descriptions | Yes |
| 6 | `EXPECTED_OUTPUT` | Fixed, versioned output-shape guidance | Yes |
| 7 | `WARNINGS` | One line per `ContextPackage.warnings` entry | Only if Context Builder reported warnings |
| 8 | `METADATA` | Context assembly timestamp/version echo | Yes |

Each `PromptSection.content` is a tuple of discrete lines built by
exactly one small, named, pure function - never a free-form
concatenated string. A section with nothing to contribute is still
constructed, in its fixed position, with empty content and
`enabled=False` - `PromptPackage.sections` always has this same
nine-section shape regardless of input.

## Composition

`SELECTED_KNOWLEDGE` and `EVIDENCE_REFERENCES` are built directly from
`ContextPackage.selected_candidates`, preserving that tuple's own
order (already deterministic, per Context Builder's own Selection
stage). `CONSTRAINTS`/`FORMATTING_RULES` render the fixed policy lists
from `composition_policy.py`, unconditionally, regardless of package
content. `WARNINGS` renders `ContextPackage.warnings` verbatim
(category + message); `METADATA` echoes
`ContextPackage.metadata.assembled_at`/`context_builder_version`/
`retrieval_policy_version`.

## Constraints and Instructions

Fixed, versioned, and always present (`composition_policy.py`,
`COMPOSITION_POLICY_VERSION`):

**Constraints** (behavioral - govern truthfulness):
1. `use_only_supplied_evidence`
2. `do_not_invent_facts`
3. `report_uncertainty`
4. `preserve_engineering_terminology`
5. `cite_supporting_evidence`

**Instructions** (formatting - govern output structure, never
truthfulness):
1. `structure_the_answer_with_clear_sections`
2. `reference_evidence_by_candidate_id`
3. `state_explicitly_when_no_supporting_evidence_exists`

Never derived from `ContextPackage` content; changing either list
requires a documented rationale and a `COMPOSITION_POLICY_VERSION`
bump.

## Token Estimation

`token_estimation.py`'s `estimate_tokens` uses a documented,
deliberately approximate, provider-independent heuristic - roughly 4
characters per token, a widely used rough approximation for English
text. **Never a real tokenizer**: every real tokenizer (`tiktoken` for
OpenAI, Anthropic's own tokenizer, ...) is provider-specific, and
depending on one would violate this bounded context's "no provider
SDK" boundary. Treat `PromptStatistics.estimated_total_tokens` as
approximate headroom, never an exact provider-specific count.

## Statistics

`PromptStatistics` summarizes the already-composed sections:
`section_count` (always 9), `estimated_total_tokens`,
`enabled_section_count`/`disabled_section_count`, `knowledge_item_count`
(= `len(ContextPackage.selected_candidates)`), `reference_count`, and
`warnings` (a diagnostic echo of `ContextPackage.warnings`, distinct
from the `WARNINGS` section's own rendered content).

## Metadata and Versioning

`PromptMetadata` carries `prompt_builder_version`,
`composition_policy_version`, `context_builder_version` (echoed from
the input `ContextPackage`, "when available"), `assembled_at` (supplied
by the caller as `now`, never read from the wall clock inside the
domain layer), and `package_version`. `PromptVersion` echoes the same
four version fields (minus the timestamp) at the top level, the same
"versioned field plus a metadata echo" pattern
`BudgetPolicy.version`/`ContextMetadata.budget_policy_version` already
established in Context Builder. Packages produced from identical
inputs and identical policies are identical (aside from
`metadata.assembled_at`, which legitimately varies with `now`).

## Validation

`prompt_validation.py`'s `validate_package` proves, after assembly,
that a `PromptPackage` satisfies every structural invariant this
milestone requires: required sections exist in canonical order,
constraints and instructions are non-empty, metadata is complete, and
statistics are internally consistent with the assembled sections.
Returned as `PromptBuildResult.validation` - an inspectable,
testable proof, never a gate; Prompt Builder always produces a
structurally valid package by construction and never raises over its
own output.

## API

```
POST /projects/{project_id}/prompt-builder/build
```

`project_id` in the path is authoritative; the request body's
`context_package` field is exactly the `package` object a prior
`/context-builder/build` call returned. Response: a
`PromptBuildResultRead` (the request's own configuration, the resulting
`PromptPackageRead`, and the self-validation result).

### Example

```http
POST /projects/42/prompt-builder/build
Content-Type: application/json

{
  "context_package": { "project_id": 42, "retrieval_summary": { ... }, "selected_candidates": [ ... ], ... }
}
```

### Errors

Every `PromptBuilderError` subtype (invalid project id, a project id
that disagrees with the supplied `ContextPackage`) maps to
`422 Unprocessable Entity`.

## Performance

Assembly is O(n) in the size of the input `ContextPackage` (its
selected candidates and warnings) - Composition is a small, constant
number of linear passes over already-materialized results; Statistics,
Metadata, and Validation are each O(1) or O(n) over the fixed, small
set of nine sections. Never a second retrieval, never a database
query - Prompt Builder performs no I/O of its own. See
[performance_baseline.md](performance_baseline.md) for recorded numbers
(`prompt_builder_composition` operation).
