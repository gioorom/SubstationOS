# Engineering Reasoning

**Status:** Foundation shipped in EPIC 32.1.
**Decision record:** [ADR-0029](adr/0029-deterministic-engineering-reasoning-foundation.md).
**Binding invariants:** [Architecture Freeze AF-01](architecture_freeze_af01.md),
plus AF-REASON-001/002/003 introduced here.

---

## 1. What this context is for

Everything upstream of this context **records**: what a document says,
what was measured, what it means, what a human approved, what the
governed projection holds, what retrieval matched, what context was
assembled. Nothing concludes.

Engineering Reasoning concludes. It is the first capability in
SubstationOS that produces a statement which is **not in any document
and was not approved by any reviewer**.

The first thing it concludes is the thing a substation engineer most
needs a system to notice: that two approved documents disagree. A
single-line diagram giving a transformer 630 kVA and a datasheet giving
the same transformer 800 kVA are both read correctly, both reviewed and
both approved - and until this context existed, whether anybody noticed
depended on what a language model happened to write.

## 2. The one distinction everything else follows from

> **Governed Knowledge is not a Reasoning Conclusion.**

A conclusion looks exactly like a fact: subject, value, provenance
chain, identifier. If it is ever allowed into the same field, the same
list or the same table as governed knowledge, then "reviewed knowledge"
stops meaning reviewed knowledge - not dramatically, but one milestone
at a time, until nobody can tell the two apart.

So the separation is a **type boundary**, not a flag:

| Layer | Governed knowledge | Derived conclusion |
|---|---|---|
| Domain | `GraphNode` / `GraphEdge` | `ReasoningResult` |
| Response | `references[]` | `derived_reasoning` |
| API | `references[]` | `derived_reasoning` |

A conclusion is deliberately **not** an evidence reference. To every
downstream consumer, an entry in `references` reads as one more governed
fact supporting the answer. A conclusion is a statement *about* those
facts, not one of them.

## 3. Where it sits

```
document → facts → semantics → Human Review → governed projection
                                                       ↓
                                          Governed Structured Retrieval
                                                       ↓
                                            Governed Context Assembly
                                                       ↓
                                          ► ENGINEERING REASONING ◄
                                                       ↓
                                        Prompt Builder → LLM → Response
```

Reasoning runs **after** context assembly and **before** the prompt, in
the `ENGINEERING_VERIFICATION` workflow only (version `2.0`). No other
workflow declares `WorkflowCapability.ENGINEERING_REASONING`, so no
other workflow reasons - a knowledge query comes back with
`derived_reasoning` of `None`, which is a different and honest state
from a `CONSISTENT` it never derived.

## 4. The four outcomes

```
CONSISTENT              the governed values agree
INCONSISTENT            approved knowledge disagrees with itself
INSUFFICIENT_KNOWLEDGE  the graph does not answer the question
AMBIGUOUS               the question named more than one asset
```

Four values, never a boolean and never a score. These are four different
engineering findings:

- "The graph does not record a rated power for this transformer" is not
  "this transformer is consistent". **An absence of contradiction is not
  agreement.**
- "The question named two transformers" is not "the transformers
  disagree".

Collapsing the last three into "not consistent" is how a real
installation gets signed off on a gap nobody looked for. The vocabulary
is closed, and a fitness function asserts it stays closed.

Each outcome carries a `ReasoningDiagnosticCode` saying *why*, from a
closed vocabulary - never free prose:

| Code | Meaning |
|---|---|
| `values_equal` | more than one governed value, all equal |
| `single_value` | exactly one governed value |
| `values_conflict` | governed values differ |
| `no_required_quantity` | the asset exists; the quantity does not |
| `no_subject` | nothing matched the designation |
| `ambiguous_subject` | more than one governed asset matched |
| `unsupported_comparison` | the values are in different units |
| `unparsable_value` | a governed value is not a decimal |

## 5. What a conclusion carries

```
ReasoningResult
  result_id                    deterministic SHA-256 identity
  query                        the typed question (never free text)
  rule        → rule_id, rule_version, family
  outcome                      one of four
  diagnostics → code, duration_seconds
  contributors[]               one per governed fact used
  reasoning_policy_version
  context_assembly_version
  evaluated_at                 supplied by the caller, never read from a clock
```

Every `ReasoningContributor` names the governed node, the governed edge,
the Semantic Statement key, the Human Review id, the reviewer's display
name, the support fingerprint, the document id, the content checksum,
and the semantic rule id and version.

That chain is what lets a reader verify a conclusion **without trusting
the reasoner** (AF-REASON-002). It survives into the response and the
API as `DerivedReasoningSupport`.

`ReasoningResult` itself carries no `review_id`, no
`reviewer_display_name`, no `statement_key` and no approval. It *points
at* the governed facts that carry those and holds none of its own.

## 6. Determinism

No LLM. No embedding. No vector similarity. No probability, confidence,
score, likelihood, ranking or threshold. No randomness. No clock.

`engineering_reasoning` is part of the AF-DET-002 deterministic core -
the only context in that list that produces something new rather than
recording something observed, and therefore the only one where
determinism had to be *chosen* rather than inherited.

