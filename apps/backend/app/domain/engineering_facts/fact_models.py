"""
Engineering Facts (EPIC 2, Milestone 29.2) - deterministic structured
associations between resolved entities.

## Four meanings, kept apart

| Layer | Says |
|---|---|
| Evidence | "I observed `TR1` at this location." |
| Entity | "These `TR1` observations refer to one document-scoped object." |
| **Fact** | "This designation entity and this quantity entity satisfy a declared association rule." |
| Graph edge *(later)* | "This equipment has this rated property." |

A fact is **not** a graph edge and **not** a classified property. It
records that a structural rule was satisfied - nothing more. See
``fact_predicates`` for why the predicate is deliberately unable to say
anything stronger.

## Facts invent no provenance

They **aggregate support**: the subject entity, the object entity, and
the evidence observations that put the two together on the same line.
Each support reference carries an evidence key and the location that
observation occupied; the character-level chain stays on the evidence
item, which remains the authoritative record.

Every fact can answer, without a text search: which subject entity,
which object entity, which observations, which rule at which version,
and where in the document those observations occur.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_evidence.evidence_models import EvidenceType
from app.domain.engineering_facts.fact_predicates import FactPredicate


class FactStatus(str, Enum):
    """
    A fact's status is **derived from its entities**, never invented.

    The distinction that matters: this is about the *value* being
    unsettled, not about whether the association holds. A pairing that
    could not be determined produces **no fact at all** - see
    ``AmbiguityReason`` and the construction diagnostics.
    """

    # The rule was satisfied and both contributing entities are
    # themselves resolved.
    CONSTRUCTED = "constructed"
    # The rule was satisfied - the association is real - and one of the
    # contributing entities is itself ambiguous, typically a quantity
    # whose number could not be read exactly. The uncertainty recorded at
    # extraction time survives into the fact rather than being laundered
    # away by the act of associating.
    AMBIGUOUS = "ambiguous"


class SupportRole(str, Enum):
    """Which side of the association an observation supports."""

    SUBJECT = "subject"
    OBJECT = "object"


class AmbiguityReason(str, Enum):
    """
    Why a line that contained candidates produced no fact.

    Recorded as a **diagnostic**, never as a fact. Ambiguous layout must
    not become a confirmed association, and a consumer reading facts must
    not be able to see these at all - which is why they live in their own
    table rather than as facts with a status.
    """

    # Two or more designations and at least one quantity on one line.
    # Which designation the quantity belongs to cannot be determined, and
    # guessing would put a rating on the wrong equipment.
    MULTIPLE_SUBJECTS = "multiple_subjects"


@dataclass(frozen=True, slots=True)
class FactSupport:
    """
    One observation supporting a fact.

    ``evidence_key`` is the pointer to the authoritative evidence
    record. The location is carried so a fact can be read and audited
    without a second lookup - and so the rule that constructed it can be
    re-checked: a same-line rule is only credible if the line it matched
    on is visible.
    """

    evidence_key: str
    role: SupportRole
    evidence_type: EvidenceType
    observed_text: str
    page_number: int
    paragraph_index: int
    line_index: int
    token_start: int
    token_end: int

    @property
    def location(self) -> tuple[int, int, int]:
        """The line this observation sits on - page, paragraph, line."""

        return (self.page_number, self.paragraph_index, self.line_index)


@dataclass(frozen=True, slots=True)
class EngineeringFact:
    """
    One deterministic association.

    Entities are referenced **by key only**. No entity payload is copied
    in: an entity's designation, quantity and evidence live on the entity,
    which stays the single account of what it is, and a fact that carried
    a copy would become a second one that could go stale.

    ``fact_key`` is deterministic - a SHA-256 over the document, the
    exact entity source, the triple, and the rule and contract versions.
    The same entities under the same rules always produce the same key,
    and a rule version bump always produces different ones.
    """

    fact_key: str
    document_id: int
    project_id: int | None
    subject_entity_key: str
    predicate: FactPredicate
    object_entity_key: str
    status: FactStatus
    fact_version: str
    construction_rule_id: str
    construction_rule_version: str
    support: tuple[FactSupport, ...] = ()

    @property
    def support_keys(self) -> tuple[str, ...]:
        return tuple(reference.evidence_key for reference in self.support)

    @property
    def subject_support(self) -> tuple[FactSupport, ...]:
        return tuple(
            reference
            for reference in self.support
            if reference.role is SupportRole.SUBJECT
        )

    @property
    def object_support(self) -> tuple[FactSupport, ...]:
        return tuple(
            reference
            for reference in self.support
            if reference.role is SupportRole.OBJECT
        )

    @property
    def supporting_lines(self) -> tuple[tuple[int, int, int], ...]:
        """The distinct lines on which this association was observed, in
        first-appearance order."""

        seen: list[tuple[int, int, int]] = []

        for reference in self.support:
            if reference.location not in seen:
                seen.append(reference.location)

        return tuple(seen)


@dataclass(frozen=True, slots=True)
class FactConstructionDiagnostic:
    """
    A line that held candidates and produced no fact.

    Deliberately **not** a fact and deliberately not shaped like one: it
    names no subject and no object, because the whole point is that which
    is which could not be determined. It exists so an engineer can see
    where the rules declined, rather than wondering why a page produced
    nothing.
    """

    reason: AmbiguityReason
    page_number: int
    paragraph_index: int
    line_index: int
    subject_entity_keys: tuple[str, ...]
    object_entity_keys: tuple[str, ...]

    @property
    def location(self) -> tuple[int, int, int]:
        return (self.page_number, self.paragraph_index, self.line_index)


@dataclass(frozen=True, slots=True)
class EngineeringFactSet:
    """
    Every fact constructed from one entity set.

    The version fields identify the exact source and rules: which
    document, which bytes, which extraction policy read them, which
    resolution policy produced the entities, and which construction
    policy associated them.

    ``extraction_policy_version`` is ``None`` only for a set stored
    before that provenance was recorded. Unknown is not a value: such a
    set can never prove a later reuse is valid, and is recomputed rather
    than trusted. A fact set whose
    provenance is unknown could not be compared with another or trusted
    by the milestone that turns facts into graph edges.

    Deliberately **no timestamp** - two constructions over the same
    entities under the same rules must compare equal.
    """

    document_id: int
    project_id: int | None
    content_checksum: str
    extraction_policy_version: str | None
    resolution_policy_version: str
    fact_policy_version: str
    facts: tuple[EngineeringFact, ...] = ()
    diagnostics: tuple[FactConstructionDiagnostic, ...] = ()

    #: This artifact's deterministic identity, and the identity of the
    #: artifact it was derived from. ``None`` only for a row stored
    #: before the identity chain existed: unknown is not a value, and an
    #: artifact that cannot say what it was derived from can never prove
    #: a reuse is valid. See ``app/domain/artifact_identity``.
    artifact_identity: str | None = None
    upstream_identity: str | None = None

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    @property
    def is_empty(self) -> bool:
        return not self.facts

    @property
    def has_ambiguities(self) -> bool:
        return bool(self.diagnostics)

    def fact(self, fact_key: str) -> EngineeringFact | None:
        for fact in self.facts:
            if fact.fact_key == fact_key:
                return fact

        return None

    def facts_for_subject(
        self, subject_entity_key: str
    ) -> tuple[EngineeringFact, ...]:
        return tuple(
            fact
            for fact in self.facts
            if fact.subject_entity_key == subject_entity_key
        )
