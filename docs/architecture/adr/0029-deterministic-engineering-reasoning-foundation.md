# ADR-0029: Deterministic Engineering Reasoning Foundation

## Status

Accepted. Introduced by EPIC 32.1, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant was weakened, bypassed,
renamed away or reinterpreted to accommodate this milestone; three new
invariants (AF-REASON-001/002/003) were added alongside them, and four
frozen dependency directions were added to AF-DEP-001.

## Context

Everything SubstationOS has built so far **records**. The document
pipeline records what a document says. Engineering Facts record what was
measured. Engineering Semantics record what a fact means. Human Review
records a judgement about that meaning. The Governed Knowledge Graph is
a rebuildable projection of the statements a human approved
([ADR-0024](0024-governed-knowledge-graph-as-projection.md)). Governed
Structured Retrieval reads that projection
([ADR-0026](0026-governed-structured-retrieval.md)) and Governed Context
Assembly turns what it read into a context package
([ADR-0027](0027-governed-context-assembly.md)).

At no point does the platform *conclude* anything. The LLM writes prose
over the assembled context; the prose is presentation, never engineering
truth ([ADR-0006](0006-ai-as-interpretation-presentation-layer.md)).

That leaves a real engineering question unanswered. A substation's
documentation routinely contains two approved statements that disagree:
a single-line diagram giving a transformer 630 kVA and a datasheet
giving the same transformer 800 kVA, both read correctly, both reviewed,
both approved. Today the platform retrieves both, puts both in the
context, and asks a language model to write about them. Whether the
conflict is noticed depends on what the model happens to write.

**That is the gap this milestone closes**, and closing it requires the
platform to produce something it has never produced before: a statement
that is not in any document and was not approved by any reviewer.

The danger is immediate and structural. A conclusion looks exactly like
a fact. It has a subject, a value, a provenance chain and an
identifier. If it is allowed to flow into the same fields, the same
lists and the same tables as governed knowledge, then within a few
milestones nobody - not an engineer reading a response, not a reviewer
reading a queue, not a future developer reading the graph - will be able
to tell which statements a human approved and which the platform
inferred. At that point the value proposition of the entire system is
gone, because "reviewed knowledge" would no longer mean reviewed
knowledge.

## Decision

### 1. Governed Knowledge is not a Reasoning Conclusion (AF-REASON-001)

A conclusion is a **separate type, in a separate bounded context, in a
separate field**, at every layer it appears:

| Layer | Governed knowledge | Derived conclusion |
|---|---|---|
| Domain | `GraphNode` / `GraphEdge` | `ReasoningResult` |
| Context | `ContextItem` | *(absent - reasoning runs after assembly)* |
| Response | `references: tuple[EngineeringEvidenceReference, ...]` | `derived_reasoning: DerivedReasoningAssessment \| None` |
| API | `references[]` | `derived_reasoning` |

`ReasoningResult` carries no `review_id`, no `reviewer_display_name`, no
`statement_key`, no approval and no promotion flag - it *points at* the
governed facts that carry those, and holds none itself.
`DerivedReasoningAssessment.is_governed_knowledge` returns `False`,
permanently and by construction, so any caller tempted to treat a
conclusion as a fact has to read the word `False` while doing it.

A conclusion is deliberately **not** listed among the evidence
references. To every downstream consumer, an entry in `references` reads
as one more governed fact supporting the answer. A conclusion is not
one: it is a statement *about* those facts.

### 2. Every conclusion is traceable (AF-REASON-002)

A `ReasoningResult` always names:

- **what concluded it** - `rule_id` and `rule_version`, plus the rule
  family;
- **why** - a `ReasoningDiagnosticCode` from a closed vocabulary, never
  free prose;
- **from what** - a `ReasoningContributor` per governed fact, carrying
  the governed node id, the governed edge id, the Semantic Statement
  key, the Human Review id, the reviewer's display name, the support
  fingerprint, the document id, the content checksum, and the semantic
  rule id and version behind it.

