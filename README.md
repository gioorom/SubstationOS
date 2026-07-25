# SubstationOS

Engineering Operating System for HV/MV substations — see
`PRODUCT_VISION.md` for the product vision and `CLAUDE.md` for how the
codebase is built.

## Documentation map

- `CLAUDE.md` — engineering manual: architecture, conventions, workflow.
  Start here before writing any code.
- `PRODUCT_VISION.md` — product vision, mission, and long-range product
  narrative.
- `docs/project/PRODUCT_DEVELOPMENT_PLAN.md` — the official long-term
  roadmap: current status, EPICs, milestones, and success criteria.
- `docs/architecture/` — Architecture Freeze v1.0: the binding
  architecture (`project_intelligence_architecture.md`), its
  Architecture Decision Records (`adr/`), and the implementation
  readiness checklist (`ARCHITECTURE_FREEZE_V1_CHECKLIST.md`).
  `knowledge_pipeline_overview.md` documents the knowledge pipeline as
  actually implemented; `database_migrations.md`,
  `repository_transaction_conventions.md`,
  `operational_reliability.md`, and `performance_baseline.md` document
  its operational hardening (Milestone 12); `structured_retrieval.md`
  documents the deterministic retrieval layer (Milestone 13).

## Backend quick start

No dependency manifest exists yet (tracked in the Development Plan's
Technical Debt) — install the backend's packages into your virtual
environment by hand (FastAPI, SQLAlchemy, Alembic, python-dotenv,
anthropic, pytest, httpx, uvicorn), then:

```bash
cd apps/backend
alembic upgrade head        # or `alembic stamp head` for an existing dev database
uvicorn app.main:app --reload
python -m pytest            # full test suite
```

See `docs/architecture/database_migrations.md` for the full migration
workflow (fresh vs. existing database) and
`docs/architecture/performance_baseline.md` for how to run the graph
performance benchmarks.

## Layout

- `apps/backend/` — Python/FastAPI backend (primary application).
- `apps/frontend/` — Next.js web frontend.
- `knowledge/` — Canonical Knowledge Protocol and extraction
  infrastructure.
