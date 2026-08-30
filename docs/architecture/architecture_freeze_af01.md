# Architecture Freeze AF-01 — Governed Engineering Knowledge Foundation

## 1. Status

**FROZEN_WITH_KNOWN_DEBT.**

Frozen as at EPIC 31.4. Every hard invariant below is executable; the
known debt (§21) is outside the frozen foundation and is classified
item by item.

This is an **as-built architecture contract**, not a milestone report. It
records what the repository *is*, converts its critical properties into
enforceable invariants, and states what a future milestone must do to
change one.

## 2. Scope

**In:** the governed engineering knowledge path from document to
Engineering Engine, its trust boundaries, its write authority, its
determinism and its provenance.

**Out:** Engineering Reasoning (EPIC 32 — its foundation shipped after
this freeze; see §18), UI, ontology growth, product
features. AF-01 adds no capability. It adds 13 architecture tests and
this document.

## 3. Architecture Baseline

Verified by inspection, not by documentation:

| Property | Evidence |
|---|---|
| 31 bounded contexts | `app/domain/*` |
| Domain dependency graph **acyclic** | DFS over real imports — `AF-DEP-002` |
| Domain purity **clean** | no domain module imports SQLAlchemy, FastAPI, Pydantic, `app.models`, `app.infrastructure`, `app.services`, `app.routers`, `app.schemas`, `app.database` or a provider SDK |
| One runtime engineering graph | `graph_contexts == ["governed_knowledge_graph"]` |
| One graph write authority | `knowledge_promotion_service.py` |
| Retrieval read port | 7 methods, **zero** write-shaped |
| Review port | `append` + 4 reads; no update, no delete |
| 100 served routes, 44 ORM tables | live route table / `Base.metadata` |
| 384 architecture tests | `tests/architecture/**` |

## 4. Bounded Context Map

Derived from runtime imports. `→` reads "depends on".

**Deterministic engineering pipeline** (establishes Engineering Truth)

```
document_identity → canonical_pdf → canonical_text → engineering_evidence
    → engineering_entities → engineering_facts → engineering_semantics
```

**Governance**

```
human_review        → shared_kernel        (depends on nothing else)
identity            → (leaf)
audit               → identity
```

**Governed knowledge**

```
governed_knowledge_graph → shared_kernel
governed_retrieval       → governed_knowledge_graph
context_builder          → governed_retrieval
prompt_builder           → context_builder, governed_retrieval
engineering_response     → context_builder, prompt_builder, governed_retrieval,
                           engineering_index
engineering_engine       → engineering_intent, engineering_response
```

**Retained source/history contexts** (§9 — *not* a knowledge graph)

```
proposed_claims  → engineering_index, project
review_workflow  → project
canonicalization → project, proposed_claims, review_workflow
retrieval_bridge → canonicalization, engineering_intent
```

**Leaves:** `document_identity`, `engineering_intent`, `identity`,
`ontology`, `shared_kernel`.

## 5. Authoritative Knowledge Path

```
Document
    ↓  document_ingestion, document_identity
Canonical Content
    ↓  canonical_pdf → canonical_text
Evidence
    ↓  engineering_evidence
Entities
    ↓  engineering_entities
Engineering Facts
    ↓  engineering_facts
Semantic Statements
    ↓  engineering_semantics
Governed Human Review
    ↓  human_review  (append-only judgement)
Governed Knowledge Graph
    ↓  knowledge_promotion_service  (the only authority)
Governed Structured Retrieval
    ↓  governed_retrieval  (read-only)
Governed Context Assembly
    ↓  context_builder  (no I/O)
Engineering Engine
```

**AF-PATH-001 — no layer may bypass an upstream trust boundary because
equivalent information appears available elsewhere.** Retrieval reads
`state`, not reviews. Context Assembly reads results, not tables. The
engine reads context, not the graph.

## 6. Trust Boundaries

| Boundary | Enforced by |
|---|---|
| anonymous → authenticated | deny-by-default middleware; `test_api_security` walks every path |
| authenticated → governed write | `promote_engineering_knowledge` capability, separate from `record_engineering_review` |
| caller data → governed provenance | **AF-PROV-002** |
| deterministic truth → human judgement | **AF-TRUTH-001 / 002** |
| governed knowledge → derived inference | **AF-REASON-001** (forward) |
| LLM output → engineering knowledge | **AF-LLM-001** |

