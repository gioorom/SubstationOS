"""
Persistence for the identity context.

Two tables, and one column that is deliberately absent from both: there
is no plaintext password anywhere, and no session token. ``users`` stores
a self-describing hash; ``authentication_sessions`` stores a SHA-256
fingerprint of a token it can never reproduce.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class UserRecord(Base):
    """One person who may authenticate."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        unique=True,
        index=True,
    )
    """
    Stored lower-cased and unique.

    The uniqueness is the **database's**, not a read-then-write in
    application code: two registrations of the same address racing must
    not both succeed, and only a constraint can promise that.
    """

    display_name: Mapped[str] = mapped_column(String(120), nullable=False)

    role: Mapped[str] = mapped_column(String(40), nullable=False)
    """
    The role's value, as a string.

    Deliberately not a database enum: adding a role would otherwise be a
    schema migration on several dialects, and the domain's ``Role`` is
    already the authority on which values are legal.
    """

    status: Mapped[str] = mapped_column(String(40), nullable=False)

    encoded_credential: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    """
    ``algorithm$parameters$salt$digest``.

    Never a password, never reversible, and never returned by any schema
    in ``app/schemas`` - a test asserts no response model declares a
    field whose name contains ``credential`` or ``password``.
    """

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    credential_updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class AuthenticationSessionRecord(Base):
    """One login, live until it is revoked or its clocks run out."""

    __tablename__ = "authentication_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    token_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    """
    SHA-256 of the session token, hex encoded.

    The token itself has no column and never will. This is the reason a
    copy of the database is not a set of live logins.
    """

    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


Index(
    "ix_authentication_sessions_user_live",
    AuthenticationSessionRecord.user_id,
    AuthenticationSessionRecord.revoked_at,
)


class AuditEventRecord(Base):
    """
    One recorded action. Append-only.

    Lives here rather than in an ``audit`` module of its own so the
    mapper configuration stays in one import, but it belongs to the audit
    bounded context and its repository is the only thing that writes it.

    ``actor_user_id`` is deliberately **not** a foreign key. An audit row
    must remain writable and readable regardless of what happens to the
    user afterwards, and a constraint here would make the trail depend on
    the identities it exists to outlive.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)

    outcome: Mapped[str] = mapped_column(String(20), nullable=False)

    actor_authenticated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    actor_session_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    actor_description: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)

    resource_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
