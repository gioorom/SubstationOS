# Architecture Invariants

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

---

## The authoritative register — read this, not a summary

`docs/architecture/architecture_freeze_af01.md` **§20 "Architecture Fitness
Functions"** is the authoritative index of architecture invariants: a table
naming each invariant, its class, and **the test functions that prove it**.

**Every *hard* invariant is executable** — the freeze's own wording. The
proving tests are spread across `apps/backend/tests/architecture/`, not confined
to one file: some IDs appear directly in `test_architecture_freeze_af01.py`, the
rest are proven by per-context boundary tests that the register names. Do not conclude an invariant is unenforced
because it is absent from the AF-01 test file — look it up in the register.

Not every row is a guarantee. `AF-LLM-001` carries the class
`NON_GOAL_AT_FREEZE`: it records something deliberately *not* done, not
something protected. Read the class column before relying on a row.

The freeze status is **`FROZEN_WITH_KNOWN_DEBT`** (frozen as at EPIC 31.4). Debt
is itemised in **§21**, outside the frozen foundation.

Classes used in the register: `HARD`, `GOVERNANCE`, `BOUNDARY`,
`DETERMINISM`, `DATA`, `SECURITY`, `PROVENANCE`, `EVOLUTION_RULE` and
`NON_GOAL_AT_FREEZE`.

> **Never present an aspiration as executable protection.** If you need to rely
> on an invariant, open the register, find its row, and run the named test.

---

## Themes, and where to look

A navigation index only. The register is authoritative for the exact invariant
text and its proof.

### Dependency direction and domain purity

| Invariant | Why it exists | Proof |
|---|---|---|
| `AF-DEP-001` frozen dependency directions | The frozen direction set (`FROZEN_DIRECTIONS`); a reversed edge would let a lower layer depend on a decision made above it. | `test_af_dep_001_frozen_dependency_directions_hold` |
| `AF-DEP-002` acyclic domain graph | A cycle makes "which context owns this?" unanswerable. | `test_af_dep_002_the_domain_dependency_graph_is_acyclic` |
| Domain imports no ORM / SQLAlchemy | `CLAUDE.md` §3: the domain depends on nothing. | `test_domain_layer_does_not_import_sqlalchemy`, `test_domain_layer_does_not_import_persistence_models` |
| Per-context allowed imports | Each context enumerates exactly what it may reach. | `tests/architecture/test_<context>_boundaries.py` |

Affected: every domain context. Also see
[BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) § How dependencies are governed —
two complementary mechanisms, both must pass.

### Determinism

| Invariant | Why | Proof |
|---|---|---|
| `AF-DET-002` no deterministic context reaches an LLM | The risk is not that one context adopts an LLM — it is that one link does and the chain keeps its reputation. | `test_af_det_002_no_deterministic_context_reaches_an_llm` |

The context list is explicit in that test, so adding a context to the
deterministic core is a visible edit. It now includes `artifact_identity`.

### Truth versus judgement

| Invariant | Why | Proof |
|---|---|---|
| `AF-TRUTH-001` review writes no deterministic artefact | Judgement must not become truth by writing to it. | `test_af_truth_001_review_writes_no_deterministic_artefact` |
| `AF-TRUTH-002` the deterministic pipeline cannot read a review | A fact that could see a review would stop being reproducible from the document alone. | `test_af_truth_002_the_deterministic_pipeline_cannot_read_a_review` |

Enforced from both sides. Affected: `engineering_facts`,
`engineering_semantics`, `human_review`.

### Graph ownership and promotion

| Invariant | Why | Proof |
|---|---|---|
| `AF-KG-001` one runtime engineering graph | Two graphs would mean two answers. | `test_there_is_exactly_one_runtime_engineering_graph_context` |
| `AF-KG-002` no alternate knowledge path | Pipeline and review modules write no graph. | `test_no_pipeline_or_review_module_writes_any_graph` |
| `AF-KG-003` promotion is the only authoring authority | The sole *runtime* writer. The adapter implements the capability and migrations create the tables; neither is an authority. Asserted on the capability across `app/services/`, not on a filename. | `test_af_kg_003_...`, `test_only_the_promotion_service_writes_the_governed_graph`, `test_only_governed_promotion_authors_queryable_knowledge` |
| `AF-KG-004` the graph is a projection | It is rebuildable, not a source of truth (ADR-0024). | `test_af_kg_004_the_graph_is_reachable_only_as_a_projection` |
| `AF-KG-005..007` | One promotion rule definition; no ungoverned field; identity never taken from a label. | named in the register |

### Retrieval and context

