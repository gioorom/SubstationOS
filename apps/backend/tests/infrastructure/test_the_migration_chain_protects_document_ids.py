"""
The one place the Alembic chain is actually executed.

Every other test builds its schema with ``Base.metadata.create_all``,
which reads the models. Real deployments run the migrations, which read
nothing - so anything a migration does, or fails to do, is invisible to
the rest of the suite. That gap is why the two defects below reached a
reviewer instead of a test.

Both concern one guarantee: a document id is never reissued, because
twelve tables remember it and a reissued id hands a new document another
document's provenance. The guarantee lives in the ``documents`` table's
own DDL - ``AUTOINCREMENT``, and the high-water mark SQLite records
beside it - and a table rebuild is exactly the operation that can drop
both without anybody writing a line about ids.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

BACKEND_ROOT = Path(__file__).resolve().parents[2]

PRIOR_REVISION = "3ca7e14b90d2"

_INSERT = (
    "INSERT INTO documents "
    "(project_id, filename, file_path, file_format, category, revision, "
    " project_name, scope, uploaded_at) "
    "VALUES (NULL, ?, ?, 'pdf', 'general_technical', '00', 'Unknown', "
    "        'project', datetime('now'))"
)


@pytest.fixture()
def migrated(tmp_path, monkeypatch) -> Path:
    """A database built by the migrations, not by the models."""

    database = tmp_path / "chain.db"

    monkeypatch.setenv("SUBSTATIONOS_DATABASE_URL", f"sqlite:///{database}")

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))

    command.upgrade(config, "head")

    return database


def _sql(database: Path, statement: str, *parameters):
    connection = sqlite3.connect(database)

    try:
        rows = connection.execute(statement, parameters).fetchall()
        connection.commit()
        return rows
    finally:
        connection.close()


def _add(database: Path, name: str) -> None:
    _sql(database, _INSERT, name, f"/storage/documents/{name}")


def _ids(database: Path) -> list[int]:
    return [row[0] for row in _sql(database, "SELECT id FROM documents")]


def test_the_migrated_schema_declares_autoincrement(migrated: Path) -> None:
    """
    What `create_all` cannot tell us.

    The model carries ``sqlite_autoincrement``, so every test database
    has it and every test would pass with the migration deleted. This
    asserts the shape a deployment actually gets.
    """

    ddl = _sql(
        migrated,
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'documents'",
    )[0][0]

    assert "AUTOINCREMENT" in ddl


def test_a_migrated_database_does_not_reuse_a_document_id(
    migrated: Path,
) -> None:
    """The guarantee itself, on the schema a deployment runs."""

    _add(migrated, "first.pdf")
    _add(migrated, "second.pdf")

    spent = max(_ids(migrated))
    _sql(migrated, "DELETE FROM documents WHERE id = ?", spent)

    _add(migrated, "third.pdf")

    assert spent not in _ids(migrated)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "Known and unfixed: a downgrade drops SQLite's high-water mark "
        "and the re-upgrade reseeds it from the highest surviving row, "
        "so an id spent on a removed document is reissued. Restoring it "
        "needs an UPDATE or an INSERT, which "
        "test_no_migration_fabricates_an_identity forbids in a "
        "migration - and narrowing that rule is an AF-01 22 decision, "
        "not a thing to settle here. Strict, so whoever fixes the "
        "migration is told this test now passes. `raises` is set so a "
        "broken fixture reports an error rather than quietly counting "
        "as the expected failure."
    ),
)
def test_the_high_water_mark_survives_a_downgrade_and_re_upgrade(
    migrated: Path
) -> None:
    """
    The defect a reviewer found by round-tripping the migration.

    ``downgrade`` rebuilds the table without ``AUTOINCREMENT``, which
    drops the mark SQLite keeps of the highest id it ever issued; a
    later ``upgrade`` reseeds it from the highest *surviving* row. An id
    spent on a document that has since been removed comes back, and the
    next upload inherits that document's ingestion job - the exact
    failure this migration exists to prevent, reintroduced by running it
    twice.

    Downgrading and re-upgrading is a documented operation, so the
    guarantee ought to survive it. It does not. This test is written as
    the assertion that *should* hold and marked expected-to-fail, rather
    than written to assert the broken behaviour: a test that asserted
    the reuse would go green on a defect and quietly become its
    specification.
    """

    _add(migrated, "first.pdf")
    _add(migrated, "second.pdf")

    spent = max(_ids(migrated))
    _sql(migrated, "DELETE FROM documents WHERE id = ?", spent)

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))

    command.downgrade(config, PRIOR_REVISION)
    command.upgrade(config, "head")

    _add(migrated, "third.pdf")

    assert spent not in _ids(migrated)
