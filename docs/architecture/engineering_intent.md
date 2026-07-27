# Engineering Request Classification

**Status:** As-built reference, Milestone 22. Describes the
`engineering_intent` bounded context as implemented - for the decision
record (why this is request classification rather than psychological
intent detection, why the first classifier is deterministic, why LLM
classification is excluded, why evidence is first-class, why confidence
is categorical, why ambiguity is valid, why the result is not
executable), see
[ADR-0019](adr/0019-engineering-request-classification.md). For where
this context sits in the wider pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md),
[conversation.md](conversation.md), and
[working_memory.md](working_memory.md).

## What this context does - and does not

It **classifies an explicit engineering request into a structured
domain result** a future orchestration component can use to select a
workflow. It answers exactly one question: *what category of
engineering workflow is being requested?*

It does **not**:

- detect the user's psychological intent, beliefs, or goals;
- understand or reason about the request;
- use an LLM, embeddings, vector similarity, or any external NLP
  service;
- execute a workflow, retrieve documents, query the graph, or invoke a
  provider;
- modify `Conversation` or `WorkingMemory`.

The package is named `engineering_intent` for roadmap continuity; its
documented responsibility is Engineering Request Classification.

## Pipeline

```
EngineeringIntentClassificationInput
        |
   input normalization       (engineering_intent_normalization.py)
        |
   rule evaluation           (engineering_intent_rules.py)
        |
   rule matches
        |
   precedence resolution     (engineering_intent_policy.py)
        |
   ambiguity detection       (engineering_intent_policy.py)
        |
   EngineeringIntent         (engineering_intent_builder.py)
        |
   validation                (engineering_intent_validation.py)
   EngineeringIntentClassificationResult
```

`engineering_intent_classifier.py` *decides* the classification;
`engineering_intent_builder.py` *constructs* the immutable aggregate
from the resolved data - the builder never duplicates classification
logic.

## Taxonomy

| Type | The request primarily asks to... |
|---|---|
| `DOCUMENT_LOOKUP` | find, locate, list or identify documents, drawings, files, pages or references |
| `KNOWLEDGE_QUERY` | obtain project facts, equipment, values, relationships, configurations or canonical engineering knowledge |
| `ENGINEERING_EXPLANATION` | explain, interpret, summarize or describe engineering content |
| `ENGINEERING_COMPARISON` | compare two or more engineering objects, documents, revisions, configurations or alternatives |
| `DRAWING_REQUEST` | create, modify or produce an engineering drawing or scheme |
| `VERIFICATION_REQUEST` | check, validate, verify, inspect or identify inconsistencies |
| `NAVIGATION_REQUEST` | open, navigate to or show a specific project resource or known location |
| `GENERAL_ENGINEERING_REQUEST` | *(fallback)* something engineering-related, with no more specific supported workflow deterministically establishable |
| `UNSUPPORTED_REQUEST` | *(fallback)* something clearly outside the supported engineering scope |
| `AMBIGUOUS_REQUEST` | *(outcome)* two or more materially distinct operations, each with strong evidence |

Deliberately small and operational - every type maps to a workflow a
future orchestrator could actually select.

## Classification input

`EngineeringIntentClassificationInput` carries only deterministic
values: `project_id`, `engineering_session_id`, `conversation_id`,
`turn_id`, `request_text`, a caller-supplied `classified_at`, plus two
optional, already-extracted structural Working Memory signals
(`working_memory_has_open_question`,
`working_memory_active_response_count`).

**It classifies the current explicit request only** - never the whole
conversation, never a concatenated history blob. It receives no
`Conversation`, `WorkingMemory`, or `EngineeringResponse` object at
all, which is what structurally prevents hidden semantic inference over
memory contents (see ADR-0019 §7).

## Normalization

