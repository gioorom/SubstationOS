# Developer Setup

How to run SubstationOS locally — backend, frontend, and the checks that
must pass before a commit.

For *what* the code is, see [`CLAUDE.md`](../CLAUDE.md); for the
frontend's design, see
[`docs/architecture/frontend_architecture.md`](architecture/frontend_architecture.md).

## Prerequisites

| Tool | Version | Used by |
|---|---|---|
| Python | 3.13+ | backend |
| Node.js | 24.15+ | frontend |

## Backend

No dependency manifest exists yet (tracked as technical debt in the
Development Plan). Install into a virtual environment by hand:

```
fastapi  sqlalchemy  alembic  python-dotenv  anthropic
pytest  httpx  uvicorn  pymupdf  pyyaml
```

Then:

```bash
cd apps/backend
alembic upgrade head          # `alembic stamp head` for an existing dev database
uvicorn app.main:app --reload # serves on http://127.0.0.1:8000
python -m pytest              # 3523 tests, all deterministic
```

The schema is managed by Alembic, never by application startup: a
database that has not been migrated fails loudly at first query rather
than being silently patched into shape. See
[`database_migrations.md`](architecture/database_migrations.md).

`ANTHROPIC_API_KEY` is **not** required. It is used only by the legacy
LLM-backed Knowledge Graph extractor on the upload path; the entire
deterministic pipeline — canonical representation, text, evidence,
entities, facts, semantics — runs without any AI provider.

## Frontend

```bash
cd apps/frontend
npm install
npm run dev                   # serves on http://localhost:3000
```

### Configuration

One variable, read in `config/env.ts`:

| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | Where the backend is |

Put overrides in `apps/frontend/.env.local` (git-ignored):

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

The backend's CORS policy allows `http://localhost:3000` (see
`app/main.py`). Serving the frontend from another origin means widening
that list — a backend change, so make it deliberately.

### Checks

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # eslint
npm test            # vitest, 312 tests
npm run build       # next build
```

All four must pass before a commit, alongside the backend's
`python -m pytest`.

## Keeping the API contract in sync

The frontend transcribes the backend's schemas into
`apps/frontend/lib/contracts`, and `tests/contracts.test.ts` asserts the
transcription still matches. It reads a committed snapshot of the
backend's OpenAPI document.

**Whenever a router, schema or enum changes, regenerate it:**

```bash
python scripts/export_openapi.py   # writes apps/backend/openapi.json
```

Then run the frontend tests. A failure there means the frontend is
describing an API that no longer exists — fix the frontend, never the
backend, unless the backend change itself was the mistake.

Since Milestone 30.1.3 the same test also checks the **filter
parameters** and the **page-size bounds**, and asserts that no document
schema in the document declares a storage field. A drift in any of those
fails the frontend suite rather than a screen.

The snapshot is committed on purpose. It is not a build artefact: it is
the version of the contract the frontend was written against, and a diff
on it is exactly the review signal a breaking enum change should produce.

If the snapshot is missing, the enum assertions skip and the structural
assertions still run, so a checkout without a Python environment is not
blocked.

## The public API contract

Full reference: [`public_api.md`](architecture/public_api.md). The parts
you need day to day:

### Pagination

Every list endpoint takes `page` (1-based, default 1) and `page_size`
(default 25, **maximum 100**). A larger page size is refused with 422,
never clamped.

```bash
curl "http://127.0.0.1:8000/documents/?page=2&page_size=50"
```

Responses are `{"items": [...], "pagination": {...}}`, where
`pagination.total` is the whole result set, not the page.

### Filters

| `GET /projects/` | `GET /documents/` |
|---|---|
| `status` (delivery phase) | `project_id` |
| `lifecycle_state` (record state) | `scope` |
| `include_deleted` | `file_format` |
| `search` — name, code, customer, location | `category` |
| | `search` — filename, project name |

Search is **case-insensitive, partial, trimmed**; internal whitespace is
significant; an empty term is no filter at all.

`status` and `lifecycle_state` are independent: a project can be
`energized` and `archived` at the same time.

### Sorting

`sort_by` and `direction` (`asc` / `desc`). Closed vocabularies —
anything else is a 422.

- Projects: `created_at` (default), `updated_at`, `name`, `code`
- Documents: `uploaded_at` (default), `filename`, `revision`,
  `document_format`

### Documents

```bash
curl http://127.0.0.1:8000/documents/1            # DocumentDetailRead
curl -OJ http://127.0.0.1:8000/documents/1/content  # the original bytes