That chain is what lets a reader verify a conclusion **without trusting
the reasoner**. It survives into the response and into the API as
`DerivedReasoningSupport`, so traceability is not lost at the boundary.

Governed values are reported exactly as governed: no rounding, no
re-scaling, no unit conversion.

### 3. Nothing is auto-promoted (AF-REASON-003)

Reasoning **cannot** write the governed graph, create a Human Review, or
promote anything - and this is enforced by absence rather than by
policy. The entire reasoning surface (domain, application service and
engine step handler) imports no repository, no session, no promotion
service, no Human Review module and no graph port. The step handler
declares no `__init__`, so it is constructed with nothing at all.

`knowledge_promotion_service` remains the single graph-authoring
authority (AF-KG-003, unchanged). An end-to-end test asserts the
governed graph is byte-identical before and after an execution that
concluded `INCONSISTENT` - the case a future "just record the
conclusion" change would target first.

The reason is not fastidiousness. A conclusion has no Human Review
behind it. Writing one into the graph would fabricate governance, and
**provenance a caller asserts is not provenance**.

### 4. Reasoning is deterministic, and that is a decision

No LLM, no embedding, no vector similarity, no probability, no
confidence, no score, no ranking, no threshold, no randomness, no clock.
`engineering_reasoning` joins the AF-DET-002 deterministic core - the
one context in that list that *produces* something new rather than
recording something observed, and therefore the one where determinism
had to be chosen rather than inherited.

A number expressing how sure a rule is would be an invitation to
threshold it, and a thresholded conclusion is a guess wearing a decimal
point. A structural fitness function asserts no identifier anywhere in
the reasoning surface is named `confidence`, `probability`, `score`,
`likelihood` or `ranking`.

Quantities are compared as `Decimal`, never `float`.

### 5. The outcome vocabulary is four-valued, never boolean

```
CONSISTENT              the governed values agree
INCONSISTENT            approved knowledge disagrees with itself
INSUFFICIENT_KNOWLEDGE  the graph does not answer the question
AMBIGUOUS               the question named more than one asset
```

These are four different engineering findings. "The graph does not
record a rated power for this transformer" and "this transformer is
consistent" are not the same statement, and an absence of contradiction
is not agreement. Collapsing the last three into "not consistent" is how
a real installation gets signed off on a gap nobody looked for.

The vocabulary is closed and asserted closed.

### 6. Different units are not compared, and never converted

The governed graph carries a declared value and a declared unit. It does
**not** carry a base value or a base unit - those exist only at the
evidence layer, upstream of promotion.

A rule that met two governed quantities in different units therefore has
two options: convert them itself, or decline. It declines, with
`UNSUPPORTED_COMPARISON` → `INSUFFICIENT_KNOWLEDGE`. Converting would
mean a unit table living in the reasoning layer, applied to values whose
provenance says nothing about how they were normalised - an
engineering-grade error waiting for the first non-SI datasheet.

### 7. Reasoning is a workflow capability, not a pipeline stage

The reasoning step runs in the `ENGINEERING_VERIFICATION` workflow
(bumped to version `2.0`), between Context Assembly and prompt building.
No other workflow declares `WorkflowCapability.ENGINEERING_REASONING`,
so no other workflow reasons: a knowledge query runs the same retrieval
and the same Context Assembly and comes back with `derived_reasoning` of
`None` - not an empty conclusion, and not a `CONSISTENT` one it never
derived.

**No new intent was added.** `VERIFICATION_REQUEST` already owns the
consistency vocabulary the deterministic classifier matches on
(`incoerenza`, `coerente`, `inconsistency`); a `CONSISTENCY_CHECK`
intent would have made that classifier ambiguous, and an ambiguous
deterministic classifier is worse than no new intent
([ADR-0019](0019-engineering-request-classification.md)).