`engineering_intent_normalization.py`, standard library only: Unicode
NFKC normalization, case folding, punctuation-to-whitespace
substitution (explicit character set, including apostrophes and hyphens
so `dell'impianto` → `("dell", "impianto")` and `media-tensione` →
`("media", "tensione")`), whitespace collapsing, whitespace
tokenization. Idempotent. The original request text is preserved
verbatim in `EngineeringIntentMetadata.original_request_text` alongside
the normalized form.

**Whole-token matching** is what this enables: the token `apri` never
fires on `aprile`, and `vs` never fires on `vsat` - a naive substring
search fires on both.

## Rule engine

`engineering_intent_rules.py` is an explicit, immutable table of
`EngineeringIntentRule` objects - never a large if/elif function. Each
rule carries whole `tokens` and/or multi-token `phrases`, a candidate
intent type, and a strength:

| Strength | Meaning | Example |
|---|---|---|
| `STRONG` | A specific workflow verb or phrase; alone identifies a workflow | `confronta`, `verifica`, `disegna`, `apri`, `spiega`, `find document` |
| `WEAK` | A supporting signal, not decisive alone | `quale`, `documento`, `differenze`, `coerenti` |
| `DOMAIN` | Establishes only that the request is engineering-related | `trasformatore`, `montante`, `switchgear`, `schema` |

Both Italian and English signals are supported throughout. Rules are
independently evaluable (`evaluate_rule`) and independently testable -
one rule at a time. `evaluate_all_rules` returns every match ordered
deterministically by `(token_index, rule_id)`.

## Precedence and ambiguity

```
1. DRAWING_REQUEST
2. VERIFICATION_REQUEST
3. ENGINEERING_COMPARISON
4. NAVIGATION_REQUEST
5. DOCUMENT_LOOKUP
6. ENGINEERING_EXPLANATION
7. KNOWLEDGE_QUERY
8. GENERAL_ENGINEERING_REQUEST
9. UNSUPPORTED_REQUEST
```

Adopted as the milestone's recommended starting policy unchanged;
`engineering_intent_policy.py`'s own comment documents why each
relative ordering holds. Worked consequences:

- *"Confronta i due documenti"* → `ENGINEERING_COMPARISON` (not
  `DOCUMENT_LOOKUP`), with `DOCUMENT_LOOKUP` reported as secondary.
- *"Verifica lo schema del montante"* → `VERIFICATION_REQUEST`.
- *"Apri la pagina con lo schema"* → `NAVIGATION_REQUEST`.

**Ambiguity** (`is_ambiguous`): when two or more *materially distinct
operations* - `DRAWING_REQUEST`, `VERIFICATION_REQUEST`,
`ENGINEERING_COMPARISON`, `NAVIGATION_REQUEST` - each have a `STRONG`
match, the result is `AMBIGUOUS_REQUEST` with every candidate reported
as secondary and all evidence retained. Reading-oriented types are
deliberately excluded from this rule (they overlap constantly in
natural phrasing). Worked consequences:

- *"Confronta e modifica lo schema"* → `AMBIGUOUS_REQUEST`, secondary
  `[DRAWING_REQUEST, ENGINEERING_COMPARISON]`.
- *"Disegna uno schema e poi verificalo"* → `AMBIGUOUS_REQUEST`,
  secondary `[DRAWING_REQUEST, VERIFICATION_REQUEST]` - the secondary
  operation is never silently discarded.

## Confidence policy

| Confidence | When |
|---|---|
| `HIGH` | Exactly one type has a `STRONG` match, and it is the selected type |
| `MEDIUM` | The selected type has only `WEAK` support, or a `STRONG` match exists but another type also has one |
| `LOW` | The result is `GENERAL_ENGINEERING_REQUEST` (only broad engineering signals) |
| `UNRESOLVED` | The result is `AMBIGUOUS_REQUEST` or `UNSUPPORTED_REQUEST` |

Categorical, never a fabricated probability.

## Evidence model

