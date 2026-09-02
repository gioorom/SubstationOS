# Bounded Contexts

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

All paths are under `apps/backend/`. A context is typically spread across
`app/domain/<name>/` (meaning + ports), `app/services/` (orchestration),
`app/infrastructure/<name>/` (adapters), `app/models/<name>.py` (tables) and
`app/routers/<name>.py` (HTTP) — but **the naming is not mechanical**: several
services and boundary tests use the singular of a plural package
(`engineering_entities` → `engineering_entity_service.py`,
`test_engineering_entity_boundaries.py`), `identity` is served by
`user_service.py` and `authentication_service.py`, and some packages have no
service or no router at all. Glob for the stem rather than assuming the
filename.

## A word on "bounded context"

`app/domain/` holds **33 packages**. The repository does **not** anywhere
enumerate a definitive list of its bounded contexts: `CLAUDE.md` §4 requires
them to be explicit and names `ontology` as the reference pattern every new
context should imitate (§4.3), and
`tests/architecture/test_bounded_context_dependencies.py` governs a *subset* by
name. Neither is a complete register.

So this document uses **domain package** for the inventory and assigns each one
a **navigation category** — a statement about where to look, not a formal DDD
claim. Where a package's status is genuinely a judgement call, it is said so.

### Inventory — every package, exactly once

| Navigation category | Packages |
|---|---|
| **Deterministic derivation context** — persists one artifact, is a reuse boundary | `canonical_pdf`, `canonical_text`, `engineering_evidence`, `engineering_entities`, `engineering_facts`, `engineering_semantics` |
| **Shared domain primitive** — no persistence, no ports, consumed by others | `artifact_identity`, `shared_kernel` |
| **Governance context** | `human_review`, `governed_knowledge_graph` |
| **Reading / assembly context** | `governed_retrieval`, `context_builder` |
| **Reasoning context** | `engineering_reasoning` |
| **Answering-path context** | `engineering_intent`, `retrieval_bridge`, `prompt_builder`, `engineering_response`, `engineering_engine` |
| **Session / conversation context** | `conversation`, `engineering_session`, `working_memory` |
| **Document lifecycle context** | `document_registry`, `document_ingestion`, `document_identity` |
| **Pre-governed-graph surface** — active, predates the governed graph | `canonicalization`, `engineering_index`, `proposed_claims`, `review_workflow` |
| **Platform context** | `project`, `identity` |
| **Reference-data context** | `ontology` |
| **Cross-cutting / measurement** | `audit`, `evidence_evaluation` |

AF-01's `DETERMINISTIC_CONTEXTS` — the set that **may reach no LLM** — is
the six derivation contexts plus `artifact_identity`, `human_review`,
`governed_knowledge_graph`, `governed_retrieval`, `context_builder` and
`engineering_reasoning`. `shared_kernel` is a primitive but is **not** in that
frozen set.