### 8. Reasoning reads only the context it was handed

The application service performs **no I/O**. Its entire input is the
`ContextPackage` passed to it: it opens no session, holds no repository,
reads no graph and reads no review.

This is a security property, not a layering preference. Governed
Structured Retrieval applied the project scope, the document scope and
the caller's authorization. A reasoning service that could read for
itself would be able to widen any of them with nothing downstream
noticing. If the knowledge a rule needs is not in the context, the
answer is `INSUFFICIENT_KNOWLEDGE` - never a second query.

### 9. Conclusion identity is deterministic

`reasoning_result_id` is a SHA-256 over a namespaced tuple of the rule
id, the rule version, the question, the project id and the **sorted**
contributing governed identities. No timestamp, no duration, no counter.

The same governed knowledge and the same rule version therefore always
produce the same identifier, which is what makes a conclusion citable at
all. Reordering the contributing facts does not change it - the same
governed facts are the same governed facts. A rule version change
*does* change it, which is the point: a change in what the platform
concludes must be visible as a different conclusion, not a silent edit
to an existing one.

`duration_seconds` is measured, is operational, varies run to run, and
is excluded from identity for exactly that reason.

### 10. Three outcomes become warnings; one does not

| Outcome | Warning category |
|---|---|
| `INCONSISTENT` | `CONFLICTING_KNOWLEDGE` *(new)* |
| `AMBIGUOUS` | `AMBIGUOUS_KNOWLEDGE` |
| `INSUFFICIENT_KNOWLEDGE` | `INSUFFICIENT_EVIDENCE` |
| `CONSISTENT` | *(none)* |

Three separate categories, deliberately. Collapsing "the knowledge
conflicts", "the question was ambiguous" and "the knowledge is missing"
into one warning would erase exactly the distinction the four-valued
outcome exists to preserve.

`CONFLICTING_KNOWLEDGE` is new because no existing category said it. The
conflict is *inside reviewed knowledge*: it cannot be resolved by
retrieving better or asking the model again, and it is not the model
being unsure or the evidence being thin. Somebody has to fix the source.

### 11. No new public API

No reasoning endpoint is added. A conclusion is reachable exactly where
it is meaningful - on the engineering response the engine produced, as
`derived_reasoning`. A standalone `POST /reasoning` would accept a
context package from a caller, and a caller-supplied context package is
a caller-supplied claim about what governed knowledge says - the same
class of problem AF-PROV-002 forbids for provenance. See
[public_api.md](../public_api.md).

### 12. One rule, one quantity kind

`governed_quantity_consistency` v1.0, over `HAS_RATED_POWER` - because
that is the only relationship kind governed semantics currently
produces. The quantity kind is a named constant in the step handler
rather than something derived, so the day a second governed quantity
kind exists, choosing between them is a visible edit at a line that
already exists, and belongs in a rule rather than in a handler.

This is deliberately not a rule engine, a DSL or a plug-in registry
(YAGNI, CLAUDE.md §12). One rule, one version, one identity.

### 13. The bounded context sits between Context Assembly and Prompt Builder

```
governed_knowledge_graph → governed_retrieval → context_builder
                                                      ↓
                                          engineering_reasoning
                                                      ↓
                                       prompt_builder → engineering_response
```

`engineering_reasoning` depends on `context_builder`,
`governed_retrieval` and `governed_knowledge_graph` (vocabulary only -
never a repository). `prompt_builder` and `engineering_response` depend
on it, to render and to report respectively; neither evaluates a rule or
constructs a `ReasoningResult`.

The graph stays acyclic, and AF-DEP-001 now freezes six directions
involving reasoning, including the two that matter most:
`human_review → engineering_reasoning` (Engineering Judgement must not
depend on what the platform concluded) and
`engineering_reasoning → human_review` (a rule must not be able to read
judgements the assembled context never authorized).

