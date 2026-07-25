# Operational Reliability

**Status:** Review and hardening record, Milestone 12 (Knowledge
Platform Hardening), Workstream 7. Documents how application startup,
configuration, and health reporting behave today - no distributed
tracing or monitoring platform is introduced (out of scope for this
milestone).

## Startup no longer mutates schema

Before this milestone, `app/main.py` called
`Base.metadata.create_all(bind=engine)` on every process start,
against the real on-disk database - meaning any missing table was
silently created the moment the app happened to boot, with no record
of when or why. This is now removed (see
[database_migrations.md](database_migrations.md)): schema lifecycle is
Alembic's responsibility exclusively (`alembic upgrade head`), and
application startup performs no DDL at all. A database that has not
been migrated fails loudly at first query - not at import time, and
not by being silently patched into shape.

The one deliberate exception is the isolated, in-memory test database
(`tests/conftest.py`'s `db_session` fixture), which still calls
`Base.metadata.create_all()` because it is disposable and rebuilt
fresh for every test - it is never this application's real schema, and
never touches an on-disk file.

## `app.main` imports cleanly

`python -c "import app.main"` succeeds with no database connection
attempt and no side effect beyond FastAPI app construction and router
registration - confirmed as part of this milestone's OpenAPI integrity
test (`tests/api/test_openapi_integrity.py::test_application_imports_and_openapi_schema_generates`),
which imports `app.main` and generates its OpenAPI schema with no
database available.

## Health endpoint

`GET /health` (`app/main.py`) already existed before this milestone and
is coherent with the "no new monitoring platform" instruction, so no
new endpoint was added. It reports three checks:

- `database`: opens a `SessionLocal()` session and runs `SELECT 1`;
  `"offline"` on any exception, `"online"` otherwise.
- `storage`: writes and deletes a `.healthcheck` file under the
  documents storage path; `"offline"` on any exception.
- `ai`: hardcoded `"offline"` - there is no AI health check today
  (the legacy Claude provider is constructed lazily, per-request, not
  at startup).

Both checks catch broad `Exception` **only** to turn a raw error into a
`"offline"` status string - neither leaks the underlying exception
message, stack trace, or connection string to the caller, satisfying
"do not expose internal secrets/raw DB errors." `overall_status` is
`"online"` only if every check is online, `"warning"` otherwise; there
is no separate `/ready` endpoint, and none is added here - `/health`
already serves both purposes for this application's current size.

## Configuration and explicit failure

- **Database connection string** (`app/database/database.py`):
  `DATABASE_URL = "sqlite:///./substationos.db"` is a fixed value, not
  environment-driven, for the application itself. `create_engine()` is
  lazy - a misconfigured or unreachable database does not fail at
  import time, but at first query, which is the same "fail loudly, not
  silently" posture startup now has for schema. Alembic's own
  `SUBSTATIONOS_DATABASE_URL` override (see
  [database_migrations.md](database_migrations.md)) affects only
  migration invocations, never the running application - documented
  explicitly in `.env.example` so the two are not confused. Making the
  application's own `DATABASE_URL` environment-driven is a reasonable
  future improvement but is **not** made in this milestone: no defect
  in current behavior was demonstrated (the value has always been
  hardcoded and the app has always worked), and changing it touches
  real deployment wiring rather than hardening the already-working
  knowledge pipeline - tracked as remaining technical debt instead.
- **AI provider configuration** (`app/services/ai/claude_provider.py`):
  `ANTHROPIC_API_KEY` is required with no default; its absence raises
  `AIProviderError` immediately at `ClaudeProvider()` construction,
  not a silent no-op or a downstream `KeyError`. This was already
  correct before this milestone and required no change.
- **`.env.example`** (new this milestone, `apps/backend/.env.example`):
  documents every environment variable the backend actually reads
  (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `SUBSTATIONOS_DATABASE_URL`),
  each with its own scope and default behavior - the project's
  `.gitignore` already anticipated this file
  (`!.env.example` alongside `.env`/`.env.*`) but it did not exist
  until now.

## Test configuration remains isolated

`tests/conftest.py`'s `db_session` fixture creates a fresh in-memory
SQLite database (`sqlite://` with `StaticPool`) per test, calls
`Base.metadata.create_all()` against it directly, and disposes the
engine on teardown. It never imports or touches
`app.database.database.engine`/`DATABASE_URL`, so running the test
suite never reads, writes, or migrates the real on-disk
`substationos.db` file. This was already true before this milestone
and is unchanged.

## What this document deliberately does not do

- No distributed tracing, APM, or external monitoring platform is
  introduced - out of this milestone's explicit non-goals.
- No new `/ready` endpoint - `/health`'s existing three-check shape
  already covers readiness for this application's current
  architecture.
- The application's own `DATABASE_URL` is not made environment-driven
  in this milestone (see above) - recorded as remaining technical
  debt, not fixed speculatively.
