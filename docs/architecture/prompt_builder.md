# Prompt Builder

**Status:** As-built reference, Milestone 15 (Prompt Builder
Foundation), extended by Milestone 23B.2 (`PromptObjective`) and
Milestone 24.1 (the verification objective) and Milestone 24.2
(the comparison objective and the two knowledge sides).
Describes the `prompt_builder` bounded context as
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

`PromptSectionType`s, always present in this fixed, canonical order
(`PROMPT_SECTION_ORDER` in `prompt_composition.py`):

| Order | Section | Content | Always enabled? |
|---:|---|---|---|
| 0 | `SYSTEM_CONTEXT` | Fixed, versioned framing text | Yes |
| 1 | `ENGINEERING_CONTEXT` | Project id, retrieved/selected counts, coverage | Yes |
| 2 | `SELECTED_KNOWLEDGE` | One deterministically formatted line per selected candidate | Only if candidates were selected |
| 3 | `DERIVED_REASONING` | The deterministic conclusion, its rule and version, its diagnostic, and the governed facts behind it | Only if the workflow reasoned (EPIC 32.1) |
| 4 | `EVIDENCE_REFERENCES` | One citation line per selected candidate's provenance | Only if candidates were selected |
| 5 | `CONSTRAINTS` | The five fixed `PromptConstraint` descriptions | Yes |
| 6 | `FORMATTING_RULES` | The three fixed `PromptInstruction` descriptions | Yes |
| 7 | `EXPECTED_OUTPUT` | Fixed, versioned output-shape guidance | Yes |
| 8 | `WARNINGS` | One line per `ContextPackage.warnings` entry | Only if Context Builder reported warnings |
| 9 | `METADATA` | Context assembly timestamp/version echo | Yes |

`DERIVED_REASONING` sits immediately after `SELECTED_KNOWLEDGE` and
before `EVIDENCE_REFERENCES`, deliberately: the model reads the governed
facts, then what was concluded from them, then the citations. It travels
as a `CONTEXT` message rather than an instruction - the model is told
what was concluded, **not asked to conclude**. The section is disabled
for every workflow that does not reason, including comparison. See
[engineering_reasoning.md](engineering_reasoning.md).

Since EPIC 32.2 the section renders **two families**, each with its own
outcome wording. For a structural conclusion it names the derived
relationship in full - ``shares_structural_location_with``, never
shortened to anything a reader could take for connectivity - and the
shared governed location.

The `INSUFFICIENT_KNOWLEDGE` wording is load-bearing rather than
decorative. A model told only "insufficient" writes *"they are in
different places"*, because that is what the word suggests in ordinary
English; the platform cannot establish separation at all, so the section
tells the model explicitly that the finding is not that one and that it
must not report the assets as separate.

Each `PromptSection.content` is a tuple of discrete lines built by
exactly one small, named, pure function - never a free-form
concatenated string. A section with nothing to contribute is still
constructed, in its fixed position, with empty content and
`enabled=False` - `PromptPackage.sections` always has this same
shape regardless of input.

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

## Objective

`PromptObjective` (Milestone 23B.2) is the **only** thing a caller may
vary about a package's composition. It is deliberately *not* a
free-form prompt, a template, a persona, or a caller-supplied
instruction string: it selects between fixed, versioned instruction and
expected-output sets declared in `composition_policy.py`, so every
prompt this system can produce stays enumerable and reviewable.

| Objective | Asks for | Used by |
|---|---|---|
| `DIRECT_ANSWER` (default) | The question answered, as briefly as the evidence allows | `KNOWLEDGE_QUERY` workflow |
| `ENGINEERING_EXPLANATION` | The function, role and behaviour of the retrieved equipment, set out for an engineer | `ENGINEERING_EXPLANATION` workflow |
| `ENGINEERING_VERIFICATION` | A verdict on whether the project's evidence supports a stated claim, plus the evidence behind it | `ENGINEERING_VERIFICATION` workflow |
| `ENGINEERING_COMPARISON` | How a RIGHT subject differs from a LEFT one, judged only on the two supplied evidence groups | `ENGINEERING_COMPARISON` workflow |

