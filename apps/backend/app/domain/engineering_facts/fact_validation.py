"""
Validation of a constructed fact set (Milestone 29.2).

Checked *before* anything is stored, because a fact set is what a future
milestone will turn into graph edges. A set that reached storage citing
support the entities do not have would surface later as an edge nobody
could trace back to a document.

Pure: it reads the set and the entity set it claims to describe, and
returns the first violation or ``None``.
"""

from __future__ import annotations

from app.domain.engineering_entities.entity_models import (
    EngineeringEntitySet,
)
from app.domain.engineering_facts.fact_construction_rules import RULES_BY_ID
from app.domain.engineering_facts.fact_failures import (
    FactConstructionFailure,
    FactConstructionFailureCode,
)
from app.domain.engineering_facts.fact_models import (
    EngineeringFact,
    EngineeringFactSet,
)


def validate_fact_set(
    fact_set: EngineeringFactSet, entity_set: EngineeringEntitySet
) -> FactConstructionFailure | None:
    """Return the first violation, or ``None`` if the set is sound."""

    if fact_set.document_id != entity_set.document_id:
        return _failure(
            FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The fact set and its entities disagree about which document "
            "they describe.",
        )

    if fact_set.content_checksum != entity_set.content_checksum:
        return _failure(
            FactConstructionFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The fact set and its entities disagree about which document "
            "version was observed.",
        )

    entities = {entity.entity_key: entity for entity in entity_set.entities}
    seen: set[str] = set()

    for fact in fact_set.facts:
        violation = _validate_fact(fact, entities)

        if violation is not None:
            return violation

        if fact.fact_key in seen:
            return _failure(
                FactConstructionFailureCode.FACT_VALIDATION_FAILURE,
                f"Two facts share the key '{fact.fact_key[:12]}'; fact "
                "identity must be unique within a set.",
            )

        seen.add(fact.fact_key)

    return None


def _validate_fact(
    fact: EngineeringFact, entities: dict
) -> FactConstructionFailure | None:
    rule = RULES_BY_ID.get(fact.construction_rule_id)

    if rule is None or rule.rule_version != fact.construction_rule_version:
        return _failure(
            FactConstructionFailureCode.INVALID_CONSTRUCTION_RULE,
            f"A fact cites rule '{fact.construction_rule_id}' version "
            f"'{fact.construction_rule_version}', which the catalogue "
            "does not declare.",
        )

    if rule.predicate is not fact.predicate:
        return _failure(
            FactConstructionFailureCode.INVALID_CONSTRUCTION_RULE,
            f"Rule '{rule.rule_id}' declares '{rule.predicate.value}' "
            f"and produced '{fact.predicate.value}'.",
        )

    if fact.subject_entity_key == fact.object_entity_key:
        return _failure(
            FactConstructionFailureCode.FACT_VALIDATION_FAILURE,
            "A fact associates an entity with itself.",
        )

    subject = entities.get(fact.subject_entity_key)
    obj = entities.get(fact.object_entity_key)

    if subject is None or obj is None:
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A fact cites an entity that is not in the source entity "
            "set.",
        )

    if (
        subject.entity_type is not rule.subject_type
        or obj.entity_type is not rule.object_type
    ):
        return _failure(
            FactConstructionFailureCode.FACT_VALIDATION_FAILURE,
            f"Rule '{rule.rule_id}' associates "
            f"{rule.subject_type.value} with {rule.object_type.value}, "
            f"and produced {subject.entity_type.value} with "
            f"{obj.entity_type.value}.",
        )

    return _validate_support(fact, subject, obj)


def _validate_support(
    fact: EngineeringFact, subject, obj
) -> FactConstructionFailure | None:
    """
    Support must be real, and must actually satisfy the rule.

    Both checks matter. The first says the fact rests on observations its
    entities really have; the second says the same-line rule was really
    applied - a fact whose subject and object support share no line would
    be the rule claiming something it did not do.
    """

    if not fact.support:
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A fact cites no supporting observation; it would rest on "
            "nothing traceable.",
        )

    subject_support = fact.subject_support
    object_support = fact.object_support

    if not subject_support or not object_support:
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A fact must be supported from both sides of the "
            "association.",
        )

    if not {
        reference.evidence_key for reference in subject_support
    } <= set(subject.evidence_keys):
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A fact cites subject support that its subject entity does "
            "not have.",
        )

    if not {
        reference.evidence_key for reference in object_support
    } <= set(obj.evidence_keys):
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A fact cites object support that its object entity does "
            "not have.",
        )

    subject_lines = {reference.location for reference in subject_support}
    object_lines = {reference.location for reference in object_support}

    if not subject_lines & object_lines:
        return _failure(
            FactConstructionFailureCode.INVALID_FACT_SUPPORT,
            "A same-line association cites support that shares no line.",
        )

    return None


def _failure(
    code: FactConstructionFailureCode, message: str
) -> FactConstructionFailure:
    return FactConstructionFailure(code=code, message=message)
