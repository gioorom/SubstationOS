"""
The entity resolver (Milestone 29.1) - the pure function that groups
evidence into entities.

```
EngineeringEvidenceSet
   -> designation observations   grouped by the declared key
   -> quantity observations      one entity each
   -> EngineeringEntitySet
```

## Three properties it is built around

1. **It sees only evidence.** The input is an
   ``EngineeringEvidenceSet``. This module imports no canonical text, no
   parser and no storage - it could not look at the document if it wanted
   to, which is what makes "resolution operates only on evidence" a
   structural fact rather than a promise.
2. **Grouping is by declared key.** Every decision comes from
   ``entity_resolution_rules``. There is no similarity score, no edit
   distance and no threshold: two observations are one object because a
   stated rule says so, or they are not.
3. **Nothing is attached to anything.** A quantity observed beside a
   designation produces two entities that do not know about each other.
   ``630 kVA`` next to ``TR1`` is not a transformer rating - that is a
   relationship, and relationships belong to a later stage.

Pure and deterministic: the same evidence set under the same rule
versions produces an equal entity set, every time.
"""

from __future__ import annotations

import hashlib

from app.domain.engineering_entities.entity_models import (
    EngineeringEntity,
    EngineeringEntitySet,
    EntityStatus,
    EntityType,
    EvidenceReference,
)
from app.domain.engineering_entities.entity_policy import (
    ENTITY_MODEL_VERSION,
    RESOLUTION_POLICY_VERSION,
)
from app.domain.engineering_entities.entity_resolution_rules import (
    DESIGNATION_GROUPING_RULE,
    QUANTITY_IDENTITY_RULE,
    ResolutionRule,
    designation_grouping_key,
)
from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidence,
    EngineeringEvidenceSet,
    EvidenceStatus,
    EvidenceType,
)

# Evidence statuses map onto entity statuses one-for-one. An entity's
# status is *derived* from the observations that formed it, never
# invented: grouping ambiguous observations yields an ambiguous
# hypothesis, and laundering that away would be the resolver asserting
# more confidence than the evidence carries.
_STATUS_FOR_EVIDENCE: dict[EvidenceStatus, EntityStatus] = {
    EvidenceStatus.OBSERVED: EntityStatus.RESOLVED,
    EvidenceStatus.AMBIGUOUS: EntityStatus.AMBIGUOUS,
}

_QUANTITY_TYPES = frozenset(
    {
        EvidenceType.VOLTAGE_VALUE,
        EvidenceType.CURRENT_VALUE,
        EvidenceType.POWER_VALUE,
        EvidenceType.CABLE_SECTION_VALUE,
    }
)


def resolve_entities(
    evidence_set: EngineeringEvidenceSet,
    *,
    resolution_policy_version: str = RESOLUTION_POLICY_VERSION,
) -> EngineeringEntitySet:
    """
    Group one evidence set into entities.

    ``REJECTED`` evidence never reaches storage, so anything in a stored
    set is either observed or ambiguous; both resolve, and the entity
    carries the status forward.
    """

    entities: list[EngineeringEntity] = []
    entities.extend(_resolve_designations(evidence_set))
    entities.extend(_resolve_quantities(evidence_set))

    return EngineeringEntitySet(
        document_id=evidence_set.document_id,
        project_id=evidence_set.project_id,
        content_checksum=evidence_set.content_checksum,
        extraction_policy_version=evidence_set.extraction_policy_version,
        resolution_policy_version=resolution_policy_version,
        entities=tuple(entities),
    )


def _resolve_designations(
    evidence_set: EngineeringEvidenceSet,
) -> list[EngineeringEntity]:
    """
    Observations sharing the declared grouping key become one entity.

    Grouped in **first-appearance order**, so an entity set renders the
    same way twice and a diff between two sets shows only real changes.
    """

    groups: dict[tuple[str, str, str], list[EngineeringEvidence]] = {}

    for item in evidence_set.evidence:
        if item.evidence_type is not EvidenceType.DESIGNATION:
            continue

        if item.designation is None:
            # A designation item carrying no designation value would be
            # a malformed evidence record. Skipped rather than guessed
            # at; validation reports it.
            continue

        key = designation_grouping_key(
            item.designation.normalized,
            item.status.value,
            item.rule_version,
        )
        groups.setdefault(key, []).append(item)

    return [
        _entity(
            evidence_set,
            DESIGNATION_GROUPING_RULE,
            items,
            discriminator="|".join(key),
            designation=items[0].designation,
        )
        for key, items in groups.items()
    ]


def _resolve_quantities(
    evidence_set: EngineeringEvidenceSet,
) -> list[EngineeringEntity]:
    """
    Each quantity observation becomes its own entity.

    **Nothing merges two quantities.** Two observations of ``630 kVA`` in
    one document may be one transformer's rating written twice, or two
    transformers with the same rating; the document does not say, and
    neither does this resolver. Merging them would be a guess that
    arrives downstream as one piece of equipment where there were two.
    """

    return [
        _entity(
            evidence_set,
            QUANTITY_IDENTITY_RULE,
            [item],
            discriminator=item.evidence_key,
            quantity=item.quantity,
        )
        for item in evidence_set.evidence
        if item.evidence_type in _QUANTITY_TYPES
    ]


def _entity(
    evidence_set: EngineeringEvidenceSet,
    rule: ResolutionRule,
    items: list[EngineeringEvidence],
    *,
    discriminator: str,
    designation=None,
    quantity=None,
) -> EngineeringEntity:
    return EngineeringEntity(
        entity_key=_entity_key(evidence_set, rule, discriminator),
        entity_type=rule.entity_type,
        status=_STATUS_FOR_EVIDENCE[items[0].status],
        document_id=evidence_set.document_id,
        entity_version=ENTITY_MODEL_VERSION,
        resolution_rule_id=rule.rule_id,
        resolution_rule_version=rule.rule_version,
        evidence=tuple(_reference(item) for item in items),
        designation=designation,
        quantity=quantity,
    )


def _reference(item: EngineeringEvidence) -> EvidenceReference:
    """
    How an entity refers to a contributing observation.

    The evidence key is the pointer to the authoritative record - the
    full character-level provenance stays on the evidence item. What is
    carried here is the location, so an entity can be read and audited
    without a second lookup.
    """

    provenance = item.provenance

    return EvidenceReference(
        evidence_key=item.evidence_key,
        evidence_type=item.evidence_type,
        observed_text=item.observed_text,
        page_number=provenance.page_number,
        paragraph_index=provenance.paragraph_index,
        line_index=provenance.line_index,
        token_start=provenance.token_start,
        token_end=provenance.token_end,
    )


def _entity_key(
    evidence_set: EngineeringEvidenceSet,
    rule: ResolutionRule,
    discriminator: str,
) -> str:
    """
    A deterministic identity for one entity.

    SHA-256 over the document, the exact evidence source, the rule and
    its version, the entity contract version, and whatever distinguishes
    this entity from its siblings. The same evidence under the same rules
    always yields the same key - which is what lets the schema enforce
    idempotency rather than merely hope for it - and a rule version bump
    yields different keys, which is what makes a re-resolution a new set
    rather than a silent rewrite.
    """

    material = "|".join(
        (
            str(evidence_set.document_id),
            evidence_set.content_checksum,
            evidence_set.extraction_policy_version,
            rule.rule_id,
            rule.rule_version,
            ENTITY_MODEL_VERSION,
            rule.entity_type.value,
            discriminator,
        )
    )

    return hashlib.sha256(material.encode("utf-8")).hexdigest()
