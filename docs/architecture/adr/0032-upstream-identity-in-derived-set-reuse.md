# ADR-0032 — Upstream identity in derived-set reuse

Status: **Amended** by EPIC 32.E2.4 — see *Amendment* below.
Originally Accepted (EPIC 32.E2.1 / 32.E2.2).

Supersedes nothing. Constrains every bounded context that persists a
deterministic derived set.

## Context

The governed pipeline is a chain of deterministic derivations, each one
persisted so that re-running it is cheap and so that a historical result
stays explainable:

```
Canonical source → Evidence → Entities → Facts → Semantics
```

Every stage stores its result and, on a re-run, looks for a stored set
that is *compatible* rather than recomputing. That lookup key is the
whole safety mechanism: it decides when a stored answer may stand in for
a fresh one.

Each set records the chain of policy versions above it. The chain,
however, began one link too late — at `resolution_policy_version` — and
omitted `extraction_policy_version`. Nothing noticed while the extraction
policy had never moved.

EPIC 32.E2 moved it, from 1.0 to 2.0, and changed what the evidence
*says*: `+GSH002` is a designation under 1.0 and a structural location
under 2.0. The consequence was reproduced end to end:

- evidence re-extracted correctly (extraction policy is its own key);
- entities reused a set resolved from the old reading;
- facts and semantics reused results built from entities that no longer
  existed;
- the location fact, its `IS_LOCATED_IN` statement, and therefore the
  governed graph edge, silently disappeared.

Nothing failed. The pipeline reported success and served knowledge that
its own current evidence contradicted, which in this domain is worse
than a visible error.

## Decision

**A persisted deterministic derived set is reusable only when the
immutable identity of its effective upstream derived set and its own
policy identity are compatible.**

Concretely, each layer's reuse key is its upstream layer's identity plus
its own policy version:

| Derived set | Reuse identity |
|---|---|
| Evidence | document, checksum, **extraction** |
| Entities | document, checksum, **extraction**, resolution |
| Facts | document, checksum, **extraction**, resolution, fact |
| Semantics | document, checksum, **extraction**, resolution, fact, semantic |

Three rules follow from it, and they are the parts worth stating
separately because each was violated at least once:

1. **The identity is copied from the upstream set object**, never passed
   in by a caller and never reconstructed. A layer consults the
   provenance of the set it is about to read; it does not re-derive what
   the layer above it established. Facts read
   `entity_set.extraction_policy_version`; semantics read
   `fact_set.extraction_policy_version`.

2. **Policy versions stay independent.** Four policies version four
   catalogues and change for four reasons. A version is raised when
   *that* policy changes and never to express that something upstream
   moved — a false provenance statement is worse than a missing one.
   The reuse key is what propagates change; the version numbers are not.

3. **Unknown provenance is not compatible provenance.** Where the column
   was added to tables that never had it, existing rows keep `NULL`
   rather than a guessed version, and a `NULL` never satisfies a reuse
   lookup. Two unknowns are not the same unknown: matching on `NULL`
   would render as `IS NULL` in SQL and pair arbitrary legacy rows, so
   the adapters refuse before building the query.

   An unknown set is therefore not merely non-reusable — it cannot be
   *built upon*. A unique constraint does not collapse `NULL`s either,
   so interpreting a fact set of unknown provenance would append a new,
   equally unusable statement set on every call. The semantic stage
   refuses instead, naming the remedy: re-run fact construction. A
   visible refusal that says what to do is the governed answer; silent
   unbounded growth is not.

Database uniqueness constraints carry the same columns as the lookups.
The lookup decides what may be *reused*; the constraint decides what may
*exist*, and a constraint narrower than its lookup would forbid the very
row a policy bump has to create.

## Consequences

**Wanted.** A change anywhere upstream invalidates everything below it,
deterministically and without anyone remembering to. Two readings of one
source coexist in storage, each explainable, neither overwriting the
other. The stale-reuse class is closed structurally rather than by
discipline: executable fitness functions assert the identity of every
boundary, and a new layer that keys reuse on less than its upstream
identity fails them.

**Accepted costs.** Every derived-set table carries a copied provenance
prefix that grows by one column per layer. This is the repository's
existing natural-key architecture — no derived set in this chain has a
surrogate id, and inventing one purely to shorten the prefix would add
an indirection that buys nothing today. A fifth layer would make the
prefix worth revisiting; four does not.

Legacy rows with unknown provenance are recomputed on the next run
rather than reused — wasted work exactly once per document, and the
price of never serving an answer whose origin nobody can establish.