## 7. Data Ownership

| Data | Authoritative owner | Writers | Readers | Derived | Mutability | Provenance |
|---|---|---|---|---|---|---|
| Documents | Document Registry | ingestion | pipeline, workspace | No | mutable metadata | source |
| Canonical content | Canonicalization pipeline | pipeline stages | evidence, workspace | **Yes** (from bytes) | replace-on-rerun | checksum |
| Evidence | Engineering Evidence | pipeline | entities, evaluation | **Yes** | replace-on-rerun | spans |
| Entities | Engineering Entities | pipeline | facts, promotion | **Yes** | replace-on-rerun | evidence |
| Engineering Facts | Engineering Facts | pipeline | semantics | **Yes** | replace-on-rerun | support chain |
| Semantic Statements | Engineering Semantics | pipeline | review, promotion | **Yes** | replace-on-rerun | fact keys + rule version |
| Human Reviews | Human Review | review service | promotion, workspace | **No** | **append-only** | reviewer + snapshot |
| Governed graph | Governed KG | **promotion only** | retrieval, API | **Yes — rebuildable** | projection | mandatory, non-null |
| Retrieval results | Governed Retrieval | **none** | context assembly | **Yes** | transient | inherited |
| Context packages | Context Assembly | **none** | prompt, response | **Yes** | transient | inherited |
| Reasoning conclusions | EPIC 32.1 / `ReasoningResult` | derived, never persisted | — | — | — | **required — `ReasoningContributor` carries the full governed chain (AF-REASON-002)** |
| Engineering Response | Engineering Response | response service | session, conversation | **Yes** | transient | citations |
| Audit events | Audit | audit service | audit API | **No** | **append-only** | actor identity |
| `canonical_facts` etc. | Canonicalization / Review Workflow | their services | their APIs | **No** | mutable | human-authored |

## 8. Write Authority

| Resource | Allowed writer | Everything else |
|---|---|---|
| Documents | `document_ingestion_service`, `document_registry_service` | forbidden |
| Canonical content | pipeline stage services | forbidden |
| Evidence / entities / facts / semantics | their pipeline services | forbidden |
| **Human Reviews** | `human_review_service` (append) | forbidden |
| **Governed KG** | **`knowledge_promotion_service`** | forbidden — `AF-KG-003` |
| Governed Retrieval | **NONE** | port has no write method — `AF-RET-001` |
| Context Assembly | **NONE** | performs no I/O — `AF-CTX-002` |
| Reasoning conclusions | **EPIC 32.1: nobody — they are never persisted, so no lifecycle was invented** | is not the graph, and cannot write it (AF-REASON-003) |
| Audit | `audit_service` | forbidden |

## 9. Dependency Direction

Frozen directions, each with a recorded reason in
`test_architecture_freeze_af01.FROZEN_DIRECTIONS`:

| Must not depend on | | Why |
|---|---|---|
| `human_review` | `governed_retrieval`, `context_builder` | judgement must not be written for what a query can find |
| `governed_knowledge_graph` | `governed_retrieval`, `context_builder` | the projection must not know how it is read |
| `governed_retrieval` | `context_builder` | context must not influence matching |
| `context_builder` | `engineering_response` | context precedes the answer |
| `engineering_facts` | `human_review`, `engineering_engine` | **truth must not depend on judgement** |
| `engineering_semantics` | `human_review`, `engineering_engine` | same, for meaning |

Composition roots (`app/routers/**`, `services/engineering_engine/composition.py`)
may reference concretes from any layer; that is dependency *injection*,
not domain dependency, and is excluded by construction — the graph is
computed over `app/domain/**` only.

## 10. Governance Model

```
Semantic Statement  +  current review APPROVED  +  applicability APPLIES
        ↓
knowledge_promotion_service.promote / promote_document / rebuild
        ↓
Governed Knowledge Graph  (ACTIVE)
```

`promotion_rules.evaluate` is the **single** definition of promotability;
incremental promotion and full rebuild both call it, so they cannot
disagree. `ReviewDecision` is closed at three values —
`APPROVED`, `REJECTED`, `NEEDS_INVESTIGATION` — and `ReviewApplicability`
at three: `APPLIES`, `REQUIRES_REVALIDATION`, `ORPHANED`.