`EngineeringIntentEvidence`: `evidence_type` (`TOKEN_MATCH`,
`PHRASE_MATCH`, `DOMAIN_VOCABULARY_MATCH`, `STRUCTURAL_CONTEXT`),
`matched_rule_id`, `matched_text`, `token_index`,
`candidate_intent_type`, `strength`, a stable machine-readable
`description_code`, and a contiguous `sequence`. Ordered
deterministically by `(token_index, matched_rule_id)`.

**No hidden reasoning, no chain-of-thought, no AI-generated prose** is
ever stored.

## Identity

`EngineeringIntentId` = `f"{conversation_id}:{turn_id}:{policy_version}"`
- deterministic, never random. Reclassifying identical input under the
same policy version yields the same identity and the same result; a
changed policy version deliberately yields a different identity, so
results from different policies are never conflated.

## Fallback vocabulary

`GENERAL_ENGINEERING_REQUEST` requires at least one `DOMAIN`-strength
match - an unknown sentence is never treated as engineering-related
merely because it occurs inside a project. The supported vocabulary is
deliberately limited to SubstationOS's current domain: primary
substations, AT/HV, MT/MV, transformers, switchgear, protection
systems, measurements, cables, equipment, bays/montanti, drawings and
schematics, and project documentation (see `domain.vocabulary` in
`engineering_intent_rules.py` for the full list).

A request with no match at all - not even domain vocabulary - is
`UNSUPPORTED_REQUEST`.

## Validation

`validate_engineering_intent` (wrapped by `EngineeringIntentValidator`)
checks identity derivation, required provenance, metadata completeness,
version consistency, evidence sequencing and deterministic ordering,
evidence-to-intent consistency (including that no higher-precedence
candidate was ignored), unsupported-request rules (no evidence),
general-engineering rules (a domain signal exists, no workflow
candidate was available), ambiguity rules (both directions), secondary
match consistency, confidence consistency with the documented policy,
and statistics consistency.

**Structural only** - never whether the user's engineering statement is
technically correct.

## Service and API

`app/services/engineering_intent_service.py` is deliberately thin - no
rule, precedence decision, confidence derivation, or ambiguity rule
lives there.

```
POST /projects/{project_id}/engineering-intents/classify
```

Body: `engineering_session_id`, `conversation_id`, `turn_id`,
`request_text`, and optionally the two structural Working Memory
signals. **Never accepts a caller-supplied classification result** - no
intent type, confidence, evidence, or secondary match field exists on
the request schema (enforced by an OpenAPI integrity test). Returns the
intent, its evidence, confidence, secondary matches, metadata,
statistics, and the validation result. Structural input problems (blank
provenance, unclassifiable request text, non-positive project id)
return `422`.

## Determinism

Identical input under the same policy version produces an identical
`EngineeringIntentId`, intent type, confidence, evidence, secondary
matches, statistics, metadata (except the caller-supplied
`classified_at`), and validation result. `classified_at` is always
supplied by the caller; the domain never reads the wall clock.

## Architecture

`app/domain/engineering_intent/**` depends on **no other domain
bounded context at all** - the smallest dependency surface in the
pipeline. Enforced by
`test_engineering_intent_does_not_import_forbidden_modules`,
`test_engineering_intent_surface_has_no_ai_or_provider_dependency`
(which also forbids `numpy`/`sklearn`/`torch`/`transformers`/`spacy`/
`faiss`/`tiktoken` and similar, not merely provider SDKs), and
`test_engineering_intent_domain_imports_no_other_bounded_context`.

## What this milestone deliberately does not do

No LLM classification, prompt-based routing, embeddings, vector
similarity, semantic search, model probabilities, tool execution,
workflow execution, Engineering Assistant, task planning, request
decomposition, agents, drawing generation, persistence, user
preferences, or long-term memory. It modifies neither `WorkingMemory`
nor `Conversation`.

These belong to Milestone 23 (Engineering Assistant Foundation) and
later EPIC 5 milestones.
