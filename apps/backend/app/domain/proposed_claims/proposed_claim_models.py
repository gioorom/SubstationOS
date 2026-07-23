from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.proposed_claims.claim_type import ClaimType


@dataclass(frozen=True, slots=True)
class ClaimSubject:
    """What the claim is about, e.g. "Cable C-295"."""

    value: str


@dataclass(frozen=True, slots=True)
class ClaimPredicate:
    """
    What the claim asserts about the subject: a relationship verb
    (``FEEDS``) for ``ClaimType.RELATIONSHIP``, or an attribute name
    (``rated_voltage``) for ``ClaimType.ATTRIBUTE``. Free text, not a
    canonical vocabulary - a ``ProposedClaim`` is a candidate statement,
    not a Canonical Domain concept (ADR-0003 governs that separately).
    """

    value: str


@dataclass(frozen=True, slots=True)
class ClaimObject:
    """
    What the claim asserts the subject relates to or has: an entity
    reference (``Transformer TR-02``) for ``ClaimType.RELATIONSHIP``, or
    a value (``132kV``) for ``ClaimType.ATTRIBUTE``.
    """

    value: str


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """
    One Engineering Index entry a ``ProposedClaim`` cites as support.
    ``document_id`` and ``locator`` are a snapshot taken from the
    referenced entry at claim-creation time - the same denormalization
    ``IndexEntry`` itself uses for ``project_id``/``document_id`` - so a
    claim can answer "which document, where" without a join back into
    the Engineering Index. Nothing else about the entry (kind,
    identifier, label) is copied here.
    """

    engineering_index_entry_id: int
    document_id: int
    locator: IndexEntryLocator

    @property
    def locator_kind(self) -> IndexEntryLocatorKind:
        return self.locator.kind

    @property
    def locator_value(self) -> str | None:
        return self.locator.value


@dataclass(frozen=True, slots=True)
class ProposedClaim:
    """
    One engineering statement extracted from one or more Engineering
    Index entries (Milestone 10.1). A ``ProposedClaim`` is not
    authoritative and is not part of the Project Knowledge Graph - it is
    the unit the Review Workflow reviews. Once ``APPROVED`` (a fact
    Review Workflow owns, not this bounded context), a future
    canonicalization service (Milestone 11) is what promotes it into the
    Graph.

    ``project_id`` is derived from, and guaranteed equal to, every
    evidence entry's own ``project_id`` (enforced by
    ``ProposedClaimValidator.validate_evidence_same_project`` at
    construction) - a claim can never span projects.

    ``id`` is ``None`` for a claim that has not yet been persisted.
    Frozen and immutable, like every other domain object in this
    codebase: replacing evidence produces a new instance
    (``ProposedClaimFactory.with_evidence``), it never mutates one in
    place.
    """

    id: int | None
    project_id: int
    claim_type: ClaimType
    subject: ClaimSubject
    predicate: ClaimPredicate | None
    object: ClaimObject | None
    evidence: tuple[EvidenceReference, ...]
    created_at: datetime
    updated_at: datetime
