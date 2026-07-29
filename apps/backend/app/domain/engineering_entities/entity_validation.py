"""
Validation of a resolved entity set (Milestone 29.1).

Checked *before* anything is stored, because an entity set is what a
future milestone will turn into graph nodes. A set that reached storage
citing evidence that is not in its source would surface later as a node
nobody could trace back to a document.

Pure: it reads the set and the evidence set it claims to describe, and
returns the first violation or ``None``.
"""

from __future__ import annotations

from app.domain.engineering_entities.entity_failures import (
    EntityResolutionFailure,
    EntityResolutionFailureCode,
)
from app.domain.engineering_entities.entity_models import (
    EngineeringEntity,
    EngineeringEntitySet,
    EntityType,
)
from app.domain.engineering_entities.entity_resolution_rules import (
    RULES_BY_ID,
)
from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidenceSet,
)


def validate_entity_set(
    entity_set: EngineeringEntitySet,
    evidence_set: EngineeringEvidenceSet,
) -> EntityResolutionFailure | None:
    """Return the first violation, or ``None`` if the set is sound."""

    if entity_set.document_id != evidence_set.document_id:
        return _failure(
            EntityResolutionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The entity set and its evidence disagree about which "
            "document they describe.",
        )

    if entity_set.content_checksum != evidence_set.content_checksum:
        return _failure(
            EntityResolutionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The entity set and its evidence disagree about which "
            "document version was observed.",
        )

    available = {item.evidence_key for item in evidence_set.evidence}
    seen: set[str] = set()

    for entity in entity_set.entities:
        violation = _validate_entity(entity, available)

        if violation is not None:
            return violation

        if entity.entity_key in seen:
            return _failure(
                EntityResolutionFailureCode.ENTITY_VALIDATION_FAILURE,
                f"Two entities share the key '{entity.entity_key[:12]}'; "
                "entity identity must be unique within a set.",
            )

        seen.add(entity.entity_key)

    return None


def _validate_entity(
    entity: EngineeringEntity, available: set[str]
) -> EntityResolutionFailure | None:
    rule = RULES_BY_ID.get(entity.resolution_rule_id)

    if rule is None or rule.rule_version != entity.resolution_rule_version:
        return _failure(
            EntityResolutionFailureCode.INVALID_RESOLUTION_RULE,
            f"Entity '{entity.label}' cites rule "
            f"'{entity.resolution_rule_id}' version "
            f"'{entity.resolution_rule_version}', which the catalogue "
            "does not declare.",
        )

    if rule.entity_type is not entity.entity_type:
        return _failure(
            EntityResolutionFailureCode.INVALID_RESOLUTION_RULE,
            f"Rule '{rule.rule_id}' declares "
            f"'{rule.entity_type.value}' and produced "
            f"'{entity.entity_type.value}'.",
        )

    if not entity.evidence:
        # An entity with no contributing evidence is an assertion, not a
        # hypothesis - there would be nothing to trace it back to.
        return _failure(
            EntityResolutionFailureCode.ENTITY_VALIDATION_FAILURE,
            f"Entity '{entity.label}' cites no contributing evidence.",
        )

    unknown = [
        key for key in entity.evidence_keys if key not in available
    ]

    if unknown:
        return _failure(
            EntityResolutionFailureCode.ENTITY_VALIDATION_FAILURE,
            f"Entity '{entity.label}' cites evidence that is not in the "
            f"source set: {unknown[0][:12]}.",
        )

    return _validate_value(entity)


def _validate_value(
    entity: EngineeringEntity,
) -> EntityResolutionFailure | None:
    """Exactly one typed value, matching the entity type."""

    if entity.entity_type is EntityType.EQUIPMENT_DESIGNATION:
        if entity.designation is None or entity.quantity is not None:
            return _failure(
                EntityResolutionFailureCode.ENTITY_VALIDATION_FAILURE,
                f"Designation entity '{entity.label}' does not carry "
                "exactly a designation value.",
            )

        return None

    if entity.quantity is None or entity.designation is not None:
        return _failure(
            EntityResolutionFailureCode.ENTITY_VALIDATION_FAILURE,
            f"Quantity entity '{entity.label}' does not carry exactly a "
            "quantity value.",
        )

    return None


def _failure(
    code: EntityResolutionFailureCode, message: str
) -> EntityResolutionFailure:
    return EntityResolutionFailure(code=code, message=message)