## 11. Provenance Model

```
Context Item → Governed Retrieval Result → governed graph object
    → statement_key → review_id → support_fingerprint → document_id
```

Every link is an **identity**, never a payload copy. `GraphProvenance`
raises at construction if any field is missing; the columns are
`nullable=False`; `GovernedRetrievalItem.provenance` and
`ContextItem.result.provenance` have no default and no `| None`.

**Provenance is never caller-asserted** — AF-PROV-002/003.

## 12. Determinism Model

| Stage | Deterministic | Versioned | Stable identity | Wall clock | Random | Rebuildable |
|---|---|---|---|---|---|---|
| Canonical PDF / text | Yes | `CANONICAL_*_VERSION` | content hash | metadata only | No | Yes |
| Evidence / entities / facts | Yes | `EXTRACTION_/RESOLUTION_/FACT_POLICY_VERSION` | deterministic keys | metadata only | No | Yes |
| Semantics | Yes | `SEMANTIC_POLICY_/CONTRACT_VERSION` | `statement_key` | metadata only | No | Yes |
| Human Review | Yes (append) | `REVIEW_RECORD_VERSION` | review id | **`recorded_at` is engineering-relevant** | No | No — source |
| Promotion | Yes | `PROMOTION_CONTRACT_VERSION` | SHA-256 of governed keys | **`created_at` = review's `recorded_at`, not the clock** | No | **Yes** |
| Retrieval | Yes | `GOVERNED_NORMALIZATION_/MATCHING_POLICY_VERSION` | `result_id` | `duration_seconds` only | No | Yes |
| Context Assembly | Yes | `CONTEXT_ASSEMBLY_/SELECTION_/BUDGET_POLICY_VERSION` | `item_id` | `assembled_at` only | No | Yes |
| LLM invocation | **No** | runtime + adapter versions | correlation id | Yes | retry jitter | No |

Engineering **output** determinism is distinguished from operational
metadata: `duration_seconds` and `assembled_at` vary and are excluded
from every identity.

## 13. Identity Model

| Identity | Determined by | Survives rebuild | New identity when |
|---|---|---|---|
| `content_checksum` | document bytes | n/a | bytes change |
| `entity_key` / `fact_key` | pipeline hash over source + rules | n/a | rules or bytes change |
| `statement_key` | document + fact source + triple + rule versions | n/a | any of those change |
| `node_id` | `sha256(namespace ∥ kind ∥ entity_key)` | **Yes** | kind or entity key changes |
| `edge_id` | `sha256(namespace ∥ kind ∥ statement_key)` | **Yes** | kind or statement key changes |
| `result_id` | result kind + node/edge id (+ edge for traversal) | **Yes** | governed identity changes |
| `item_id` | `result_id` | **Yes** | as above |

**Identity is never derived from a label.** `TR1` in two documents is two
`entity_key`s, therefore two `node_id`s, therefore two answers.

## 14. Versioning Model

Bounded versions, not a global one. Each is owned by the context that
can change the behaviour it describes: 40+ constants across
`app/domain/**/[a-z]*_policy.py`. A material behavioural change must be
identifiable through the appropriate version; introducing a global
version number would make every context's change look like everyone's.

## 15. Retrieval Contract

Read-only. Five typed queries (`ASSET_BY_DESIGNATION`,
`QUANTITY_FOR_ASSET`, `RELATIONSHIPS`, `DOCUMENT_KNOWLEDGE`,
`GOVERNED_IDENTITY`); eight match strategies with total precedence;
three deterministic folds; `CURRENT_ONLY` default scope; no score, no
property bag, no collation-dependent semantics, no query language.

Retrieval must not approve, reject, promote, recompute review
eligibility, invent relationships, mutate, infer, or read a retired
store.

## 16. Context Assembly Contract

Deterministic organisation of already-retrieved governed knowledge.

**May:** select, group, deduplicate *by governed identity*, apply
deterministic limits, package provenance, emit diagnostics.

**Must not:** retrieve, write, review, promote, infer, collapse
ambiguity, invent provenance. It performs **no I/O** — which is what
prevents it widening the scope retrieval applied.

## 17. Engineering Engine Contract