The objective changes **exactly two sections** - `FORMATTING_RULES` and
`EXPECTED_OUTPUT` - for every objective except
`ENGINEERING_COMPARISON`, which is built from a two-sided context and is
described in [Comparison prompts](#comparison-prompts) below. Every other section is composed identically, from
the same `ContextPackage`, by the same functions. `DIRECT_ANSWER` is
byte-identical to what this context produced before the enum existed,
which is why omitting the objective is always safe.

`PromptPackage.objective` records which set produced a package;
together with `version.composition_policy_version` it is the full
reproduction key.

## Comparison prompts

`ENGINEERING_COMPARISON` is the only objective assembled from a
`ComparisonContextPackage` rather than a single `ContextPackage`
(`comparison_prompt_composition.py`, reached through
`prompt_builder_service.build_comparison_prompt_package`).

Two section types exist for it: **`LEFT_KNOWLEDGE`** and
**`RIGHT_KNOWLEDGE`**. They are separate typed sections rather than
labelled lines inside `SELECTED_KNOWLEDGE`, because a flattened rendering
would let a formatting change silently transpose the sides - and a
comparison answered backwards is worse than one not answered. Like every
other section they are always constructed: empty and disabled for every
objective that is not a comparison, which is why the package shape stays
fixed at eleven sections throughout.

`SELECTED_KNOWLEDGE` stays empty for a comparison: there is no single
body of selected knowledge, and putting either side there would imply one
is the default.

**A side with no evidence is rendered as an explicit statement that the
project holds none** - never as an empty section. An empty section would
leave the model to infer why it is empty, and the likeliest wrong
inference (that the equipment does not exist) is exactly the one the
workflow must prevent.

## Constraints and Instructions

Fixed, versioned, and always present (`composition_policy.py`,
`COMPOSITION_POLICY_VERSION`):

**Constraints** (behavioral - govern truthfulness). **Identical for
every objective.** An explanation is held to the same "never invent an
engineering fact" rule as a direct answer, because a longer answer is a
larger opportunity to invent one, not a licence to:
1. `use_only_supplied_evidence`
2. `do_not_invent_facts`
3. `report_uncertainty`
4. `preserve_engineering_terminology`
5. `cite_supporting_evidence`

**Instructions** (formatting - govern output structure, never
truthfulness). Selected by objective:

*`DIRECT_ANSWER`* (`INSTRUCTIONS`):
1. `structure_the_answer_with_clear_sections`
2. `reference_evidence_by_candidate_id`
3. `state_explicitly_when_no_supporting_evidence_exists`

*`ENGINEERING_EXPLANATION`* (`EXPLANATION_INSTRUCTIONS`):
1. `explain_function_and_role`
2. `structure_the_answer_with_clear_sections`
3. `reference_evidence_by_candidate_id`
4. `describe_only_what_the_evidence_covers`
5. `state_which_aspects_the_evidence_does_not_cover`

The last two exist because this objective specifically needs them:
*"how does an 87T work"* has a plausible textbook answer that owes
nothing to **this** substation, and a plausible answer about the wrong
installation is worse than an admitted gap.

*`ENGINEERING_VERIFICATION`* (`VERIFICATION_INSTRUCTIONS`, Milestone
24.1):
1. `declare_the_verdict_on_the_first_line`
2. `evaluate_only_retrieved_project_evidence`
3. `distinguish_absence_of_evidence_from_evidence_of_absence`
4. `report_conflicting_evidence_rather_than_choosing`
5. `report_uncertainty_honestly`
6. `cite_supporting_evidence_by_candidate_id`

The third is the one that makes verification meaningfully different from
every other objective. *"The project's evidence does not show a
differential protection on T1"* and *"T1 has no differential
protection"* are different statements, and in this domain confusing them
is how a real installation gets signed off on a gap nobody looked for.
The instruction set forces that distinction rather than hoping for it.

*`ENGINEERING_COMPARISON`* (`COMPARISON_INSTRUCTIONS`, Milestone 24.2):
1. `declare_the_comparison_outcome_on_the_first_line`
2. `compare_only_the_two_supplied_evidence_groups`
3. `preserve_left_and_right_direction`
4. `separate_added_removed_modified_and_unchanged`
5. `never_report_missing_evidence_as_a_difference`
6. `state_when_the_evidence_cannot_settle_the_comparison`
7. `cite_supporting_evidence_for_each_finding`

Two of these carry most of the weight. **Direction** (3): *"T1 has a
protection T2 lacks"* and its reverse are opposite engineering findings,
so direction is instructed explicitly rather than assumed from the order
evidence happens to appear in. **Missing evidence** (5): if one side's
evidence simply does not mention a protection, that is not a removal -
and a "removed protection" that was only ever un-indexed is exactly the
kind of confident wrong answer this domain cannot afford.

### The verdict protocol

`COMPARISON_OUTCOME_TOKENS` is the same device for comparisons, with
three literals - `COMPARABLE`, `INSUFFICIENT_EVIDENCE`,
`CONFLICTING_EVIDENCE`. Deliberately not "same" versus "different": a
real comparison usually contains both changed and unchanged aspects, so a
same/different verdict would force a false choice. The findings
themselves stay prose in the response body.

`VERIFICATION_VERDICT_TOKENS` is a closed vocabulary of four literals -
`SUPPORTED`, `NOT_SUPPORTED`, `INSUFFICIENT_EVIDENCE`,
`CONFLICTING_EVIDENCE` - and the **only** part of any answer this system
reads as a machine-readable token rather than as prose. The
`declare_the_verdict_on_the_first_line` instruction asks for exactly one
of them, alone, on the answer's first line.

Prompt Builder owns this vocabulary **because Prompt Builder is what asks
for it**; Engineering Response imports it rather than restating it, so
the question asked and the answer read cannot drift apart. An
architecture test asserts there is exactly one definition of it in the
codebase.

Never derived from `ContextPackage` content; changing an existing
objective's list requires a documented rationale and a
`COMPOSITION_POLICY_VERSION` bump. **Adding a new objective does not**
- it changes nothing about the packages already produced.

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

It also checks the **objective correspondence**: a package's
instructions and expected output must be exactly the fixed sets its
declared objective selects, and its constraints must be the single
shared set. This is what keeps `PromptObjective` an enumerable selector
rather than a way to smuggle arbitrary instructions into a prompt - a
package whose instructions are not one of the declared sets is
structurally invalid, however plausible its text looks.
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
`/context-builder/build` call returned. The optional `objective` field
selects the instruction/expected-output set (default `direct_answer`) -
it accepts only the declared enum values, never prompt text. Response: a
`PromptBuildResultRead` (the request's own configuration, the resulting
`PromptPackageRead`, and the self-validation result).

### Example

```http
POST /projects/42/prompt-builder/build
Content-Type: application/json

{
  "context_package": { "project_id": 42, "retrieval_summary": { ... }, "selected_candidates": [ ... ], ... },
  "objective": "engineering_explanation"
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