# One page of the canonical representation (EPIC 30.2) - what the
# Engineering Workspace's page map draws, at the parser's own coordinates
curl http://127.0.0.1:8000/documents/1/canonical-representation/pages/1
```

**No public schema carries a storage location.** `file_path` is private
backend state; the download takes a document id and nothing else, so a
path can never be supplied or disclosed. Tests enforce both.

## Authentication

Since EPIC 30.3 the API denies anonymous callers by default. Before
anything works, create the first administrator:

```bash
cd apps/backend && alembic upgrade head       # users, sessions, audit_events
cd ../.. && python scripts/create_administrator.py     --email you@example.com --name "Your Name"
```

The password is read from the terminal without echo, or from
`SUBSTATIONOS_ADMIN_PASSWORD`. It is **never** taken from a command-line
argument - arguments land in shell history and in the process list. The
script refuses to run once any account exists.

Then sign in at the frontend. Additional accounts are created by an
administrator through `POST /users/`; there is no self-registration,
because a private engineering platform does not admit whoever finds the
address.

### The dev origin matters

The session cookie is `HttpOnly` and `SameSite=Lax`. "Site" is scheme
plus registrable domain - ports are ignored, but `localhost` and
`127.0.0.1` are **different hosts**. Run the backend on
`http://localhost:8000` (the default `config/env.ts` points at), not
`http://127.0.0.1:8000`, or the cookie will silently not travel and every
request will arrive anonymous.

```bash
cd apps/backend && uvicorn app.main:app --reload --host localhost
```

### Trying it with curl

```bash
# Sign in, keeping the cookie jar.
curl -c cookies.txt -X POST http://localhost:8000/auth/login     -H 'Content-Type: application/json'     -d '{"email":"you@example.com","password":"..."}'

# Reads need only the cookie.
curl -b cookies.txt http://localhost:8000/projects/

# Writes additionally need the CSRF token echoed from its cookie.
CSRF=$(grep substationos_csrf cookies.txt | awk '{print $7}')
curl -b cookies.txt -H "X-CSRF-Token: $CSRF"     -X POST http://localhost:8000/projects/     -H 'Content-Type: application/json'     -d '{"name":"Cabina","code":"CP-1","customer":"Distributore Nazionale"}'
```

Anonymous requests answer `401`; an authenticated caller without the
capability answers `403`. `/`, `/health`, `/auth/*` and the API docs are
the only public routes - `security_architecture.md` §7 lists each and why.

## Running the whole loop

To exercise a document end to end:

1. Start the backend and the frontend, and sign in.
2. Create a project at `/projects/new` — code, name and customer are
   required by the API.
3. Upload a **PDF** at `/documents` (only PDFs enter the canonical
   pipeline; other formats are stored and classified but stop there).
4. Open the document's pipeline and run the stages in order:
   representation → text → evidence → entities → facts → semantics.

A stage that has not run yet answers 404 and shows as *ready*; a stage
that ran and found nothing shows as *empty*. Neither is an error.

A useful test document is a single line reading
`Trasformatore TR1 630 kVA`: it produces two observations, two entities,
one fact, and one `HAS_RATED_POWER` statement — the whole chain in one
line.

5. Open the **Engineering Workspace** at
   `/documents/{id}/workspace` and walk that chain backwards. Select the
   `HAS_RATED_POWER` statement; the Inspector shows its supporting fact,
   both entities, both observations and the canonical line, and the page
   map highlights the span the observation was read from.

Two things worth checking deliberately, because they are what the
Workspace exists to get right:

- Upload a document and open the Workspace **before running any stage**.
  Every explorer says *non eseguito*, not *nessun risultato*. Those are
  different documents, and the UI never conflates them.
- Select an artefact, then reload the page. The selection is in the URL
  (`?kind=…&key=…`) and survives; Back and Forward step through
  inspections.

The Workspace is **inspection-only**. There is no approve, reject or
correct, and there deliberately will not be until a governed Human Review
bounded context exists — see
[engineering_workspace.md](architecture/engineering_workspace.md).
