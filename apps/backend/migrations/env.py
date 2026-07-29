import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import the application's Base and every active model module so
# Base.metadata is fully populated before Alembic reads it - the exact
# same import set app/main.py uses to register tables. Keeping this list
# in sync with main.py is a deliberate, documented manual step (see
# docs/architecture/database_migrations.md) - there is no automatic
# model-discovery mechanism in this codebase, and adding one is out of
# this milestone's scope.
from app.database.database import Base, DATABASE_URL
from app.models import (  # noqa: F401
    canonical_pdf,
    canonical_text,
    canonicalization,
    document,
    document_ingestion,
    engineering_entities,
    engineering_evidence,
    engineering_index,
    evidence_evaluation,
    graph_builder,
    knowledge_graph,
    project,
    project_knowledge_graph,
    proposed_claims,
    review_workflow,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Single source of truth for the connection string: app.database.database
# .DATABASE_URL, not a value duplicated into alembic.ini (see alembic.ini's
# own comment on this). SUBSTATIONOS_DATABASE_URL overrides it for a single
# invocation - e.g. generating/testing a migration against a scratch
# database without touching the real one, or pointing at a different
# environment's database. Never required for normal use.
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("SUBSTATIONOS_DATABASE_URL", DATABASE_URL),
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
