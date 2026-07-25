from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    EvidenceReference,
)


@dataclass(frozen=True, slots=True)
class CanonicalEntityReference:
    """
    The normalized identity of an engineering object, e.g. "Cable 295",
    "C-295", and "C295" all normalize to ``entity_type="CABLE"``,
    ``canonical_id="C-295"``. Produced only by
    ``canonicalization_normalizer.normalize_entity_reference`` -
    deterministic string normalization, never fuzzy matching, never AI.
    """

    entity_type: str
    canonical_id: str

    @property
    def value(self) -> str:
        """The fully-qualified reference, e.g. "CABLE:C-295"."""

        return f"{self.entity_type}:{self.canonical_id}"


@dataclass(frozen=True, slots=True)
class CanonicalPredicate:
    """
    A normalized relationship verb for a ``ClaimType.RELATIONSHIP``
    fact, e.g. "feeds"/"supplies"/"energizes" all normalize to
    ``"FEEDS"``.
    """

    value: str


@dataclass(frozen=True, slots=True)
class CanonicalAttribute:
    """
    A normalized attribute name for a ``ClaimType.ATTRIBUTE`` fact, e.g.
    "Rated Voltage" normalizes to ``"rated_voltage"``. Format
    normalization only (case, separators) - folding synonyms onto real
    Canonical Domain attribute ids (``app/domain/ontology/**``) is future
    integration work, out of scope for this milestone.
    """

    value: str


@dataclass(frozen=True, slots=True)
class CanonicalValue:
    """
    The normalized value asserted by a ``ClaimType.ATTRIBUTE`` fact,
    e.g. ``"132kV"``. Whitespace-trimmed only - no unit parsing or
    conversion, which would require domain knowledge this bounded
    context deliberately does not consult (see module docstring).
    """

    value: str


@dataclass(frozen=True, slots=True)
class CanonicalProvenance:
    """
    The chain of custody a ``CanonicalFact`` carries forward from Review
    Workflow: who approved the Proposed Claim it was canonicalized from,
    and when. Distinct from the bare ``proposed_claim_id``/
    ``review_candidate_id`` references also on ``CanonicalFact`` - those
    are identifiers; this is provenance.
    """

    reviewed_by: str
    reviewed_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalFact:
    """
    One canonicalized engineering statement, produced from exactly one
    ``APPROVED`` Review Candidate. A ``CanonicalFact`` is an
    intermediate object: it has no graph identifier and no graph edges
    (ADR-0002's Index/Graph separation, extended here) - the Project
    Knowledge Graph (Milestone 11.1) is what turns a ``CanonicalFact``
    into a graph node/edge, not this bounded context.

    ``predicate``/``object`` follow ``claim_type``, mirroring
    ``ProposedClaim``'s own shape (see
    ``app.domain.proposed_claims.proposed_claim_models.ProposedClaim``):

    - ``RELATIONSHIP`` - ``predicate`` is a ``CanonicalPredicate``,
      ``object`` is a ``CanonicalEntityReference``.
    - ``ATTRIBUTE`` - ``predicate`` is a ``CanonicalAttribute``,
      ``object`` is a ``CanonicalValue``.
    - ``EXISTENCE`` - ``predicate`` and ``object`` are both ``None``.

    ``evidence`` is copied unchanged from the source ``ProposedClaim`` -
    canonicalization normalizes the statement, it does not touch what
    supports it. ``id`` is ``None`` for a fact that has not yet been
    persisted.
    """

    id: int | None
    project_id: int
    claim_type: ClaimType
    subject: CanonicalEntityReference
    predicate: CanonicalPredicate | CanonicalAttribute | None
    object: CanonicalEntityReference | CanonicalValue | None
    proposed_claim_id: int
    review_candidate_id: int
    evidence: tuple[EvidenceReference, ...]
    provenance: CanonicalProvenance
    created_at: datetime

    @property
    def predicate_value(self) -> str | None:
        """The bare normalized string, regardless of whether
        ``predicate`` is a ``CanonicalPredicate`` or
        ``CanonicalAttribute`` - a read-side convenience mirroring
        ``EvidenceReference.locator_kind``/``locator_value``."""

        return self.predicate.value if self.predicate is not None else None

    @property
    def object_entity(self) -> CanonicalEntityReference | None:
        """``object`` narrowed to a ``CanonicalEntityReference``, or
        ``None`` for an ATTRIBUTE or EXISTENCE fact."""

        return (
            self.object
            if isinstance(self.object, CanonicalEntityReference)
            else None
        )

    @property
    def object_value(self) -> str | None:
        """``object`` narrowed to a ``CanonicalValue``'s bare string, or
        ``None`` for a RELATIONSHIP or EXISTENCE fact."""

        return (
            self.object.value
            if isinstance(self.object, CanonicalValue)
            else None
        )

    @property
    def reviewed_by(self) -> str:
        return self.provenance.reviewed_by

    @property
    def reviewed_at(self) -> datetime:
        return self.provenance.reviewed_at


@dataclass(frozen=True, slots=True)
class CanonicalizationResult:
    """
    The outcome of canonicalizing one approved Review Candidate: the
    resulting ``CanonicalFact``, and whether this call actually produced
    a new fact (``created=True``) or idempotently returned an
    already-canonicalized one for the same Review Candidate
    (``created=False``). Canonicalizing the same approved candidate more
    than once never creates a duplicate fact.
    """

    fact: CanonicalFact
    created: bool