Consumer of governed context. No fallback exists to legacy retrieval,
raw graph queries, Canonical Facts, raw proposed claims, unreviewed
statements or raw LLM extraction — the packages are deleted, so the
fallback is not merely unwired but unavailable.

## 18. Engineering Reasoning Contract (EPIC 32)

> **Discharged in part by EPIC 32.1.** AF-REASON-001, AF-REASON-002 and
> AF-REASON-003 were forward requirements when AF-01 was written; the
> first reasoning capability now exists, and all three are enforced by
> executing fitness functions in
> `tests/architecture/test_engineering_reasoning_boundaries.py`. See
> [ADR-0029](adr/0029-deterministic-engineering-reasoning-foundation.md)
> and [engineering_reasoning.md](engineering_reasoning.md).
>
> **No invariant below was weakened, bypassed, renamed away or
> reinterpreted.** AF-DEP-001 gained six frozen directions involving
> `engineering_reasoning`, and AF-DET-002's deterministic core gained
> `engineering_reasoning` as an eleventh context — both additions, not
> relaxations.

**May:** consume governed knowledge and context; derive explicit
reasoning artefacts; produce conclusions with provenance; represent
uncertainty, conflict and insufficiency.

**Must not:** promote conclusions into the governed graph; rewrite facts
or statements; fabricate a review; convert inference into reviewed fact;
hide ambiguity; create a second knowledge graph; make probabilistic
retrieval authoritative.

**AF-REASON-001 — fact ≠ inference.** A reasoning conclusion must be
structurally distinguishable from a governed statement. The system must
be able to answer *"what did the documents and the reviewer establish?"*
separately from *"what did the engine infer?"*

**AF-REASON-002 — reasoning provenance.** Every material conclusion must
be traceable to its governed inputs and its reasoning rule and version:

```
Conclusion → rule/version → governed context/retrieval inputs
    → governed graph objects → statements → review → evidence → document
```

**AF-REASON-003.** Any reasoning output that later becomes persistent
engineering knowledge requires an explicit governance lifecycle,
designed then, not assumed now.

**As implemented (EPIC 32.1).** No reasoning output becomes persistent
engineering knowledge, so no governance lifecycle was needed and none
was invented. Reasoning is enforced to be *incapable* of persistence:
the whole reasoning surface imports no repository, no session, no
promotion service, no Human Review module and no graph port, and the
engine step handler declares no `__init__`, so it is constructed with
nothing at all. `knowledge_promotion_service` remains the single
graph-authoring authority (AF-KG-003, unchanged), and an end-to-end test
asserts the governed graph is byte-identical across an execution that
concluded `INCONSISTENT`.

## 19. Retired Architecture Tombstones

Retired and not to be reintroduced into authoritative runtime without an
ADR superseding AF-01:

| Retired | By |
|---|---|
| `knowledge_graph.py`, `project_entities`, `entity_relations` | EPIC 31.1 / ADR-0025 |
| `graph_builder`, `project_knowledge_graph`, `graph_query`, legacy `structured_retrieval` | EPIC 31.4 / ADR-0028 |
| Canonical Facts graph-shaped projection (7 tables) | EPIC 31.4 / migration `f4a90c27b615` |
| `governed_context_projection.py` | EPIC 31.3 / ADR-0027 |

These names legitimately appear in historical migrations, ADRs, retired
documentation and in tests that assert their absence. **Tests must
distinguish a historical reference from a runtime dependency** — the
string `structured_retrieval` is not banned, because
`governed_structured_retrieval` is the current implementation.

## 20. Architecture Fitness Functions

