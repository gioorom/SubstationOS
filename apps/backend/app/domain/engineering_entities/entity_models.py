"""
Engineering Entities (EPIC 2, Milestone 29.1) - deterministic groupings
of evidence.

## The one distinction this layer exists to make

| Layer | Answers |
|---|---|
| Engineering Evidence | "I observed this, here, under this rule." |
| Engineering Entity | "These observations refer to the same engineering object." |

And, just as importantly, what it does **not** answer:

- "this object feeds another";
- "this object protects another";
- "this object belongs to a bay";
- "this quantity is that object's rating".

Every one of those is a claim about the *installation* rather than about
the document, and each belongs to a later stage that can be reviewed as
reasoning. There is no field in this model in which any of them could be
written, and an architecture test asserts the schema stays that way.

## An entity is a hypothesis, not a graph node

"The designation `T1` appears four times in this document, and those four
observations are one thing" is a *deterministic hypothesis*: it follows
from a stated rule at a stated version, and it can be recomputed. It is
not yet a node in the Project Knowledge Graph, and nothing here writes
one. A later milestone will generate graph nodes from entities - from
these, and from nothing else.

## Entities never own provenance

They **aggregate** it. Each contributing observation is referenced by its
evidence key, together with the location that observation occupied. The
character-level chain stays where it was recorded, on the evidence item,
which remains the authoritative record - an entity that copied it would
become a second source of truth for where a thing was seen.

Every entity can enumerate the evidence that created it, and no entity
exists without at least one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceType,
)


class EntityType(str, Enum):
    """
    The deliberately minimal catalogue this milestone supports.

    There is **no** transformer, breaker, current transformer, voltage
    transformer, relay or cable here. Deciding that ``T1`` names a
    transformer is a classification, and a classification needs a rule
    somebody reviewed and a vocabulary somebody governs. Naming those
    classes now would let the shape of the model imply knowledge the
    system does not have.
    """

    # A designation-like string observed one or more times in a document.
    # Says nothing about what kind of equipment it names.
    EQUIPMENT_DESIGNATION = "equipment_designation"
    # A quantity observed in a document. Says nothing about what it is a
    # property *of*.
    ENGINEERING_QUANTITY = "engineering_quantity"
    # A location aspect observed inside a compound IEC 81346 reference
    # designation - the ``+E01`` of ``+E01-QA1``.
    #
    # Deliberately **not** ``BAY``, ``PANEL`` or ``ROOM``. IEC 81346
    # assigns ``+`` to the location aspect and says nothing about what
    # kind of location it is; deciding that ``+E01`` names a bay is the
    # same classification this catalogue refuses everywhere else. It is
    # a structural object the documents place equipment *in*, and that
    # is all it claims to be.
    STRUCTURAL_LOCATION = "structural_location"


class EntityStatus(str, Enum):
    """
    An entity's status is **derived from its evidence**, never invented.

    A grouping of ambiguous observations is an ambiguous entity: the
    uncertainty recorded at extraction time survives into the hypothesis,
    rather than being laundered away by the act of grouping.
    """

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """
    One contributing observation, as an entity refers to it.

    ``evidence_key`` is the pointer to the authoritative record - the
    evidence item carries the full character-level provenance, and this
    reference deliberately does not copy it. What it does carry is the
    *location*, so an entity can be read and audited without a second
    lookup: which page, paragraph, line and tokens this observation
    occupied.
    """

    evidence_key: str
    evidence_type: EvidenceType
    observed_text: str
    page_number: int
    paragraph_index: int
    line_index: int
    token_start: int
    token_end: int

    @property
    def location(self) -> tuple[int, int, int, int, int]:
        return (
            self.page_number,
            self.paragraph_index,
            self.line_index,
            self.token_start,
            self.token_end,
        )


@dataclass(frozen=True, slots=True)
class EngineeringEntity:
    """
    One deterministic grouping of observations.

    ``designation`` and ``quantity`` are two typed fields rather than one
    untyped value, matching the evidence model: exactly one is populated,
    decided by ``entity_type`` and enforced at construction.

    ``entity_key`` is deterministic - a SHA-256 over the document, the
    evidence source, the rule and version, and what distinguishes this
    entity from its siblings. The same evidence under the same rule
    version always produces the same key, which is what lets the schema
    enforce idempotency rather than merely hope for it.

    ``entity_version`` is the version of *this contract* - the shape of
    an entity - recorded alongside the rule version so a stored entity
    says both which rules produced it and which model it was built under.

    Collections are tuples: nothing about a stored hypothesis should be
    mutable after the fact. Recomputing it from evidence is the only
    legitimate way to change it.
    """

    entity_key: str
    entity_type: EntityType
    status: EntityStatus
    document_id: int
    entity_version: str
    resolution_rule_id: str
    resolution_rule_version: str
    evidence: tuple[EvidenceReference, ...]
    designation: DesignationValue | None = None
    quantity: EngineeringQuantity | None = None

    @property
    def evidence_keys(self) -> tuple[str, ...]:
        """Every observation that created this entity."""

        return tuple(reference.evidence_key for reference in self.evidence)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def locations(self) -> tuple[tuple[int, int, int, int, int], ...]:
        """The aggregated locations of the contributing observations - an
        entity's provenance is exactly the provenance of its evidence,
        and nothing more."""

        return tuple(reference.location for reference in self.evidence)

    @property
    def label(self) -> str:
        """A human-readable rendering, for a report or a list. Derived,
        never stored: it is a way of showing the entity, not a fact about
        it."""

        if self.designation is not None:
            return self.designation.normalized

        if self.quantity is not None:
            return f"{self.quantity.value} {self.quantity.unit}"

        return self.entity_key[:12]


@dataclass(frozen=True, slots=True)
class EngineeringEntitySet:
    """
    Every entity resolved from one evidence set.

    The version fields are what keep a historical set explainable: which
    document, which bytes, which extraction policy produced the evidence,
    and which resolution policy grouped it. A set whose provenance is
    unknown cannot be trusted by the milestone that turns entities into
    graph nodes.

    Deliberately **no timestamp** - two resolutions of the same evidence
    under the same rules must compare equal, and a timestamp would make
    that impossible. When a set was built is a fact about the row.
    """

    document_id: int
    project_id: int | None
    content_checksum: str
    extraction_policy_version: str
    resolution_policy_version: str
    entities: tuple[EngineeringEntity, ...] = ()

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def is_empty(self) -> bool:
        return not self.entities

    def of_type(
        self, entity_type: EntityType
    ) -> tuple[EngineeringEntity, ...]:
        return tuple(
            entity
            for entity in self.entities
            if entity.entity_type is entity_type
        )

    def entity(self, entity_key: str) -> EngineeringEntity | None:
        for entity in self.entities:
            if entity.entity_key == entity_key:
                return entity

        return None