A number expressing how sure a rule is would be an invitation to
threshold it, and a thresholded conclusion is a guess wearing a decimal
point. A structural fitness function asserts that no identifier anywhere
in the reasoning surface is named `confidence`, `probability`, `score`,
`likelihood` or `ranking`.

Quantities are compared as `Decimal`, never `float`.

`result_id` is a SHA-256 over the rule id, the rule version, the
question, the project id and the **sorted** contributing governed
identities. No timestamp, no duration, no counter. The same governed
knowledge always yields the same identifier; a rule version change
always yields a different one.

## 7. It reads only what it was handed

The application service performs **no I/O**. Its entire input is the
`ContextPackage` passed to it: no session, no repository, no graph read,
no review read. The engine step handler declares no `__init__`, so it is
constructed with nothing at all.

This is a security property, not a layering preference. Governed
Structured Retrieval applied the project scope, the document scope and
the caller's authorization. A reasoning service that could read for
itself would be able to widen any of them with nothing downstream
noticing.

**If the knowledge a rule needs is not in the context, the answer is
`INSUFFICIENT_KNOWLEDGE` - never a second query.**

## 8. It promotes nothing

Reasoning cannot write the governed graph, cannot create a Human Review
and cannot promote anything - enforced by **absence**. The whole
reasoning surface imports no repository, no session, no promotion
service, no Human Review module and no graph port.

`knowledge_promotion_service` remains the single graph-authoring
authority (AF-KG-003). An end-to-end test asserts the governed graph is
byte-identical before and after an execution that concluded
`INCONSISTENT` - the case a future "just record the conclusion" change
would target first.

A conclusion has no Human Review behind it. Writing one into the graph
would fabricate governance, and **provenance a caller asserts is not
provenance**.

## 9. Units are never converted

The governed graph carries a declared value and a declared unit. It does
**not** carry a base value or a base unit; those exist only at the
evidence layer, upstream of promotion.

Two governed quantities in different units therefore produce
`unsupported_comparison` → `INSUFFICIENT_KNOWLEDGE`. Converting would
mean a unit table living in the reasoning layer, applied to values whose
provenance says nothing about how they were normalised - an
engineering-grade error waiting for the first non-SI datasheet.

## 10. How it reaches the reader

**In the prompt.** A `derived_reasoning` section renders the outcome,
the rule and version, the diagnostic and the contributing governed
facts. It travels as a `CONTEXT` message, not an instruction: the model
is told what was concluded, not asked to conclude.

**In the response.** `EngineeringResponse.derived_reasoning` carries the
machine-readable `DerivedReasoningAssessment`. Three of the four
outcomes also raise a warning, in three separate categories:

| Outcome | Warning |
|---|---|
| `INCONSISTENT` | `conflicting_knowledge` |
| `AMBIGUOUS` | `ambiguous_knowledge` |
| `INSUFFICIENT_KNOWLEDGE` | `insufficient_evidence` |
| `CONSISTENT` | *(none - nothing for a reader to act on)* |

`conflicting_knowledge` is a new category because no existing one said
it. The conflict is *inside reviewed knowledge*: not the model being
unsure, not the evidence being thin. It cannot be fixed by retrieving
better or asking again - somebody has to fix the source.

**In the API.** `derived_reasoning` on the engineering response. There
is **no reasoning endpoint**: a standalone `POST /reasoning` would
accept a context package from a caller, and a caller-supplied context
package is a caller-supplied claim about what governed knowledge says.

## 11. Current scope

One rule: `governed_quantity_consistency` v1.0, over `HAS_RATED_POWER` -
the only relationship kind governed semantics currently produces.

This is not a rule engine, a DSL or a plug-in registry. One rule, one
version, one identity. The quantity kind is a named constant
(`REASONED_QUANTITY_KIND`) rather than something derived, so the day a
second governed quantity kind exists, choosing between them is a visible
edit at a line that already exists.

The milestone's deliverable is the boundary. A second rule now costs a
file rather than a redesign.

## 12. Where the invariants are enforced

| Invariant | File |
|---|---|
| AF-REASON-001/002/003, determinism, closed vocabulary | `tests/architecture/test_engineering_reasoning_boundaries.py` |
| Frozen dependency directions, deterministic core, acyclicity | `tests/architecture/test_architecture_freeze_af01.py` |
| Allowed bounded-context dependency graph | `tests/architecture/test_bounded_context_dependencies.py` |
| The rule's behaviour, all four outcomes | `tests/domain/test_engineering_reasoning.py` |
| End-to-end through the real engine; no promotion | `tests/services/test_engineering_engine_reasoning.py` |
| Only the verification workflow reasons | `tests/services/test_engineering_engine_verification.py` |

## 13. The pressure to watch

The first genuine pressure on this design will be a request to show
conclusions in the review queue, or to seed proposed claims from them.
Both are reasonable products. Both cross AF-REASON-003.

Either needs its own ADR and, almost certainly, its own explicitly
**ungoverned** surface - never a write into the governed graph.