| Invariant | Why | Proof |
|---|---|---|
| `AF-RET-001` retrieval has no write authority | The read port declares no write operation. | `test_the_read_port_declares_no_write_operation` |
| `AF-RET-002..005` | Never recomputes governance; no confidence score; no property bag; no query language. | named in the register |
| `AF-CTX-001..004` | Context assembly performs **no I/O** and owns budgeting/selection only. | named in the register |
| `AF-AMB-001` closed outcome vocabulary | Ambiguity is three-valued and closed. | `test_af_amb_001_the_match_outcome_vocabulary_is_closed` |
| `AF-AMB-002` outcome computed pre-limit | A limit must not change what the outcome *is*. | `test_af_amb_002_the_outcome_is_computed_before_any_limit` |

**Do not collapse retrieval and context.** Separate contexts, separate ADRs
(0026, 0027), separate invariant families.

### Provenance and trust boundary

| Invariant | Why | Proof |
|---|---|---|
| `AF-PROV-002` no persisting route accepts governed provenance | A caller must not be able to assert what the pipeline produced. | `test_af_prov_002_no_persisting_route_accepts_governed_provenance` |
| `AF-PROV-003` stateless composition routes persist nothing | | `test_af_prov_003_the_stateless_composition_routes_persist_nothing` |

### Reasoning separation

| Invariant | Why | Proof |
|---|---|---|
| `AF-REASON-001..004` | Reasoning is not the graph and cannot write it; a conclusion never claims to be governed; provenance survives into the response; conclusions are never persisted, so **no lifecycle was invented for them**. | `tests/architecture/test_engineering_reasoning_boundaries.py` — every `test_af_reason_*` function lives there, not in the AF-01 file, which only names the ids |

**Reasoning output is not approved knowledge.** No promotion path exists from a
conclusion to the graph; creating one is new architecture.

### Artifact identity and reuse coherency

Governed by `tests/architecture/test_artifact_identity_architecture.py` and
ADR-0032 (as amended), not by an AF-* identifier — this layer post-dates the
freeze.

| Invariant | Why | Proof (test function) |
|---|---|---|
| Every persisted artifact has identity columns | An artifact that cannot say what produced it cannot prove a reuse is valid. | `test_every_persisted_artifact_has_an_identity_column` |
| Reuse is an identity comparison | One comparison replaces a copied version prefix that drifted six times. | `test_every_service_decides_reuse_on_identity` |
| DB uniqueness equals application identity | A narrower constraint would forbid the row a change upstream must create. | `test_the_database_enforces_the_same_identity` |
| No stage names another stage's version | Everything upstream arrives through one upstream identity. | `test_no_stage_names_another_stages_version` |
| Local derivation identity is complete | Every version that can change what a stage persists is in its identity. | `test_each_stage_declares_every_version_it_owns` |
| Identity is deterministic and kind-separated | Length-prefixed preimage, declared field order, kind inside the digest. | `test_identity_is_deterministic_and_unambiguous`, `test_artifact_kinds_are_domain_separated` |
| No caller supplies an identity | Provenance is internal pipeline state. | `test_no_caller_can_supply_an_identity` |
| Unknown legacy identity is never current-compatible | `NULL` is not a value. | `test_unknown_legacy_identity_is_never_current_compatible` |
| No migration fabricates identity | A computed identity would assert a derivation never observed. | `test_no_migration_fabricates_an_identity` |
| The six boundaries are accounted for | A seventh persisted artifact must be a visible decision. | `test_no_persisted_reuse_boundary_is_unaccounted_for` |

### Rule-catalogue governance

`test_a_rule_version_change_cannot_hide_behind_its_policy` pins each of the four
rule catalogues (extraction, resolution, fact, semantic) by fingerprint beside
its policy version. **Changing a rule without raising its policy fails the
build**, with a message naming the fix. This converts a discipline into a
tripwire; it is not the same as encoding rule versions in the identity, and the
ADR says so.

### Engineering vocabulary is closed

Several fitness tests pin the exact members of `EntityType`, `FactPredicate`,
`SemanticStatementType`, `GraphNodeKind` and `GraphEdgeKind`, and assert that
hierarchy vocabulary (`PART_OF`, `CONTAINS`, `CHILD_OF`, …) stays **absent**.
Asserted in `test_designation_evidence_boundaries.py`,
`test_structural_relationship_boundaries.py` and
`test_structural_reasoning_boundaries.py`.
(`test_artifact_identity_architecture.py` pins the vocabularies as *unchanged
by the identity work*, which is a narrower claim.)

---

## Known debt

`architecture_freeze_af01.md` §21 is the authoritative list for the freeze.
Additional debt recorded in ADR-0032: `GraphProvenance.pipeline_identity` is
descriptive-only and omits the extraction policy.

Debt recorded elsewhere is listed in [README.md](README.md) § Discovered
documentation drift. **Do not fix debt as a side effect of another change** —
`CLAUDE.md` §12 requires refactoring to be separate and in scope.
