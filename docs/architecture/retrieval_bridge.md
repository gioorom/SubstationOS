# Classification-to-Retrieval Bridge

**Status:** As-built reference, Milestone 23B.3, extended by Milestone 24.2 (the comparison arm). Describes the
`retrieval_bridge` bounded context and the Engineering Request
Preparation stage built on it. No new ADR: the decisions this milestone
makes are applications of
[ADR-0019](adr/0019-engineering-request-classification.md) ("a
classification result is not a command") and
[ADR-0020](adr/0020-engineering-engine-foundation.md) ("the engine
receives an explicit execution request"), not departures from either.
For where it sits, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## The gap it closes

Until this milestone the pipeline had a seam an engineer could not cross
unaided:

- the **classifier** decided *which workflow* a request wanted;
- the **engine** required retrieval criteria - a canonical entity id, an
  entity type, lexical terms - that only a caller who already knew the
  graph's contents could supply;
- **nothing deterministic connected the two.**

Every workflow was therefore usable only by a caller who already had the
answer half-written. The bridge closes that, and nothing more.

```
Raw Request
   → Classification        (EngineeringIntent - Milestone 22)
   → Retrieval Bridge      (RetrievalConfiguration - this milestone)
   → Engine                (explicit execution request - Milestone 23A)
   → Workflow              (23A / 23B.1 / 23B.2)
```

## What it is - and is not

It maps a **classified request** to **retrieval criteria**. It is:

- **not a query planner** - it never touches Graph Query and never
  decides how retrieval executes;
- **not a fact extractor** - it reports designations a request literally
  contains, never entities it believes the request is "about";
- **not an interpreter** - no embeddings, no LLM, no provider call, no
  fuzzy matching, no scoring;
- **not a fallback** - insufficient or conflicting evidence yields a
  typed unresolved result, never a broadened retrieval.

## Boundary

| Layer | Location | Holds |
|---|---|---|
| Domain | `app/domain/retrieval_bridge/**` | Immutable models, the policy table, designation extraction, the mapping, structural validation |
| Application | `app/services/engineering_request_preparation_service.py` | Composes classification + bridge into an `EngineeringEngineExecutionRequest` |
| API | `app/routers/engineering_request_preparation.py`, `app/schemas/engineering_request_preparation.py` | `POST /projects/{id}/engineering-requests/prepare` |

It depends on exactly three other domain contexts, all upstream:
`engineering_intent` (what it maps from), `canonicalization` (the one
existing canonical vocabulary), `structured_retrieval` (`RetrievalMode`
and the request bounds). **It depends on the Engineering Engine not at
all, and the engine depends on it not at all** - enforced by
`tests/architecture/test_retrieval_bridge_boundaries.py`.

## Designations

A **designation** is a token the request literally contains that is
shaped like equipment: **at least one ASCII letter and at least one
ASCII digit** ("T2", "87T", "Q52", "C-295", "TR2").

Deliberately excluded:

- **bare words** ("trasformatore", "montante", "TA") - a type name is not
  an instance designation, and searching for one would broaden retrieval
  to every transformer in the project when the engineer asked about one;
- **bare numbers** ("295", "400") - nothing distinguishes an equipment
  number from a voltage, a page, or a quantity.

Extraction preserves the designation **exactly as written** and
deduplicates case-insensitively, keeping the first spelling. This module
tokenizes the request itself rather than reusing the classifier's
normalizer, which treats `-` as a separator (correctly, for its own
purpose) and would split "C-295" into "c" and "295".

### Resolution

Each designation gets one attempt against Canonicalization's public
`normalize_entity_reference` - never a second copy of that vocabulary:

| Outcome | Meaning |
|---|---|
| `CANONICAL_REFERENCE` | Recognized: "C-295" → `CABLE:C-295` |
| `LEXICAL_TERM` | Not recognized: carried forward verbatim as a search term |

**A designation is never guessed into a canonical identifier.** Today's
canonical vocabulary covers `CABLE`/`TRANSFORMER`/`BREAKER`/`RELAY`/
`CABINET`/`SWITCH`/`BUSBAR` with a letter-prefix-then-digits shape, so
real designations like "87T" (an ANSI device number) and "Q52" resolve
to lexical terms. That is an honest "this system does not know which
graph entity this names", not a failure.

## Mapping policy

An immutable table (`retrieval_bridge_policy.py`), versioned by
`BRIDGE_POLICY_VERSION` - never an if/else chain. An AST-level test
enforces that no module outside the table branches over intent types.

| Intent | Canonical lookup? | Lexical mode | Neighborhood | Limit |
|---|---|---|---|---|
| `KNOWLEDGE_QUERY` | yes | `LEXICAL_SEARCH` | no | 20 |
| `DOCUMENT_LOOKUP` | **no** | `LEXICAL_SEARCH` | no | 20 |
| `ENGINEERING_EXPLANATION` | yes | `LEXICAL_SEARCH` | **yes, depth 1** | 20 |

Two entries deserve their reasons stated:

- **`DOCUMENT_LOOKUP` never produces a canonical reference.** That
  workflow reads the Engineering Index by identifier, not the graph by
  canonical id; handing it `CABLE:C-295` would send it looking for a
  document mentioning that string, which no document does.
- **`ENGINEERING_EXPLANATION` expands the neighborhood.** An explanation
  asks how things relate, so the relationships around the named
  equipment are part of the answer rather than context beyond it. This is
  the only expansion the bridge applies, it is fixed policy rather than
  per-request, and depth 1 is the only depth Structured Retrieval
  supports.

### The comparison arm (Milestone 24.2)

A comparison does not produce *one* retrieval configuration - it produces
two - so it sits outside `RETRIEVAL_POLICY_BY_INTENT`, which maps an
intent to exactly one. `comparison_bridge.py` derives it, reusing the
same designation extraction and resolution, under a single
`COMPARISON_OPERAND_POLICY` applied to **each operand independently**:

| | |
|---|---|
| Canonical lookup | **yes**, per side - unlike the single-operand path, two canonicalizable subjects are the normal case here, because each side has its own configuration to carry one |
| Neighborhood | **depth 1**, both sides - what usually differs between two montanti is what each is connected to and protected by |
| Operand count | **exactly 2** (`REQUIRED_COMPARISON_OPERAND_COUNT`) |

**The operand count is a hard rule, and the heart of this arm:**

- **Fewer than two** → `INSUFFICIENT_EVIDENCE`. A comparison against one
  subject is not a comparison, and the second operand is never inferred -
  not from the conversation, not from the project, not from what usually
  gets compared with a T1.
- **More than two** → `CONFLICTING_EVIDENCE`. Three named subjects leave
  the system choosing which two the engineer meant, and choosing silently
  is how a comparison of the wrong pair gets acted on. **The surplus is
  never truncated.**

**Order is preserved** from the request's own token order: first
designation LEFT (baseline), second RIGHT (candidate). `left` and `right`
are named fields, never a list - "confronta T1 con T2" and "confronta T2
con T1" are different questions, and there is no index to transpose.

Both arms reuse the same failure taxonomy; Milestone 24.2 added no new
codes.

**Intents absent from the table are refused** (`UNSUPPORTED_INTENT_MAPPING`),
never given a default. Navigation and Drawing are deliberately out of scope; Verification
joined in Milestone 24.1 and Comparison in 24.2, each when its
workflow existed to receive the prepared request.

## Output

`RetrievalConfiguration` is a field-for-field mirror of the `retrieval_*`
configuration `EngineeringEngineExecutionRequest` already accepts, so the
engine consumes it with no new model and no change of any kind.

`entity_type` and `attribute_name` are **always `None`**, and validation
enforces it:

- an entity type alongside a canonical reference makes the request
  invalid (`ENTITY_LOOKUP` admits the canonical-id criterion only);
- an entity type without one would make the engine derive
  `ENTITY_TYPE_SEARCH` and silently widen a lexical search to every
  entity of that type;
- nothing in classifier evidence identifies an attribute.

The resolved entity type is still reported - on the `RequestDesignation`,
which is where provenance belongs.

### The mode-agreement invariant

The engine's retrieval step handler **re-derives** a `RetrievalMode` from
which criteria fields are set. A configuration whose declared mode
disagreed with what the engine derives would report one thing and do
another. `retrieval_bridge_validation.py` makes that disagreement
structurally impossible, and a test asserts the declared mode always
equals the mode the engine actually builds.

*(This invariant earned its place: the first implementation emitted an
entity type alongside the canonical reference, and this test caught the
resulting invalid retrieval request before it reached anything.)*

## Failure model

Five typed, provider-neutral outcomes. None describes a provider, a
network, or an execution - this context executes nothing.

| Code | When |
|---|---|
| `INVALID_BRIDGE_INPUT` | The intent is structurally invalid (non-positive project, blank text, metadata disagreement) |
| `UNSUPPORTED_INTENT_MAPPING` | The intent has no policy entry |
| `INSUFFICIENT_EVIDENCE` | The request names no designation |
| `CONFLICTING_EVIDENCE` | Two distinct canonical entities were named, and retrieval resolves one |
| `INVALID_RETRIEVAL_CONFIGURATION` | The derived configuration failed structural validation (e.g. more than eight lexical terms) |

**A refusal always reports the designations it found.** A refusal that
reported nothing would be indistinguishable from a bug.

Two rules follow from "never silently broaden":

- an under-specified request is refused, not answered against everything;
- a surplus of designations is refused, not truncated - dropping some
  would answer a narrower question than the one asked.

## Determinism

The same classified request and the same policy version always produce
the same result, including designation order and every derived field.
`derived_at` is caller-supplied; no wall clock is read. No I/O, no
persistence, no network.

## API

```
POST /projects/{project_id}/engineering-requests/prepare
```

The body carries a raw sentence and request provenance. It carries **no
retrieval criteria, no prompt, no instruction, no workflow name and no
intent type** - deriving those is the endpoint's purpose, and accepting
an override would reopen the gap it exists to close.

The response's `execution_request` is exactly the body
`/engineering-engine/execute` accepts, so a caller posts it on unchanged
- the same "reuse the upstream response shape" pattern every stage here
follows.

**An unresolvable request returns HTTP 200 with `prepared=false`**, not a
client error: the request was well-formed and the bridge answered it
correctly. `422` keeps meaning exactly one thing - a structurally invalid
request.

## Known limitations

- **Conversational reference is not resolved.** "Come funziona questo
  montante?" names no designation; the bridge refuses rather than
  guessing which equipment "questo" means. Resolving it needs Working
  Memory, which this stage deliberately does not consult.
- **The canonical vocabulary is narrow.** ANSI device numbers ("87T") and
  the "T1"/"Q52" designation styles are not canonicalizable today, so
  they become lexical terms rather than entity lookups.
- **No attribute criteria.** `ATTRIBUTE_SEARCH` and `COMBINED` are never
  produced, because nothing in classifier evidence identifies an
  attribute.