### 14. The prompt states the conclusion; it does not ask for one

A `derived_reasoning` prompt section renders the outcome, the rule and
its version, the diagnostic and the contributing governed facts, and it
travels as a `CONTEXT` message rather than an instruction: the model is
told what was concluded, not asked to conclude. The comparison prompt
carries the section disabled, because comparison does not reason in this
milestone.

### 15. Consequences

**Gained.** The platform can now state, deterministically and with a
citable identity, that reviewed knowledge disagrees with itself - the
first engineering conclusion SubstationOS has ever produced, and the
first finding it can make that no document contains.

**Accepted cost.** One rule over one quantity kind is a narrow
capability relative to the architecture it establishes. That is the
intended trade: the milestone's deliverable is the boundary, and a
second rule now costs a file rather than a redesign.

**Constrained.** Any future rule must reach its conclusion from the
assembled context alone, must decline rather than convert units, must
choose from the same four outcomes, and must carry a version. A rule
that needs to read the graph is a signal that retrieval or Context
Assembly is missing something - not a reason to give reasoning a
repository.

**Watch.** The first genuine pressure on this ADR will be a request to
show conclusions in the review queue, or to seed proposed claims from
them. Both are reasonable products and both cross AF-REASON-003. Either
needs its own ADR and, almost certainly, its own explicitly
*ungoverned* surface - never a write into the governed graph.

### 16. What was deliberately not built

- No rule engine, DSL, rule registry or rule repository.
- No persistence of conclusions. A conclusion is derived on demand from
  governed knowledge; storing it would create a second copy that could
  drift from the graph it was derived from, and a stale conclusion is
  worse than no conclusion.
- No reasoning over document evidence, canonical text or unreviewed
  claims. Reasoning consumes governed knowledge exclusively.
- No cross-project or cross-document inference.
- No unit conversion (see §6).
- No new intent, no new public endpoint, no new database table, no
  migration.

### 17. Alternatives considered

**Ask the LLM to check consistency.** Rejected: the answer would vary
between runs, could not be versioned, and would make the one finding
that must be trustworthy the one finding that rests on prose.

**Store conclusions as graph nodes with a `derived: true` flag.**
Rejected: a flag is a convention, and conventions erode. AF-REASON-001
is a type boundary precisely so that erosion requires an edit somebody
must justify.

**Return a boolean plus a reason string.** Rejected: see §5. The reason
string is where the three non-agreeing outcomes would go to be ignored.

**A separate `POST /reasoning` endpoint.** Rejected: see §11.

### 18. Enforcement

| Invariant | Where |
|---|---|
| AF-REASON-001/002/003 + determinism | `tests/architecture/test_engineering_reasoning_boundaries.py` |
| Frozen dependency directions, deterministic core | `tests/architecture/test_architecture_freeze_af01.py` |
| Allowed context dependency graph, acyclicity | `tests/architecture/test_bounded_context_dependencies.py` |
| The rule's own behaviour, all four outcomes | `tests/domain/test_engineering_reasoning.py` |
| End-to-end through the real engine, and no promotion | `tests/services/test_engineering_engine_reasoning.py` |
| Only the verification workflow reasons | `tests/services/test_engineering_engine_verification.py` |

## References

- [Architecture Freeze AF-01](../architecture_freeze_af01.md)
- [Engineering Reasoning](../engineering_reasoning.md)
- [ADR-0006: AI as Interpretation/Presentation Layer](0006-ai-as-interpretation-presentation-layer.md)
- [ADR-0023: Human Review as Append-Only Judgement](0023-human-review-append-only-judgement.md)
- [ADR-0024: The Governed Knowledge Graph is a Rebuildable Projection](0024-governed-knowledge-graph-as-projection.md)
- [ADR-0026: Governed Structured Retrieval](0026-governed-structured-retrieval.md)
- [ADR-0027: Governed Context Assembly](0027-governed-context-assembly.md)
