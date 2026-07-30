"""add identity, authentication sessions, audit events and project owner

EPIC 30.3: the tables that make an action attributable to a verified
person.

**Almost purely additive.** Three new tables and one new nullable column
on ``projects``. No existing column is altered, no existing row is
rewritten, and nothing in the engineering pipeline is touched - by
design. An `EngineeringEntity`, an `EngineeringFact` and a
`SemanticStatement` are functions of the document's bytes and the
versioned rules that read them, and if a user id appeared on any of them
the pipeline would stop being deterministic. Identity attaches to
*actions*, which is what ``audit_events`` records.

Three things that are deliberately **not** columns here:

- **No plaintext password**, and no reversibly encrypted one. ``users``
  stores the output of a salted, memory-hard key derivation, in a
  self-describing form (``algorithm$parameters$salt$digest``) so the cost
  can be raised - or the algorithm replaced - without a migration and
  without forcing a password reset.
- **No session token.** ``authentication_sessions`` stores a SHA-256
  fingerprint of a token it cannot reproduce. A copy of this database is
  therefore not a set of live logins.
- **No foreign key from ``audit_events`` to ``users``.** The trail must
  stay writable and readable regardless of what happens to the identities
  it records, and a constraint would make the record depend on the thing
  it exists to outlive.

``projects.owner_user_id`` is nullable, and stays nullable. Every project
created before this milestone has no owner and cannot honestly be given
one - inventing an owner would be recording a fact nobody established.
The application treats an unowned project as administrable by any
authenticated engineer, which is exactly the behaviour those projects had
yesterday.

Revision ID: a4c81f2b90de
Revises: 7300ff6a7531
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c81f2b90de"
down_revision: Union[str, None] = "7300ff6a7531"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "encoded_credential", sa.String(length=512), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "credential_updated_at", sa.DateTime(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"])

    # Unique at the database, not in application code: two registrations
    # of the same address racing must not both succeed, and only a
    # constraint can promise that.
    op.create_index(
        op.f("ix_users_email"), "users", ["email"], unique=True
    )

    op.create_table(
        "authentication_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "token_fingerprint", sa.String(length=64), nullable=False
        ),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_authentication_sessions_id"),
        "authentication_sessions",
        ["id"],
    )
    op.create_index(
        op.f("ix_authentication_sessions_user_id"),
        "authentication_sessions",
        ["user_id"],
    )

    # The lookup on every authenticated request. Unique because two
    # sessions sharing a fingerprint would mean two sharing a token.
    op.create_index(
        op.f("ix_authentication_sessions_token_fingerprint"),
        "authentication_sessions",
        ["token_fingerprint"],
        unique=True,
    )
    op.create_index(
        "ix_authentication_sessions_user_live",
        "authentication_sessions",
        ["user_id", "revoked_at"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("actor_authenticated", sa.Boolean(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_session_id", sa.Integer(), nullable=True),
        sa.Column(
            "actor_description", sa.String(length=300), nullable=False
        ),
        sa.Column("resource_type", sa.String(length=60), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_id"), "audit_events", ["id"])
    op.create_index(
        op.f("ix_audit_events_occurred_at"),
        "audit_events",
        ["occurred_at"],
    )
    op.create_index(
        op.f("ix_audit_events_action"), "audit_events", ["action"]
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_id"),
        "audit_events",
        ["actor_user_id"],
    )

    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("owner_user_id", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    """
    Reverses the schema change.

    Note what this cannot reverse: dropping ``audit_events`` destroys the
    record of who did what. That is inherent to removing an audit table
    and is stated here so nobody discovers it by running this.
    """

    with op.batch_alter_table("projects") as batch:
        batch.drop_column("owner_user_id")

    op.drop_index(op.f("ix_audit_events_actor_user_id"), "audit_events")
    op.drop_index(op.f("ix_audit_events_action"), "audit_events")
    op.drop_index(op.f("ix_audit_events_occurred_at"), "audit_events")
    op.drop_index(op.f("ix_audit_events_id"), "audit_events")
    op.drop_table("audit_events")

    op.drop_index(
        "ix_authentication_sessions_user_live", "authentication_sessions"
    )
    op.drop_index(
        op.f("ix_authentication_sessions_token_fingerprint"),
        "authentication_sessions",
    )
    op.drop_index(
        op.f("ix_authentication_sessions_user_id"),
        "authentication_sessions",
    )
    op.drop_index(
        op.f("ix_authentication_sessions_id"), "authentication_sessions"
    )
    op.drop_table("authentication_sessions")

    op.drop_index(op.f("ix_users_email"), "users")
    op.drop_index(op.f("ix_users_id"), "users")
    op.drop_table("users")
