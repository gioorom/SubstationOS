# Repository Map

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

Organised by responsibility, not by directory listing. Paths are
repository-relative.

---

## Top level

| Path | Role |
|---|---|
| `apps/backend/` | The product. All engineering interpretation happens here. |
| `apps/frontend/` | Next.js delivery surface. Renders engineering artefacts and consumes the API; decides no engineering meaning. |
| `docs/architecture/` | Long-form as-built architecture references and the architecture freeze. |
| `docs/architecture/adr/` | Accepted architecture decisions. |
| `docs/project/` | Product and milestone planning. **Historical record — not a current source.** |
| `docs/ai-context/` | This layer. |
| `CLAUDE.md` | The engineering manual. Binding. |
| `PRODUCT_VISION.md` | Product north star. |
| `scripts/` | Operational and contract tooling. Notably `scripts/export_openapi.py`, which writes the committed `apps/backend/openapi.json` contract snapshot. |
| `packages/`, `infrastructure/`, `tools/`, `knowledge/`, `storage/` | Shared libraries, deployment, local artefact storage. Peripheral to the engineering pipeline. |

**Excluded from all maps** (noise, never inspect): `.git/`, `node_modules/`,
`.next/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, build output, and the
untracked local databases in `apps/backend/` (`*.db`).

---

## Backend

`apps/backend/app/` is layered per `CLAUDE.md` §4. The dependency rule points
inwards: **the domain depends on nothing.**

| Path | Role | Read it when | Do not assume |
|---|---|---|---|
| `app/domain/` | Entities, value objects, domain services, **ports** (abstract repositories), rules-as-data catalogues. | Always, first — this is where meaning lives. | That every directory is a bounded context. Some are support or reference; see [BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md). |
| `app/services/` | Application orchestration, one module per use case: one use case per module, typed failure results rather than exceptions. | Tracing what actually runs end to end. | That a service owns domain rules. It sequences them. |
| `app/infrastructure/` | Adapters implementing domain ports — SQLAlchemy repositories, YAML loaders, the PDF parser, LLM providers. | Changing persistence or an external mechanism. | That an adapter may contain a domain rule. |
| `app/models/` | SQLAlchemy tables, uniqueness constraints, indexes. | Changing what is persisted, or reading an identity/uniqueness contract. | That a model is the domain. Domain objects are frozen dataclasses elsewhere. |
| `app/routers/` | FastAPI endpoints. | Changing a public contract. | That a router may decide engineering meaning. |
| `app/schemas/` | Request/response DTOs. | Changing the API surface. | That a DTO is a domain type. |
| `app/database/` | Session and engine wiring. | Rarely. | |
| `app/application/` | Cross-cutting application concerns (e.g. LLM invocation runtime). | Working on the answering path. | |
| `app/main.py` | Application entry point; router registration. | Finding which routers exist. | |

**Key entry points:** `app/main.py` (wiring) · `app/domain/<context>/` (meaning)
· `app/services/<context>_service.py` (orchestration).

---

## Persistence and migrations

| Path | Role |
|---|---|
| `apps/backend/migrations/versions/` | Alembic revisions. **Single head** at this baseline: `e5a2f7b91c60`. |
| `apps/backend/alembic.ini`, `migrations/env.py` | Migration config. The database URL comes from `app.database.database.DATABASE_URL`; `SUBSTATIONOS_DATABASE_URL` overrides it for a single run. |

**Use a scratch database for migration experiments.** Set
`SUBSTATIONOS_DATABASE_URL` to a temporary SQLite file; never test destructively
against `apps/backend/substationos.db`.

Migration governance is ADR-0008. See
[BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) for which context owns which tables.

---

## Tests

`apps/backend/tests/`, mirroring the source layout.

| Path | Contains |
|---|---|
| `tests/domain/` | Pure, fast, no I/O. |
| `tests/services/` | Real services against a real in-memory database through real adapters. |
| `tests/api/` | Endpoint contracts, including OpenAPI integrity. |
| `tests/infrastructure/` | Adapters against real fixtures. |
| `tests/architecture/` | **Executable architecture invariants — the highest-authority artefacts in the repository.** |
| `tests/integration/` | Full pipeline, end to end. |
| `tests/application/`, `tests/benchmarks/`, `tests/fixtures/` | Application concerns, performance baselines, canonical test data. |

Canonical command, per `CLAUDE.md` §9: **`python -m pytest` from
`apps/backend/`**. Config in `apps/backend/pytest.ini`. See
[TEST_MAP.md](TEST_MAP.md).

---

## Documentation

| Path | Role | Trust |
|---|---|---|
| `docs/architecture/*.md` | As-built references, one per context. | High — but code and tests outrank them. |
| `docs/architecture/architecture_freeze_af01.md` | The AF-01 freeze contract. | High. Paired with executable tests. |
| `docs/architecture/adr/` | The ADRs, plus a `README.md` index carrying the authoritative status column. | High. |
| `docs/project/` | Milestone plans and development history. | **Historical.** Do not read as current architecture. |
| `docs/ai-context/` | This layer. | Navigation only. |

---

## Frontend

`apps/frontend/` — Next.js. `apps/frontend/CLAUDE.md` includes
`apps/frontend/AGENTS.md`, which warns that this Next.js version differs from
training data and directs you to `node_modules/next/dist/docs/` before writing
code.

The frontend is a **delivery surface**: rendering, interaction, API
consumption. It has dedicated views for engineering artefacts — a document
`pipeline` and `workspace`, a project `knowledge-graph`, and components such as
`ArtifactInspector` and `EngineeringExplorer` — but these *render* typed data
received from the API rather than deciding meaning. ADR-0006 places AI and
presentation outside the source of engineering truth; the backend is
authoritative.

**The API contract is enforced across the boundary.** `apps/backend/openapi.json`
is a **committed contract snapshot**, produced by
`scripts/export_openapi.py`, not a build artefact. The frontend
keeps a hand-written transcription in `apps/frontend/lib/contracts/`, and
`apps/frontend/tests/contracts.test.ts` checks that transcription against
that snapshot. It asserts a **hand-listed set of cases**, not every enum, and a few
(`DOCUMENT_FORMATS`, `DOCUMENT_CATEGORIES`) are checked by spot-value because
the schema does not reference them directly. So it catches drift in what it
covers rather than proving whole-contract agreement.
(`scripts/export_openapi.py`'s own docstring says "every enum"; the test is
narrower.)

| Path | Role |
|---|---|
| `apps/frontend/app/` | Routes and pages, incl. `documents/[documentId]/{pipeline,workspace}` and `projects/[projectId]/knowledge-graph`. |
| `apps/frontend/components/` | Presentational components. |
| `apps/frontend/lib/contracts/` | Hand-written transcription of the backend contract. |
| `apps/frontend/tests/` | Vitest suite, incl. the contract test. |

Frontend commands (`apps/frontend/package.json`): `npm run test` (vitest),
`npm run typecheck`, `npm run lint`, `npm run build`.