| Invariant | Class | Enforcing test |
|---|---|---|
| **AF-KG-001** one runtime engineering graph | HARD | `test_there_is_exactly_one_runtime_engineering_graph_context` |
| **AF-KG-002** no alternate knowledge path | HARD | `test_no_pipeline_or_review_module_writes_any_graph` |
| **AF-KG-003** promotion is the only authoring authority | GOVERNANCE | `test_af_kg_003_promotion_is_the_only_graph_authoring_authority`, `test_only_governed_promotion_authors_queryable_knowledge` |
| **AF-KG-004** the graph is a projection | DATA | `test_af_kg_004_the_graph_is_reachable_only_as_a_projection` |
| **AF-KG-005** one promotion rule definition | GOVERNANCE | `test_the_promotion_rule_has_exactly_one_definition` |
| **AF-KG-006** no ungoverned field on the graph | DATA | `test_the_graph_tables_carry_no_ungoverned_field` |
| **AF-KG-007** identity never from a label | DATA | `test_identity_is_derived_and_never_taken_from_a_label` |
| **AF-REV-001** reviews are append-only | GOVERNANCE | `test_the_review_port_declares_no_mutating_operation`, `test_the_review_repository_issues_no_update_or_delete` |
| **AF-REV-002** a review is immutable | GOVERNANCE | `test_a_review_is_an_immutable_value` |
| **AF-REV-003** closed decision vocabulary | GOVERNANCE | `test_the_decision_vocabulary_is_not_extensible_at_a_call_site` |
| **AF-TRUTH-001** review writes no deterministic artefact | HARD | `test_af_truth_001_review_writes_no_deterministic_artefact` |
| **AF-TRUTH-002** the pipeline cannot read a review | HARD | `test_af_truth_002_the_deterministic_pipeline_cannot_read_a_review` |
| **AF-TRUTH-003** promotion modifies no artefact | GOVERNANCE | `test_promotion_changes_no_engineering_artefact` |
| **AF-RET-001** retrieval has no write authority | HARD | `test_the_read_port_declares_no_write_operation`, `test_no_retrieval_module_can_write_a_graph_projection` |
| **AF-RET-002** retrieval never recomputes governance | GOVERNANCE | `test_retrieval_never_recomputes_review_eligibility` |
| **AF-RET-003** no confidence score | DETERMINISM | `test_retrieval_carries_no_confidence_score_or_weight` |
| **AF-RET-004** no property bag | DETERMINISM | `test_no_property_bag_reaches_the_governed_retrieval_path` |
| **AF-RET-005** no query language | SECURITY | `test_no_graph_query_language_is_imported_or_implemented` |
| **AF-AMB-001** closed three-valued outcome | HARD | `test_af_amb_001_the_match_outcome_vocabulary_is_closed` |
| **AF-AMB-002** outcome computed pre-limit | HARD | `test_af_amb_002_the_outcome_is_computed_before_any_limit` |
| **AF-CTX-001** assembly consumes governed retrieval | BOUNDARY | `test_the_temporary_context_projection_is_gone`, `test_no_module_projects_governed_results_into_candidates` |
| **AF-CTX-002** assembly performs no I/O | HARD | `test_context_assembly_reads_nothing_for_itself` |
| **AF-CTX-003** assembly performs no governance | GOVERNANCE | `test_context_assembly_never_recomputes_governance` |
| **AF-CTX-004** no property bag in context | DETERMINISM | `test_context_assembly_holds_no_property_bag` |
| **AF-PROV-001** graph provenance is mandatory | PROVENANCE | `test_every_graph_object_carries_its_provenance` |
| **AF-PROV-002** persisting routes reject caller provenance | HARD | `test_af_prov_002_no_persisting_route_accepts_governed_provenance` |
| **AF-PROV-003** composition routes persist nothing | HARD | `test_af_prov_003_the_stateless_composition_routes_persist_nothing` |
| **AF-DEP-001** frozen dependency directions | BOUNDARY | `test_af_dep_001_frozen_dependency_directions_hold` |
| **AF-DEP-002** acyclic domain graph | BOUNDARY | `test_af_dep_002_the_domain_dependency_graph_is_acyclic` |
| **AF-DEP-003** domain imports no infrastructure | BOUNDARY | `test_*_domain_imports_no_infrastructure` (per context) |
| **AF-DET-001** semantics reaches no LLM | DETERMINISM | `test_the_semantic_layer_cannot_import_the_llm_runtime` |
| **AF-DET-002** the whole deterministic core reaches no LLM | HARD | `test_af_det_002_no_deterministic_context_reaches_an_llm` |
| **AF-ENG-001** engine has no legacy fallback | HARD | `test_the_engine_no_longer_wires_the_legacy_graph_repository`, `test_no_engine_module_imports_legacy_retrieval` |
| **AF-ENG-002** engine reaches the LLM only via the neutral runtime | BOUNDARY | `test_engine_reaches_the_llm_only_through_the_neutral_runtime` |
| **AF-LEG-001** retired lineage absent from runtime | HARD | `test_no_retired_lineage_package_survives_anywhere_in_runtime`, `test_no_runtime_module_imports_the_retired_lineage` |
| **AF-LEG-002** no retired route served | HARD | `test_no_route_serves_the_retired_lineage` |
| **AF-LEG-003** no retired ORM table | DATA | `test_the_retired_graph_tables_are_not_in_the_orm_metadata` |
| **AF-SEC-001** deny by default | SECURITY | `tests/api/test_api_security.py` |
| **AF-SEC-002** no storage field on a public schema | SECURITY | `test_no_public_schema_declares_a_storage_field` |
| **AF-SEC-003** no arbitrary filter/sort | SECURITY | `test_sort_fields_are_closed_enums_not_strings`, `test_the_retrieval_api_accepts_no_arbitrary_filter` |
| **AF-EVO-001** this document exists and matches | EVOLUTION_RULE | `test_af_evo_001_the_freeze_document_exists` |
| **AF-LLM-001** LLM output is not authoritative | NON_GOAL_AT_FREEZE | §23 — no LLM output reaches any authoritative store; enforced by AF-DET-002 + AF-KG-003 |
| **AF-REASON-001** fact ≠ inference | HARD | `test_af_reason_001_a_result_is_a_type_of_its_own`, `test_af_reason_001_a_conclusion_never_claims_to_be_governed`, `test_af_reason_001_the_response_keeps_reasoning_out_of_evidence` |
| **AF-REASON-002** reasoning provenance | PROVENANCE | `test_af_reason_002_a_result_names_its_rule_and_version`, `test_af_reason_002_every_contributor_carries_governed_provenance`, `test_af_reason_002_provenance_survives_into_the_response` |
| **AF-REASON-003** no auto-promotion | HARD | `test_af_reason_003_reasoning_imports_nothing_that_can_write`, `test_af_reason_003_reasoning_imports_no_graph_repository`, `test_af_reason_003_the_reasoning_step_handler_holds_no_dependency`, `test_af_reason_003_the_reasoning_service_opens_no_session`, `test_reasoning_promotes_nothing_into_governed_knowledge` |
| **AF-REASON-004** reasoning is deterministic | DETERMINISM | `test_reasoning_reads_no_clock`, `test_the_result_identity_is_a_pure_function_of_governed_material`, `test_the_outcome_vocabulary_is_four_valued_and_closed`, `test_no_confidence_or_score_anywhere_in_reasoning` |

