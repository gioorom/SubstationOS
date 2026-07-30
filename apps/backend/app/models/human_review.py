"""
Persistence for the Human Review context.

**One table, append-only.** No status column, no `is_current` flag, no
`superseded_at` - every one of those would be a mutable field on a record
that must never be modified, and every one of them would be a second
account of something the history already says.

Three things are deliberately absent, and each absence is structural
rather than conventional:

- **No engineering payload.** No statement type, no subject, no object,
  no quantity, no support. A review names an artefact by key; a column
  holding what the artefact *said* would be a copy of engineering
  knowledge living outside the pipeline that produced it.
- **No foreign key to the semantic tables.** A re-run replaces a semantic
  set, and a constraint would either block the pipeline or cascade a
  historical judgement into nothing. The whole point of the snapshot is
  that a review outlives the artefact it reviewed.
- **No foreign key to ``users``.** The reviewer is denormalised for the
  same reason the audit trail denormalises its actor: the record must
  stay readable after the account is renamed, re-roled or disabled.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ReviewRecord(Base):
    """One recorded engineering judgement. Written once, never updated."""

    __tablename__ = "engineering_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- What was reviewed ----------------------------------------------

    target_type: Mapped[str] = mapped_column(String(40), nullable=False)

    target_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    """
    The artefact's own deterministic key.

    For a semantic statement this is a SHA-256 over the document, the fact
    source, the triple and the rule versions - which is what makes
    "does this review still apply?" a lookup rather than a guess.
    """

    document_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    # --- The judgement ---------------------------------------------------

    decision: Mapped[str] = mapped_column(String(40), nullable=False)

    reason: Mapped[str] = mapped_column(String(60), nullable=False)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Plain text. Never rendered as markup - see ``ReviewComment``."""

    # --- Who, and when ---------------------------------------------------

    reviewer_user_id: Mapped[int] = mapped_column(Integer, nullable=False)

    reviewer_display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    reviewer_email: Mapped[str] = mapped_column(String(254), nullable=False)

    reviewer_role: Mapped[str] = mapped_column(String(40), nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    record_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- The snapshot: what the artefact's identity was at review time ---

    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)

    semantic_rule_id: Mapped[str] = mapped_column(String(120), nullable=False)

    semantic_rule_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    semantic_contract_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    resolution_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    fact_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    semantic_policy_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    support_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    support_count: Mapped[int] = mapped_column(Integer, nullable=False)


#: The history read: every review of one target, newest first.
Index(
    "ix_engineering_reviews_target_history",
    ReviewRecord.document_id,
    ReviewRecord.target_key,
    ReviewRecord.recorded_at.desc(),
)
