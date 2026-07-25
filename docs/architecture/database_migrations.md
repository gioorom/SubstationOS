# Database Migrations

**Status:** Practical runbook, Milestone 12 (Knowledge Platform
Hardening). For the *decision* behind this setup (why Alembic, why this
baseline strategy), see
[ADR-0008](adr/0008-database-migration-governance.md). This document is
the *commands* — it changes whenever the workflow changes, unlike the
ADR.

## Setup (once per environment)

Alembic is not yet in this project's dependency manifest (there is no
`requirements.txt`/`pyproject.toml` in `apps/backend` at all — a
pre-existing gap, not introduced or resolved by this milestone).
Install it into the same virtual environment as the rest of the
backend:

```bash
cd apps/backend
pip install alembic
```

## The single source of truth for the connection string

`alembic.ini`'s `sqlalchemy.url` is intentionally left unset.
`migrations/env.py` reads `app.database.database.DATABASE_URL` at
runtime instead — the exact URL the running application uses — so
migrations and the application can never silently point at different
databases (CLAUDE.md §16, Provider Independence).

To point Alembic at a different database for a single command (e.g. a
scratch file while testing a new migration), set
`SUBSTATIONOS_DATABASE_URL`. This variable is read **only** by
`migrations/env.py` — the running application never reads it (see
`.env.example`).

```bash
# One-off, does not affect the real database or require editing code:
SUBSTATIONOS_DATABASE_URL="sqlite:///./scratch.db" alembic upgrade head
```

## Bringing a fresh database under migration control

```bash
cd apps/backend
alembic upgrade head
```

Creates every table in `Base.metadata` from nothing, via
`migrations/versions/b3e2e0f30024_baseline_all_governed_tables.py`
(the current head). Proven this milestone against a throwaway scratch
SQLite file — see [ADR-0008](adr/0008-database-migration-governance.md) §3.

To reverse it (drops every table the baseline created):

```bash
alembic downgrade base
```

## Bringing an EXISTING, `create_all()`-built database under migration control

If a database already has every table `Base.metadata` declares (e.g.
a dev database created before this milestone, when `app/main.py` still
called `create_all()` on startup), **do not** run `alembic upgrade
head` against it — the baseline migration's `CREATE TABLE` statements
would fail against tables that already exist.

Instead, adopt it non-destructively:

```bash
cd apps/backend
alembic stamp head
```

`stamp` writes only a single row into a new `alembic_version` table
recording "this database is at revision `b3e2e0f30024`" — it runs no
DDL against any existing table. This is genuinely non-destructive: it
was proven this milestone against a full copy of an existing
`create_all()`-built dev database with no data loss and no schema
change to any table other than the new `alembic_version` bookkeeping
table.

**Before running `stamp head` against a real database, verify its
schema actually matches the baseline** (same table/column set) — this
runbook does not do that verification for you. If a real database's
schema has drifted from `Base.metadata` (a manual `ALTER TABLE` was
run outside of `create_all()`, for instance), reconcile that first;
`stamp` will not detect or fix a mismatch, it only records a revision
as applied.

## Running the application after migrating

`app/main.py` performs no schema DDL at startup (see
[operational_reliability.md](operational_reliability.md)) — a database
that has not been migrated (or stamped) will fail at first query, not
be silently patched into shape. Run `alembic upgrade head` (fresh) or
`alembic stamp head` (existing, pre-Alembic database) once, before
starting the application, in every environment.

## Adding a new migration

After changing a model under `app/models/**`:

1. Make sure `migrations/env.py`'s model-import list includes the
   changed module (it must match `app/main.py`'s import list — this is
   a manual, documented step; there is no automatic model-discovery
   mechanism in this codebase).
2. Generate a migration by diffing `Base.metadata` against a real (or
   scratch) database already at the current head:

   ```bash
   cd apps/backend
   alembic revision --autogenerate -m "add rated_voltage index to project_graph_nodes"
   ```

3. **Read the generated migration.** `--autogenerate` produces a
   best-effort diff, not a guaranteed-correct one (it cannot detect
   every kind of change, e.g. some column-type narrowing) — review
   `upgrade()`/`downgrade()` before committing.
4. Test it against a scratch database (`SUBSTATIONOS_DATABASE_URL`,
   as above) before running it against anything real.

## Test databases are not migrated

`tests/conftest.py`'s `db_session` fixture builds a fresh, in-memory
SQLite database per test via `Base.metadata.create_all()` directly —
it does not use Alembic. This is deliberate: a disposable,
rebuilt-per-test database gains nothing from migration history, and
requiring `alembic upgrade head` per test would only add latency. This
is the one place `create_all()` remains in this codebase — see
[ADR-0008](adr/0008-database-migration-governance.md) §1.

## Running the performance benchmarks

Unrelated to schema migration, but documented here for the same
"how do I run this locally" purpose — see
[performance_baseline.md](performance_baseline.md) for methodology and
recorded results:

```bash
cd apps/backend
python -m scripts.benchmarks.graph_performance_benchmark
```

## Running the test suite

```bash
cd apps/backend
python -m pytest
```