**`artifact_identity` is a shared domain primitive, not a derivation stage.**
It is deterministic and in that frozen set, but it persists nothing, declares no
repository port, and has no service, model or router. It is **not** a seventh
persisted reuse boundary — see [§ Artifact identity](#artifact-identity--cross-reference).

`shared_kernel` is thinner still: pagination primitives only.

---

## How dependencies are governed

Two complementary mechanisms, both executable. Check both before adding an
import.

1. **`ALLOWED_DOMAIN_DEPENDENCIES`** — a per-context whitelist in
   `tests/architecture/test_bounded_context_dependencies.py`, covering a
   **subset** of packages by name. A context whose directory is absent is
   skipped, so retired names still appear there harmlessly (see README drift
   item 2).
2. **Per-context boundary tests** — `tests/architecture/test_*_boundaries.py`,
   each enumerating exactly what one context may import. This is how most of the
   deterministic pipeline is governed. The two mechanisms overlap rather than
   partition: `context_builder` and `engineering_reasoning`, for instance, are
   whitelist keys *and* have boundary tests, while the six derivation stages are
   governed by boundary tests alone.

On top of both, **AF-01** freezes a set of forbidden direction pairs
(`FROZEN_DIRECTIONS`) and asserts the domain dependency graph is acyclic
(`tests/architecture/test_architecture_freeze_af01.py`, AF-DEP-001/002).

---

# The deterministic pipeline

The six stages in this section each persist one artifact keyed on
`(document_id, artifact_identity)`, and each is one of the six reuse
boundaries. They are listed here in derivation order.

`artifact_identity` is described first because everything below depends on it —
but it is a **shared primitive, not a stage**, and persists nothing.

## artifact_identity *(shared primitive — not a derivation stage)*

**Purpose.** The primitive every deterministic stage composes its identity
with. Knows canonicalisation, hashing and artifact kinds — and nothing about
engineering.

- **Owns:** `ArtifactIdentity`, `ArtifactKind`, `derive_identity()`,
  `source_identity()`, `ARTIFACT_IDENTITY_CONTRACT_VERSION`.
- **Does not own:** any engineering meaning, any persistence, any policy that
  versions a rule catalogue.
- **Depends on:** nothing but the standard library.
- **Consumed by:** all six pipeline stages.
- **Files:** `app/domain/artifact_identity/artifact_identity_{models,builder,policy,exceptions}.py`
- **Tests:** `tests/domain/test_artifact_identity.py` ·
  `tests/architecture/test_artifact_identity_architecture.py`
- **ADR:** 0032 (as amended). **Before changing:** read the amendment first — the
  contract version is a re-identification event, never a cache-buster.

## canonical_pdf

- **Purpose.** Parse source bytes into a canonical representation.
- **Owns:** the representation value hierarchy (document → pages → blocks →
  spans), `CANONICAL_REPRESENTATION_VERSION`, `representation_identity()`.
- **Does not own:** text segmentation, OCR (there is none), engineering meaning.
- **Upstream:** stored document bytes (via `DocumentContentPort`). **Downstream:** canonical_text.
- **Ports:** `canonical_representation_repository.py` (`find_by_identity`,
  `find_latest_for_document`, `save`), `pdf_parser_port.py` (exposes
  `parser_name`/`parser_version` — both are identity inputs).
- **Persistence:** `app/models/canonical_pdf.py`, four tables.
- **Tests:** `tests/architecture/test_canonical_pdf_boundaries.py` ·
  `tests/services/test_canonical_pdf_service.py`
- **Before changing:** a parser upgrade changes every downstream identity. That
  is intended.

## canonical_text

- **Purpose.** Segment a representation into pages/paragraphs/lines/tokens.
- **Owns:** the segmentation contract, `CANONICAL_SEGMENTATION_VERSION`,
  `segmentation_identity()`, normalization.
- **Upstream:** canonical_pdf. **Downstream:** engineering_evidence.
- **Special:** the only stage that **reconstructs its upstream's identity** from
  the representation's own immutable columns — the `RECONSTRUCT_UPSTREAM` case in
  ADR-0032. A mismatch against a stored identity is refused as corruption.
- **Tests:** `tests/architecture/test_canonical_text_boundaries.py` ·
  `tests/services/test_canonical_text_service.py`

## engineering_evidence

- **Purpose.** Observe designations, quantities and location aspects in canonical
  text, with character-level provenance.
- **Owns:** `EvidenceType`, the extraction rule catalogue (`evidence_rules.py`,
  `evidence_patterns.py`), units and quantities, `EXTRACTION_POLICY_VERSION`.
- **Does not own:** what an observation *is* (that is an entity), or any
  classification of equipment.
- **Upstream:** canonical_text. **Downstream:** engineering_entities.
- **Grammar constraints (verified in code):** dot-qualified designations such as
  `-E1.L` are **one atomic designation** — the dot is lexical, creates no
  hierarchy, and a fitness function forbids splitting on it. A standalone
  `+GSH002` is a location aspect, not equipment. `SF6` is a *measured* false
  positive, deliberately not suppressed.
- **Tests:** `tests/architecture/test_engineering_evidence_boundaries.py` ·
  `tests/architecture/test_designation_evidence_boundaries.py` ·
  `tests/domain/test_real_designation_evidence.py`
- **Before changing:** the reference corpus
  (`app/domain/evidence_evaluation/corpora/substation_reference.yaml`) measures
  precision/recall; raising a rule version requires raising
  `EXTRACTION_POLICY_VERSION` or the build fails.

## engineering_entities

- **Purpose.** Group observations that refer to the same object, within one
  document.
- **Owns:** `EntityType` (`equipment_designation`, `engineering_quantity`,
  `structural_location`), the resolution rule catalogue,
  `RESOLUTION_POLICY_VERSION`, `ENTITY_MODEL_VERSION`.
- **Does not own:** equipment classification, cross-document identity, or any
  relationship between entities.
- **Tests:** `tests/architecture/test_engineering_entity_boundaries.py`

## engineering_facts

- **Purpose.** Associate entities under governed construction rules.
- **Owns:** `FactPredicate` (`has_associated_quantity`, `has_location_aspect`),
  `fact_construction_rules.py`, `FACT_POLICY_VERSION`, `FACT_CONTRACT_VERSION`.
- **Does not own:** the meaning of an association.
- **Constraint:** `HAS_LOCATION_ASPECT` is produced by two rules — TOKEN-scoped
  `compound_reference_designation`, and LINE-scoped `same_line_location_association`
  (EPIC 32.P2), which requires exactly one designation and one location written as
  distinct tokens. There is **no** equipment-to-equipment hierarchy — no `PART_OF`,
  `CONTAINS`, `CHILD_OF` — and a fitness function asserts that vocabulary stays
  absent.
- **Tests:** `tests/architecture/test_engineering_fact_boundaries.py`

## engineering_semantics

- **Purpose.** Assign governed meaning to facts.
- **Owns:** `SemanticStatementType` (`has_rated_power`, `is_located_in`),
  `semantic_rules.py`, `SEMANTIC_POLICY_VERSION`, `SEMANTIC_CONTRACT_VERSION`.
- **`IS_LOCATED_IN`** represents governed reference-designation structural-location
  semantics (ADR-0030). It is **not** independently verified physical
  containment; do not describe or extend it as such.
- **Downstream:** human_review (judgement), then promotion.
- **Tests:** `tests/architecture/test_engineering_semantic_boundaries.py` ·
  `tests/architecture/test_structural_relationship_boundaries.py`

---

# Governance

## human_review

- **Purpose.** Record human judgement about semantic statements. **Append-only**
  (ADR-0023).
- **Owns:** review decisions, `ReviewSnapshot` (the upstream identity at review
  time), `ReviewApplicability` (`APPLIES` / `REQUIRES_REVALIDATION` /
  `ORPHANED`), review events and projection.
- **Does not own:** any deterministic artefact. AF-TRUTH-001 asserts review
  writes none; AF-TRUTH-002 asserts the deterministic pipeline cannot read one.
- **Applicability is decided by whether the reviewed `statement_key` is present
  in the *current* semantic set** — not by comparing version tuples. A
  recomputation that changes a statement's identity yields
  `REQUIRES_REVALIDATION`; **a review is never discarded and never
  auto-migrated.**
- **Tests:** `tests/architecture/test_human_review_boundaries.py` ·
  `tests/domain/test_human_review_domain.py`

## governed_knowledge_graph *(with `knowledge_promotion_service`, an application service)*

- **Purpose.** A **rebuildable projection** of approved semantic statements
  (ADR-0024) — not a source of truth.
- **Owns:** `GraphNodeKind` (`engineering_asset`, `engineering_quantity`,
  `structural_location`), `GraphEdgeKind` (`has_rated_power`, `is_located_in`),
  graph identity, provenance, generations, lifecycle, promotion rules.
- **Authorized runtime write ownership** runs through one chain:

  ```
  approved semantic statement
        -> knowledge_promotion_service        the only authorized runtime writer
        -> GovernedGraphRepository            the write port (upsert_node,
                                              upsert_edge, record_generation, clear)
        -> SqlAlchemyGovernedGraphRepository  the persistence adapter
  ```

  The adapter *implements* the write capability and the migrations *create* the
  tables — neither is a runtime authority. `app/routers/governed_knowledge_graph.py`
  constructs the adapter and hands it to promotion; it calls no write method
  itself, so an ordinary API caller cannot bypass promotion.

  Retrieval reads the same tables through a **separate read-only port**
  (`GovernedKnowledgeReader`), whose adapter issues only `select(...)`. Context,
  reasoning and human review reach no graph write path at all.

  Proven by AF-KG-003 (asserted on the *capability* across `app/services/`, not
  on a filename), AF-KG-004, and
  `tests/architecture/test_graph_consolidation.py`
  (`test_only_the_promotion_service_writes_the_governed_graph`,
  `test_no_pipeline_or_review_module_writes_any_graph`,
  `test_only_governed_promotion_authors_queryable_knowledge`).
- **Known debt:** `GraphProvenance.pipeline_identity` is descriptive-only and
  omits the extraction policy (recorded in ADR-0032).
- **Tests:** `tests/architecture/test_governed_graph_boundaries.py` ·
  `tests/architecture/test_graph_consolidation.py`

---

# Reading path

## governed_retrieval

- **Purpose.** Answer questions about stored governed knowledge. **Read-only** —
  the reader port exposes only `nodes`, `edges`, `find_node`, `find_edge`,
  `latest_generation` and similar.
- **Owns:** match policy, ambiguity outcomes (a closed vocabulary, AF-AMB-001),
  result assembly and identity, normalization.
- **Never infers.** The outcome is computed before any limit is applied
  (AF-AMB-002).
- **Tests:** `tests/architecture/test_governed_retrieval_boundaries.py`

## context_builder

- **Purpose.** Select, budget and assemble what retrieval returned into a context
  package (ADR-0027).
- **Owns:** budget policy and enforcement, item selection, coverage analysis,
  warnings, statistics, context metadata.
- **Performs no I/O** and reaches no AI/vector dependency — asserted in
  `test_bounded_context_dependencies.py`
  (`test_context_builder_does_not_import_forbidden_modules`,
  `test_context_builder_surface_has_no_ai_or_vector_dependency`). This context has no
  boundary test file of its own; the AF-CTX-* invariants are proven by the tests
  the freeze register names.
- **Do not collapse retrieval and context.** They are separate contexts with
  separate ADRs (0026, 0027).

## prompt_builder → engineering_engine / engineering_response

The answering path. `prompt_builder` renders context; `engineering_engine`
(ADR-0020) and `engineering_response` (ADR-0015) produce the answer.
`engineering_intent` classifies the request (ADR-0019). These may reach an LLM —
they are outside `DETERMINISTIC_CONTEXTS`.

## engineering_reasoning

- **Purpose.** Deterministic reasoning over **governed** knowledge (ADR-0029).
- **Owns:** two rules today — `quantity_consistency_rule.py` and
  `shared_structural_location_rule.py` (ADR-0031) — plus reasoning vocabulary,
  outcomes, identity and policy.
- **Consumes:** `context_builder`, `governed_retrieval`,
  `governed_knowledge_graph`.
- **Persists nothing.** There is no reasoning ORM model. Conclusions are
  computed and returned; **nothing makes a conclusion governed knowledge**, and
  no promotion path from reasoning exists. Creating one would be new
  architecture.
- **In `DETERMINISTIC_CONTEXTS`** — a conclusion an LLM helped reach would be a
  guess with a rule id attached.
- **Tests:** `tests/architecture/test_engineering_reasoning_boundaries.py` ·
  `tests/architecture/test_structural_reasoning_boundaries.py`

---

# Supporting contexts

| Context | Role |
|---|---|
| `project` | The root aggregate. Depends on nothing; nearly everything is scoped to it (ADR-0001). |
| `document_registry`, `document_ingestion`, `document_identity` | Document lifecycle and content identity (checksum resolution) before canonicalisation. |
| `identity` | Users, sessions, password hashing (ADR-0022), audit identity. |
| `ontology` | The electrical reference vocabulary — YAML attribute and equipment definitions treated as domain data. **No dedicated boundary test.** |
| `audit` | Audit records. **No dedicated boundary test.** |
| `evidence_evaluation` | Measures the extractor against an annotated reference corpus; distinguishes real transcribed documents from synthetic ones. |
| `conversation`, `engineering_session`, `working_memory` | Session and conversational state (ADRs 0016–0018). **No dedicated boundary test**; governed by `ALLOWED_DOMAIN_DEPENDENCIES`. |
| `shared_kernel` | Shared primitives. Depends on nothing. |
| `engineering_index`, `proposed_claims`, `review_workflow`, `canonicalization` | Pre-governed-graph surfaces, **still referenced by services and routers** — active, not retired. Verify current callers before touching. |
| `retrieval_bridge` | The Classification-to-Retrieval bridge (Milestone 23B.3), used by `engineering_request_preparation_service`. Answering-path, not legacy; has its own boundary test. |

## Packages that are not derivation stages

Everything outside the six deterministic derivation contexts still matters, but
changing it is a different kind of change. `shared_kernel` and
`artifact_identity` are shared primitives with many dependents; `audit` is
cross-cutting; `ontology` is reference data — and note that `CLAUDE.md` §4.3
names `ontology` as **the** bounded-context reference pattern, so it is a
context in the manual's own terms even though it holds no engineering
derivation.

Before changing any of these, check what depends on them; a primitive with many
dependents is not a low-risk edit.

## Retired

`graph_builder`, `graph_query`, `project_knowledge_graph`,
`structured_retrieval` — the legacy graph stack, retired by ADR-0025 and
ADR-0028. **No domain directories exist for them.** Their names survive only as
inert keys in `ALLOWED_DOMAIN_DEPENDENCIES`. Do not treat them as available.

---

# Artifact identity — cross-reference

The six persisted deterministic reuse boundaries, each with a `find_by_identity`
port method and a `(document_id, artifact_identity)` unique constraint:

| # | Context | Identity module | Local derivation identity |
|---|---|---|---|
| 1 | canonical_pdf | `canonical_pdf_identity.py` | representation version, parser name, parser version |
| 2 | canonical_text | `canonical_text_identity.py` | segmentation version |
| 3 | engineering_evidence | `evidence_identity.py` | extraction policy |
| 4 | engineering_entities | `entity_identity.py` | resolution policy, entity model |
| 5 | engineering_facts | `fact_identity.py` | fact policy, fact contract |
| 6 | engineering_semantics | `semantic_identity.py` | semantic policy, semantic contract |

- **Primitive:** `app/domain/artifact_identity/`
- **Migrations:** `c1f80d54ea27` (extraction-policy provenance on fact/semantic
  sets), `e5a2f7b91c60` (identity columns and constraints on all six)
- **Fitness:** `tests/architecture/test_artifact_identity_architecture.py`
- **Behaviour:** `tests/services/test_artifact_identity_reuse.py`
- **ADR:** 0032, as amended by EPIC 32.E2.4

**Legacy rows** carry `NULL` identity: never reusable, never backfilled, never
written back. They are recomputed into a new fully identified artifact stored
alongside. A stage whose *upstream* has no identity refuses visibly rather than
deriving from provenance nobody can establish.

**Rule catalogues** are fingerprinted and pinned beside their policy version, so
changing a rule without raising its policy fails the build.