## 21. Known Technical Debt

| Debt | Affects the frozen foundation? |
|---|---|
| Project-level authorization is filtering, not enforcement | **No** — orthogonal to the knowledge invariants; any authenticated engineer may read any project, unchanged since EPIC 30.3 |
| `analysis.entities_found` always `0` | **No** — a response field surviving its cause |
| `scripts/benchmarks` imports one governed fixture from `tests/**` | **No** — a benchmark, contrary to its own docstring; not runtime |
| No cross-document entity resolution | **No** — an explicit stated limit; AF-AMB-001 depends on it being absent |
| Rebuild is synchronous and unbounded | **No** — operational |
| Governed graph is unversioned per project | **No** — one global generation |

None blocks the freeze.

## 22. Change / Supersession Policy

**Does not supersede AF-01** — ordinary evolution: a new semantic rule; a
new governed node or edge kind whose rule exists; a new typed governed
query; a new context diagnostic; a new workflow; UI work; performance
work.

**Requires an ADR naming the AF-01 invariant it changes:**

- introducing a second authoritative knowledge graph *(AF-KG-001)*;
- letting anything but governed promotion author graph knowledge, including reasoning *(AF-KG-003)*;
- making unreviewed semantics authoritative *(AF-KG-002)*;
- making retrieval probabilistic and authoritative *(AF-RET-003)*;
- accepting caller-asserted provenance on a persisting route *(AF-PROV-002)*;
- merging Human Review into the deterministic pipeline, either direction *(AF-TRUTH-001/002)*;
- collapsing `MULTIPLE_MATCHES` *(AF-AMB-001)*;
- introducing an LLM into the deterministic core *(AF-DET-002)*.

The ADR must name the invariant, state why the property is no longer
worth protecting, and update or delete its fitness function in the same
change. **A fitness function must never be deleted without an ADR** — an
architecture test removed quietly is an architecture decision reversed
quietly.
