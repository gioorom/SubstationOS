# AI Context Architecture

**CLASSIFICATION: DERIVED NAVIGATION AID — NOT AN AUTHORITATIVE SOURCE OF
ENGINEERING OR ARCHITECTURAL TRUTH.**

Derived from repository state at baseline commit
`a304b114c4c7ec65a0d84d89d80e9cfe9c65361d` ("Harden deterministic derived
artifact identity"), generated and verified 2026-09-01.

## What this directory is for

These documents exist so an agent can find the *right* part of SubstationOS
and read the authoritative evidence there — not so it can skip reading it.

> **The maps tell you where to look. The repository tells you what is true.**

**Do not preload the repository because these maps exist.** Their entire value
is letting you load *less*: identify the minimum authoritative context for the
task, read that, trace what it touches, then act.

## Read this first

`CLAUDE.md` at the repository root is the engineering manual and binds all
work — conventions, the dependency rule, testing, and what must never be done.
`apps/frontend/CLAUDE.md` (which includes `apps/frontend/AGENTS.md`) applies to
frontend work. Read the applicable one before writing code. Nothing here
overrides them.

## Authority

When something in these documents disagrees with the repository, **the
repository wins**. Authority sits, roughly in this order, with:

1. **[FITNESS]** executable architecture invariants — `apps/backend/tests/architecture/`
2. **[ADR]** accepted decisions — `docs/architecture/adr/`
3. **[CODE]** domain contracts and implementation — `apps/backend/app/domain/`
4. **[CODE]** persistence contracts and migrations — `apps/backend/app/models/`, `apps/backend/migrations/`
5. **[TEST]** behavioural proof — `apps/backend/tests/`
6. **[AUTH]** long-form architecture documentation — `docs/architecture/`
7. **[NAV]** these navigation documents — last, always

This ordering is a default, not a rule to apply mechanically: a migration and a
fitness function answer different questions, and neither outranks the other on
the question it owns.

**If two authoritative sources disagree, do not silently reconcile them.**
Record the discrepancy. This layer must never hide architecture drift.

## The documents

| Document | Answers |
|---|---|
| [REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Where does a responsibility live? Where do I start looking? |
| [ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md) | How does the pipeline fit together? Where are the trust boundaries? |
| [BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) | What does this context own, depend on, and prove? What must I inspect before changing it? |
| [ARCHITECTURE_INVARIANTS.md](ARCHITECTURE_INVARIANTS.md) | What is structurally forbidden, and which test enforces it? |
| [TEST_MAP.md](TEST_MAP.md) | What proves this behaviour? What must I run after changing it? |
| [ADR_INDEX.md](ADR_INDEX.md) | Which decision governs this, and is it still current? |
| [CONTEXT_LOADING_STRATEGY.md](CONTEXT_LOADING_STRATEGY.md) | Which files do I actually need for this kind of change? |

**Reading order for a newcomer:** this file → `ARCHITECTURE_MAP.md` →
`BOUNDED_CONTEXTS.md` (only the contexts you need) → `CONTEXT_LOADING_STRATEGY.md`.

**Reading order for a specific task:** `CONTEXT_LOADING_STRATEGY.md` → the
matching context pack → the authoritative files it names.

## The loop

```
MAP      -> REPOSITORY_MAP / ARCHITECTURE_MAP: which area owns this?
SEARCH   -> grep the repository; the maps are a starting set, never a complete one
READ     -> the authoritative domain contract, port, ADR
TRACE    -> who imports it, who persists it, which fitness test guards it
IMPLEMENT
VERIFY   -> TEST_MAP: the focused suites, then the gates the milestone requires
```

## Freshness

Each document records the baseline commit it was derived from. **If current
`HEAD` differs materially from that baseline, treat these documents as
navigation only and re-verify any claim you are about to rely on** against
current code, tests, ADRs and fitness functions.

Regeneration is not needed after every commit. Review this layer when any of
these change materially: bounded contexts, the domain dependency graph, ADRs,
architecture fitness functions, test topology, persistence ownership, major
directory structure, or governance boundaries.

## Discovered documentation drift

Verified during generation, recorded rather than fixed. None of these affects
the correctness of the running system; they affect how much you should trust
older documentation.

| # | Classification | Finding | Evidence |
|---|---|---|---|
| 1 | `HISTORICAL_ONLY` | `docs/project/PRODUCT_DEVELOPMENT_PLAN.md` describes the canonical PDF uniqueness constraint as `(document_id, content_checksum, representation_version)`. That constraint was replaced by `(document_id, artifact_identity)` in migration `e5a2f7b91c60`. The file is a historical milestone record, not a live architecture reference. | `docs/project/PRODUCT_DEVELOPMENT_PLAN.md`; `apps/backend/app/models/canonical_pdf.py` |
| 2 | `STALE_NAVIGATION` | `ALLOWED_DOMAIN_DEPENDENCIES` still contains entries for four contexts that no longer exist as domain packages — `graph_builder`, `graph_query`, `project_knowledge_graph`, `structured_retrieval` — retired by ADR-0025 and ADR-0028. Harmless: the test skips a context whose directory is absent. | `apps/backend/tests/architecture/test_bounded_context_dependencies.py` |
| 3 | `DOCUMENTATION_DEBT` | Domain dependency governance is not uniform. Many packages have no dedicated `test_*_boundaries.py`; most of those are keys in `ALLOWED_DOMAIN_DEPENDENCIES` instead. **`audit` and `ontology` are covered by neither** — they are absent from the whitelist, have no boundary test, and no `FROZEN_DIRECTIONS` pair names them. Both are support contexts, so the exposure is small, but it is real. | `apps/backend/tests/architecture/test_bounded_context_dependencies.py`; `test_architecture_freeze_af01.py` |
| 4 | `DOCUMENTATION_DEBT` | `GraphProvenance.pipeline_identity` describes the upstream chain as a four-tuple that does not include the extraction policy. ADR-0032 records this explicitly as descriptive-only debt — nothing is keyed on it. | `apps/backend/app/domain/governed_knowledge_graph/graph_provenance.py`; ADR-0032 |
| 5 | `DOCUMENTATION_DEBT` | `architecture_freeze_af01.md` §9's prose table omits the `engineering_reasoning` pairs that EPIC 32 added to `FROZEN_DIRECTIONS`, and the `AF-DEP-001` docstring undercounts them too. The executable tuple is authoritative; the prose is incomplete. | `docs/architecture/architecture_freeze_af01.md` §9; `apps/backend/tests/architecture/test_architecture_freeze_af01.py` |
| 6 | `DOCUMENTATION_DEBT` | `scripts/export_openapi.py`'s docstring says `contracts.test.ts` compares "every enum"; the test asserts a hand-listed set of cases, and checks a few enums (`DOCUMENT_FORMATS`, `DOCUMENT_CATEGORIES`) by spot-value rather than by equality because the schema does not reference them directly. Separately, `contracts.test.ts` tells the reader to regenerate with `cd apps/backend && python -m scripts.export_openapi`, but the script is at repository root. | `scripts/export_openapi.py`; `apps/frontend/tests/contracts.test.ts` |
| 7 | `DOCUMENTATION_DEBT` | ADR-0032's status `Amended (32.E2.4)` is not one of the statuses `docs/architecture/adr/README.md` otherwise uses. [ADR_INDEX.md](ADR_INDEX.md) copies it faithfully rather than normalising it. | `docs/architecture/adr/README.md` |

Items 3–7 are documentation-level; the authoritative executable artefacts are
correct in every case. None is `POSSIBLE_ARCHITECTURE_DRIFT`; none is
`REQUIRES_HUMAN_REVIEW`.
