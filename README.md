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

## Layout

- `apps/backend/` — Python/FastAPI backend (primary application).
- `apps/frontend/` — Next.js web frontend.
- `knowledge/` — Canonical Knowledge Protocol and extraction
  infrastructure.