Where the *upstream* set is the unknown one, the stage below it refuses
rather than recomputing, because its output would inherit the unknown
and could never be reused or deduplicated. An operator re-runs the
stage above. This is the one place where the chain answers with an
error rather than with work, and it is deliberate: the alternative is a
table that grows without bound.

**Known residual — the contract-version axis.** Each layer also hashes a
*contract version* (`ENTITY_MODEL_VERSION`, `FACT_CONTRACT_VERSION`,
`SEMANTIC_CONTRACT_VERSION` — the shape of an entity, a fact, a
statement) into every row key it produces, and none of them appears in
any reuse key or unique constraint. Bumping one alone would change every
row key while leaving the set-level identity untouched: the stored set
would be reused and the new shape would never materialise. That is this
same defect, one axis over. It is dormant only because no contract
version has ever moved — which is exactly what was true of the
extraction policy before EPIC 32.E2.

It is not closed structurally here, because doing so means carrying
three more columns through three tables and that decision has not been
taken. Instead the known-good `(policy version, contract version)`
pairings are pinned in
`tests/architecture/test_artifact_identity_architecture.py`, so a
contract version cannot move silently: the build fails, and the fix is
to raise the policy version beside it, which *is* in the reuse key. A
tripwire, not a proof, and recorded as such.

**Deliberately not decided here.** `GraphProvenance.pipeline_identity`
still describes the upstream chain as a four-tuple without the
extraction policy. It is descriptive — no reuse or deduplication is
keyed on it — and the governed graph's identity rules are not this
decision's business. It is recorded as known debt.

## Enforcement

Superseded by the Amendment's enforcement list below. The modules named
in the original decision were replaced along with the model they held.

---

## Amendment (EPIC 32.E2.4) — deterministic artifact identity

The rule above stands. **How it is enforced has been replaced.**

### Why

The original decision made each layer's reuse key its upstream layer's
key plus its own policy version — a copied prefix, propagated by hand.
EPIC 32.E2.3 audited every persisted reuse boundary in the repository
and reproduced **six** independent places where that prefix had silently
lost a component:

| Boundary | Missing from its reuse identity |
|---|---|
| Canonical PDF | `representation_version` (its own constraint had it; the lookup did not) |
| Canonical Text | the representation it segmented |
| Evidence | the segmentation it read |
| Entities | `ENTITY_MODEL_VERSION` |
| Facts | `FACT_CONTRACT_VERSION` |
| Semantics | `SEMANTIC_CONTRACT_VERSION` |

Two things made this fatal rather than merely untidy. Closing it by
extending the natural keys would have taken the semantic set to
**eleven** identity columns, each one copied through five tables. And
the mechanism that had already failed six times was exactly that
copying: a reviewer, not a compiler, was the only thing checking that a
downstream key still listed everything above it.

### The new decision

Every persisted deterministic artifact carries its own identity:

```
identity = H(identity contract, artifact kind, upstream identity,
             local derivation identity)
```

- **`upstream identity`** is the identity of the artifact this one was
  derived from — one link, not a transitive list.
- **`local derivation identity`** is every version *this* stage owns and
  nothing else. Facts name their fact policy and fact contract; they do
  not name the extraction policy, and cannot fall out of step with it.
- **`artifact kind`** is inside the preimage, so two artifacts built from
  identical material but of different kinds cannot collide.
- **`identity contract`** versions the composition scheme itself. It is
  deliberately independent of every engineering policy and must never be
  borrowed to invalidate a cache.

Reuse is one comparison: *does an artifact with this identity exist for
this document?* The uniqueness constraint encodes the same rule.
Invalidation then propagates by construction — a change at any stage
changes its identity, which is the next stage's upstream identity, all
the way down. The full matrix is asserted in
`tests/services/test_artifact_identity_reuse.py`.

### Stages are invoked; identity decides what each one does

There is **no automatic cascade**, and there was never meant to be. Each
stage is invoked explicitly - by the pipeline, by an operator, by an
endpoint - and identity decides what that invocation *does*. Reading the
matrix therefore needs five outcomes, not two:

