# SubstationOS

**An engineering operating system for HV/MV substations.**

Commissioning a high-voltage substation means working across hundreds of
documents: single-line diagrams, functional and protection schematics, relay
setting sheets, factory and site test reports, client specifications, standards.
They arrive in different formats, from different vendors, in different
revisions. Answering one concrete question — *which CT ratio was specified for
this bay, and does the relay setting actually match it?* — means opening five
documents and trusting your memory for the rest.

SubstationOS ingests that documentation, organises it into per-site project
workspaces, and turns it into a queryable engineering knowledge base.

The project is built by a field commissioning engineer, against the problem as
it actually shows up on site.

---

## What it does today

- **Project workspaces** — one project per substation or commissioning job,
  holding all of its technical documentation.
- **Knowledge pipeline** — ingestion and extraction of technical documents into
  a canonical knowledge representation, rather than a pile of raw files.
- **Structured retrieval** — a deterministic retrieval layer over that knowledge
  base, so answers are traceable back to the document they came from.
- **Governed API** — a versioned Project and Document API contract, consumed by
  a Next.js web client.

## Roadmap

- **Engineering agent** — advanced search and cross-document reasoning:
  connecting a specification to the scheme that implements it and to the test
  report that verifies it.
- **AutoCAD integration** — a copilot for drafting and revising functional and
  protection schematics from within the drawing environment.

## Architecture

| Layer | Stack |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Frontend | Next.js (119 tests) |
| LLM layer | Anthropic API |
| Database | SQL, migration-managed |

The architecture is frozen at **v1.0** and documented as Architecture Decision
Records. Operational concerns — migrations, transaction conventions,
reliability, performance baselines — are documented rather than implied.

## Status

Under active development, single author. Working software, not production
software: expect breaking changes, and don't point it at anything you can't
afford to lose. Issues and observations are welcome.

## Getting started

**Backend** — no dependency manifest yet (tracked as technical debt). Install
into a virtualenv: `fastapi`, `sqlalchemy`, `alembic`, `python-dotenv`,
`anthropic`, `pytest`, `httpx`, `uvicorn`.

```bash
cd apps/backend
alembic upgrade head        # or `alembic stamp head` on an existing dev database
uvicorn app.main:app --reload
python -m pytest
```

**Frontend**

```bash
cd apps/frontend
npm install
npm run dev                 # http://localhost:3000
npm test
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` (default
`http://127.0.0.1:8000`). Full setup notes in `docs/developer_setup.md`.

## Repository layout

```
apps/backend/     Python / FastAPI backend (primary application)
apps/frontend/    Next.js web frontend
knowledge/        Canonical Knowledge Protocol and extraction infrastructure
docs/             Architecture, ADRs, operational and product documentation
```

## Documentation

| Document | What it covers |
|---|---|
| [`PRODUCT_VISION.md`](PRODUCT_VISION.md) | Product vision, mission, long-range narrative |
| [`CLAUDE.md`](CLAUDE.md) | Engineering manual: architecture, conventions, workflow |
| [`docs/architecture/`](docs/architecture/) | Architecture Freeze v1.0, ADRs, readiness checklist |
| [`docs/project/PRODUCT_DEVELOPMENT_PLAN.md`](docs/project/PRODUCT_DEVELOPMENT_PLAN.md) | Roadmap: status, EPICs, milestones |
| [`docs/developer_setup.md`](docs/developer_setup.md) | Local development setup |

## License

All rights reserved. Readable as a portfolio and reference project; not licensed
for reuse.
