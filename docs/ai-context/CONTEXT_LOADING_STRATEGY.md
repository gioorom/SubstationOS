# Context Loading Strategy

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

The objective is **minimum sufficient authoritative context** — enough to be
correct, and no more.

---

## Phases

**Phase 0 — Instructions.** Read `CLAUDE.md` (root). For frontend work also
`apps/frontend/CLAUDE.md` → `apps/frontend/AGENTS.md`. These bind; nothing in
`docs/ai-context/` overrides them.

**Phase 1 — Locate.** Use [REPOSITORY_MAP.md](REPOSITORY_MAP.md) and
[BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) to name the owning context. If you
cannot name one, you are not ready to change anything.

**Phase 2 — Search.** Grep the repository for the symbols and the *callers*. The
packs below are a starting set; the repository is the evidence.

**Phase 3 — Read authoritative files.** The domain module that holds the rule,
its port, its policy constants. Domain before service before adapter.

**Phase 4 — Trace.** Who imports it. What persists it. Which unique constraint
governs it. Which fitness test guards it. Read
[ARCHITECTURE_INVARIANTS.md](ARCHITECTURE_INVARIANTS.md) for the theme.

**Phase 5 — ADRs and tests.** [ADR_INDEX.md](ADR_INDEX.md) for the governing
decision; existing tests to learn the expected behaviour and the idioms.

**Phase 6 — Implement.** Follow `CLAUDE.md`. Behaviour change and refactoring
are separate commits.

**Phase 7 — Verify.** [TEST_MAP.md](TEST_MAP.md): focused suites first, then
architecture + AF-01, then whatever the milestone requires. Full suite green
before any commit.

**Phase 8 — Independent review.** Code review over the diff before closure.

---

## Context packs

Each pack lists **categories and paths to open**, not contents to paste. All
paths under `apps/backend/` unless noted.

> **A context pack is a starting set, never proof that no other affected files
> exist.** Always perform your own dependency discovery in Phase 2.

### Artifact identity change
The highest-risk pack — these constants look ordinary and are not.
- `app/domain/artifact_identity/` (all four modules)
- The stage's `app/domain/<context>/<name>_identity.py`
- `app/services/<stage>_service.py` — where reuse is decided
- `app/models/<context>.py` — the `(document_id, artifact_identity)` constraint
- `migrations/versions/e5a2f7b91c60_*`, `c1f80d54ea27_*`
- `tests/architecture/test_artifact_identity_architecture.py`,
  `tests/services/test_artifact_identity_reuse.py`,
  `tests/domain/test_artifact_identity.py`
- **ADR-0032 including the amendment** — mandatory
- Remember: raising a rule version requires raising its policy version, or the
  catalogue fingerprint test fails.

### Evidence change
- `app/domain/engineering_evidence/` — `evidence_rules.py`,
  `evidence_patterns.py`, `evidence_policy.py`, `evidence_extractor.py`
- `app/domain/evidence_evaluation/corpora/substation_reference.yaml` — the
  measured corpus
- `tests/architecture/test_designation_evidence_boundaries.py`,
  `tests/domain/test_real_designation_evidence.py`,
  `tests/infrastructure/test_reference_corpus.py`
- Constraints to preserve: dot-qualified designations atomic, standalone
  location aspects, SF6 as a measured false positive.

### Entities / Facts / Semantics change
- `app/domain/<context>/` — the rule catalogue, policy, models, validation
- `app/services/engineering_<x>_service.py`
- `app/models/engineering_<x>.py`
- `tests/architecture/test_engineering_<x>_boundaries.py` + the context's
  domain and service tests
- ADR-0030 / 0031 for anything structural
- Vocabulary is closed: adding a member changes fitness tests deliberately.

### Human Review change
- `app/domain/human_review/` — especially `review_applicability.py` and
  `review_snapshot.py`
- `app/services/human_review_service.py`
- ADR-0023
- `tests/architecture/test_human_review_boundaries.py`,
  `tests/domain/test_human_review_domain.py`
- Do not turn review into an editable status field; do not migrate judgement.

### Graph / promotion change
- `app/domain/governed_knowledge_graph/` — `graph_vocabulary.py`,
  `promotion_rules.py`, `graph_identity.py`, `graph_provenance.py`
- `app/services/knowledge_promotion_service.py` — **the sole authorized *runtime* graph writer** (the adapter implements the capability; see BOUNDED_CONTEXTS.md for the chain)
- ADR-0024, 0025, 0028
- `tests/architecture/test_governed_graph_boundaries.py`,
  `test_graph_consolidation.py`, AF-01 KG invariants

### Retrieval change
- `app/domain/governed_retrieval/` — reader port, match policy, result assembly
- `app/services/governed_retrieval_service.py`
- ADR-0026; AF-RET-* and AF-AMB-* in the freeze register
- Read-only: the port declares no write operation.

### Context assembly change
- `app/domain/context_builder/` — budget policy, item selection, aggregation
- `app/services/context_builder_service.py`
- ADR-0027; AF-CTX-* invariants
- No I/O in this context.

### Reasoning change
- `app/domain/engineering_reasoning/` — the two rules, vocabulary, policy
- `app/services/engineering_reasoning_service.py`
- ADR-0029, 0031
- `tests/architecture/test_engineering_reasoning_boundaries.py`,
  `test_structural_reasoning_boundaries.py`
- Conclusions are not persisted and not promoted. Keep it that way.

### Persistence / migration change
- `app/models/<context>.py` and the owning domain port
- `migrations/versions/` — find the current head first
- ADR-0008
- Verify on a **scratch database** (`SUBSTATIONOS_DATABASE_URL`); never against
  `substationos.db`. Confirm a single head and ORM/migration parity.

### API change
- `app/routers/<name>.py`, `app/schemas/<name>.py`
- `tests/api/` including the OpenAPI contract and integrity tests
- Baseline: 100 paths / 415 schemas. Any change to those numbers is a public
  contract change and needs justification.
- AF-PROV-002: a persisting route may not accept governed provenance.
- **The contract crosses the boundary.** `apps/backend/openapi.json` is a
  committed snapshot regenerated by `scripts/export_openapi.py`,
  and `apps/frontend/tests/contracts.test.ts` asserts the frontend's
  `lib/contracts/` transcription matches it. A backend enum change can fail a
  frontend test.

### Frontend change
- `apps/frontend/CLAUDE.md` → `apps/frontend/AGENTS.md` **first** — this
  Next.js version differs from training data; read
  `node_modules/next/dist/docs/` before writing code.
- The frontend consumes the API. It renders engineering artefacts
  (`pipeline`, `workspace`, `knowledge-graph` views) but owns no engineering
  meaning.
- `apps/frontend/lib/contracts/` + `apps/frontend/tests/contracts.test.ts` —
  the transcribed backend contract and its assertion.
- Commands from `apps/frontend/`: `npm run test`, `npm run typecheck`.

---

## What not to do

- Do not read the whole of `app/domain/` to answer a narrow question.
- Do not treat `docs/project/` as current architecture — it is historical.
- Do not treat these documents as authoritative. Verify before relying.
- Do not add an import without checking both dependency mechanisms
  (see [BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md)).
- Do not fix unrelated debt in passing; `CLAUDE.md` §12 requires it separate.

## When the maps are wrong

Say so, in the report, with evidence. Do not quietly patch a map to match the
code, and do not patch code to match a map. A discrepancy between this layer and
the repository is information — it means the layer is stale, and the staleness
is worth knowing.