| Outcome | Meaning |
|---|---|
| `REUSE` | The stored artifact has the identity being asked for. Returned unchanged. |
| `RECOMPUTE` | No artifact has that identity. Derived afresh and stored **alongside** the old one. |
| `UNSUPPORTED` | The upstream artifact was built under a policy version this build does not declare. Refused visibly, with the stage named. Neither a reuse nor a recomputation. |
| `UNKNOWN_UPSTREAM` | The upstream artifact carries no identity - a row written before this chain existed. Refused, naming the stage to re-run, because anything derived from it could prove nothing and nothing could deduplicate it. |
| `RECONSTRUCT_UPSTREAM` | The upstream artifact's identity is **recomposed from its own immutable persisted columns** rather than read. Available only where the whole preimage is stored, which today is exactly one place: canonical text recomposing the representation's identity. |

`RECONSTRUCT_UPSTREAM` is the documented exception to `UNKNOWN_UPSTREAM`,
and it is narrow by construction. Canonical text can recompose a
representation's identity because all six preimage components -
document, checksum, checksum algorithm, representation contract, parser
name, parser version - are `NOT NULL` columns on the representation row.
That is a deterministic proof from immutable state, not a guess, so a
representation stored before the identity chain existed does not block
segmentation. No other stage has its upstream's full preimage, so no
other stage may do this, and none does.

`UNSUPPORTED` is a separate, older gate and not an identity question -
but it is the one that decides what a *policy bump* feels like in
practice, so it is worth stating exactly.

Every `SUPPORTED_*_VERSIONS` set is a singleton of the current policy
constant. Raising a policy therefore does two things at once: new
artifacts are built under the new version, and **already-stored upstream
artifacts under the old version become unsupported**. The stage below
does not reuse them and does not quietly recompute from them - it
refuses, naming the version it found.

That makes the order of invocation part of the contract, not an
implementation detail:

- **In pipeline order.** Re-run the stage whose policy changed, then the
  stages below it. Each produces a new identity, each stage below sees a
  supported upstream, and every one of them reports `RECOMPUTE`. A
  raised `RESOLUTION_POLICY_VERSION`, reproduced end to end, gives
  `RECOMPUTE` at Entities, Facts and Semantics, with Evidence and above
  keeping their identities and the lineage intact at every link.
- **A lower stage alone.** Its stored upstream is still under the old
  policy, which this build no longer declares, so it answers
  `UNSUPPORTED` and names the stage to run. Not a stale answer, and not
  a silent one.

The deterministic path to a current chain is therefore always the same:
**run the stages in order from the one whose policy changed.** There is
no automatic cascade, and the refusal is what makes its absence safe.

### What this changes about the original decision

The **rule** is unchanged: reuse requires a compatible upstream identity
and a compatible local contract. What changes is that a downstream layer
no longer *restates* what its upstream depends on. The "accepted cost" of
a growing copied prefix is withdrawn — the evidence is that the cost was
not the width but the drift.

The three supporting rules survive intact and are still enforced:
identity is copied from the upstream artifact and never supplied by a
caller; policy versions stay independent and are never raised to
invalidate something else; and unknown provenance is never compatible
provenance — a legacy artifact carries no identity, can never match a
lookup, and the stage below it refuses rather than deriving from a
provenance nobody can establish.

### The residual this closes, and the one it governs instead

The contract-version axis recorded above as a known residual
(`ENTITY_MODEL_VERSION`, `FACT_CONTRACT_VERSION`,
`SEMANTIC_CONTRACT_VERSION`) is now **closed**: each is part of its own
stage's local derivation identity.

One axis remains governed rather than encoded. Each catalogue's per-rule
`rule_version` feeds the row keys a stage produces, while the stage's
*policy* version is what its derivation identity names. The architecture
contract is that a policy version identifies the complete effective rule
catalogue. That is no longer left to discipline: the catalogue is
fingerprinted and pinned beside its policy version in
`tests/architecture/test_artifact_identity_architecture.py`, so changing
a rule without raising the policy fails the build and says so.

`GraphProvenance.pipeline_identity` remains descriptive-only debt, as
recorded above.

### Enforcement (as amended)

- `tests/architecture/test_artifact_identity_architecture.py` — the six
  persisted artifacts as an executable audit: identity columns, ports,
  uniqueness, no stage naming another stage's version, local identity
  completeness, catalogue fingerprints, kind separation, preimage
  determinism, the trust boundary, and the absence of fabricated
  provenance in migrations.
- `tests/services/test_artifact_identity_reuse.py` — the behavioural
  half: directional invalidation on every axis, same-input reuse, legacy
  refusal, and the governed location reading reaching Semantics.
- `tests/domain/test_artifact_identity.py` — the identity primitive
  itself.
- Migrations `c1f80d54ea27` (fact and semantic extraction provenance)
  and `e5a2f7b91c60` (the identity columns and constraints).
