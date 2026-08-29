# Promotion Rules

> **Since EPIC 31.2 this rule is also the *retrieval* gate.** Governed
> Structured Retrieval reads a graph object's `state` and performs no
> governance logic of its own, so what is written here is the only
> definition of which knowledge may answer an engineering question. See
> [governed_structured_retrieval.md](governed_structured_retrieval.md)
> §8 and [ADR-0026](adr/0026-governed-structured-retrieval.md) §4 for
> why a second definition was deliberately not created.

> What may become governed engineering knowledge, and what may not.
> Implemented in `app/domain/governed_knowledge_graph/promotion_rules.py`.
> Every rule here is tested individually.

---

## The rule

```
    current review decision == APPROVED
        AND
    review applicability == APPLIES
        AND
    the statement type has a governed edge kind
        AND
    both endpoint entities have governed node kinds
        AND
    the endpoint kinds are the ones the edge kind requires
        ↓
    PROMOTE
```

**Everything else is refused, with a stated reason.** There is no
implicit behaviour, no "promote anyway at lower confidence", and no
threshold. A statement is either governed engineering knowledge or it is
not.

`promotion_contract_version` is `1.0`. It is bumped when a rule changes
what would be promoted from identical inputs - never for a refactor - and
is recorded on every graph generation.

## The refusals

| Refusal | Condition | Why |
|---|---|---|
| `not_reviewed` | Nobody has reviewed the statement | An unreviewed statement is pipeline output, not governed knowledge. Admitting it would make the graph exactly what [ADR-0004](adr/0004-reviewed-facts-only-in-queryable-graph.md) forbids. |
| `review_rejected` | Current decision is `REJECTED` | An engineer looked and did not sustain it. |
| `review_inconclusive` | Current decision is `NEEDS_INVESTIGATION` | An engineer looked and could not yet decide. **Not a weak approval.** |
| `review_stale` | Applicability is `REQUIRES_REVALIDATION` | The judgement was passed on a statement derived under different rules or bytes. Promoting on the strength of it would publish knowledge nobody approved. |
| `review_orphaned` | Applicability is `ORPHANED` | There is no current interpretation to compare the judgement against. |
| `ungoverned_statement_type` | No edge kind for the statement type | Inventing one would be inventing engineering ontology. |
| `ungoverned_entity_type` | No node kind for an endpoint entity type | Same. |
| `invalid_endpoints` | The endpoint kinds are wrong for the edge kind | A rated power relates an asset to a quantity. The reverse would let the graph answer *"what is the rated power of 630 kVA?"*. |

### Order of evaluation

**Governance first, then vocabulary.** A rejected statement of an
ungovernable type is reported as `review_rejected`, because that is the
more useful thing to tell somebody: the reviewer's judgement is the fact
that matters, and the vocabulary gap is this platform's problem rather
than theirs.

### An unrecognised decision is refused

A decision value this context does not recognise is refused rather than
guessed at. A new decision upstream must be a deliberate change here, not
a silent promotion.

## Which refusals retire existing knowledge

Two groups, and only the first can retire anything:

**Judgement stopped sustaining it** - `not_reviewed`, `review_rejected`,
`review_inconclusive`, `review_stale`, `review_orphaned`. These describe
a statement that *was* promotable and is not any more, so knowledge in
the graph is retired.

**It was never promotable** - `ungoverned_statement_type`,
`ungoverned_entity_type`, `invalid_endpoints`. Nothing entered the graph,
so there is nothing to retire. These three *do* emit a
`PromotionFailed` event, because they are integrity problems worth
seeing; the first five do not, because a statement nobody approved is the
normal state of most statements and an event for each would bury the ones
that matter.

## Refusal → retirement reason

| Refusal | Retirement reason recorded on the object |
|---|---|
| `review_stale` | `requires_revalidation` |
| `review_orphaned` | `orphaned` |
| `not_reviewed`, `review_rejected`, `review_inconclusive` | `review_reversed` |
| Statement absent from the current interpretation | `requires_revalidation` |
| Node left with no relationships | `no_remaining_relationships` |

## Promotion outcomes

| Situation | What happens |
|---|---|
| Promotable, no edge yet | Nodes and edge created, `ACTIVE`. Emits `KnowledgePromoted`. |
| Promotable, edge retired | Edge **reactivated** - identity preserved. Emits `KnowledgeRevalidated`. |
| Promotable, edge already active | Provenance refreshed. Idempotent, and emits nothing: nothing became true. |
| Not promotable, edge active | Edge retired `HISTORICAL` with a reason. Emits `KnowledgeHistorical`. |
| Not promotable, no edge | Nothing. Most statements, most of the time. |

## The rule has exactly one definition

`promotion_rules.evaluate` is called by incremental promotion **and** by
a full rebuild. Neither re-implements it, and an architecture test
asserts no second `evaluate` exists in the context. Incremental and full
can therefore never disagree about what is promotable - which is the
usual failure mode of an incremental projection.

## The rule is pure

`evaluate` takes a `PromotionCandidate` - plain strings the application
service assembled - and returns a decision. No repository, no request, no
clock, and no import of the semantics or review contexts. That is what
lets every rule above be tested without a pipeline and without a
reviewer, and what keeps the graph context from depending on the ones it
projects.

---

See [knowledge_graph.md](knowledge_graph.md) for the graph itself, and
[ADR-0024](adr/0024-governed-knowledge-graph-as-projection.md) for why
these are the rules.
