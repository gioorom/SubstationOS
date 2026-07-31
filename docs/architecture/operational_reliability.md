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
- **AI provider configuration**: `ANTHROPIC_API_KEY` is required with no
  default, and its absence fails immediately at construction rather than
  as a silent no-op or a downstream `KeyError`. This was described here
  against `app/services/ai/claude_provider.py`, which **EPIC 31.1
  deleted** along with the rest of the legacy Knowledge Graph path. The
  same property now belongs to the governed provider adapter,
  `app/infrastructure/llm/anthropic/**`, configured through
  `app/application/config/llm_configuration.py`.
- **`.env.example`** (new this milestone, `apps/backend/.env.example`):
  documents every environment variable the backend actually reads
  (`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `SUBSTATIONOS_DATABASE_URL`),
  each with its own scope and default behavior - the project's
  `.gitignore` already anticipated this file
  (`!.env.example` alongside `.env`/`.env.*`) but it did not exist
  until now.
  **Extended in Milestone 16** with `LLM_PROVIDER`/`LLM_MODEL`/
  `LLM_DEFAULT_MAX_OUTPUT_TOKENS`/`LLM_TEMPERATURE` - a deliberately
  separate configuration surface for the new, provider-neutral LLM
  Provider Abstraction Layer (`app/application/**`), unrelated to the
  legacy `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` pair above. Unlike
  `CLAUDE_MODEL`, `LLM_MODEL` has no hardcoded fallback model name of
  any kind - see `docs/architecture/llm_provider_abstraction.md`.
  **Extended again in Milestone 17** with `LLM_RUNTIME_ENABLED`/
  `LLM_CONNECT_TIMEOUT_SECONDS`/`LLM_READ_TIMEOUT_SECONDS`/
  `LLM_TOTAL_TIMEOUT_SECONDS`/`LLM_MAX_ATTEMPTS`/
  `LLM_RETRY_BASE_DELAY_SECONDS`/`LLM_RETRY_MAX_DELAY_SECONDS`/
  `LLM_RETRY_JITTER_ENABLED` for the LLM Invocation Runtime - this
  surface reuses `ANTHROPIC_API_KEY` as its credential rather than
  introducing a second key variable, since both paths ultimately call
  the same Anthropic account. `LLM_RUNTIME_ENABLED` defaults to
  `false`: a freshly deployed instance never performs a real provider
  call, and never transmits project data externally, until an operator
  explicitly opts in.

## The LLM Invocation Runtime's failure posture

Added in Milestone 17 (see
[llm_invocation_runtime.md](llm_invocation_runtime.md) and
[ADR-0014](adr/0014-llm-invocation-runtime.md)). Three timeouts are
distinguished, never conflated: a per-call connect timeout, a per-call
read timeout, and a single total invocation deadline covering every
attempt and retry delay combined - a new attempt never starts once the
deadline has passed, regardless of how much of `LLM_MAX_ATTEMPTS`
remains. Retryable provider failures (connection/timeout/rate-limit/
overload/transient-provider categories) are retried with bounded,
jittered exponential backoff; every other category (authentication,
invalid request, model not found, content-policy rejection, and,
conservatively, any error the mapper cannot categorize) fails on the
first attempt. `asyncio.CancelledError` is never treated as a
retryable failure - it propagates as genuine cancellation. Every
attempt (successful, failed, or cancelled) is preserved on the
invocation result, so a caller can answer "what actually happened"
without correlating logs across the SDK, the adapter, and the runtime.
The Anthropic SDK's own retry logic is disabled entirely
(`max_retries=0`): the runtime is the only layer that ever decides to
retry, so total attempt count and total elapsed time stay predictable
from one configuration surface.

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
