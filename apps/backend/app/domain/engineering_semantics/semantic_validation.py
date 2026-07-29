"""
Validation of an interpreted semantic set (Milestone 30.1).

Checked *before* anything is stored, because a semantic set is what the
Knowledge Graph will be built from. A set that reached storage citing
facts its source does not contain would surface later as interpreted
knowledge nobody could trace back to a document.

Pure: it reads the set and the fact set it claims to describe, and
returns the first violation or ``None``.
"""

from __future__ import annotations

from app.domain.engineering_facts.fact_models import EngineeringFactSet
from app.domain.engineering_semantics.semantic_failures import (
    SemanticInterpretationFailure,
    SemanticInterpretationFailureCode,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
    EngineeringSemanticStatement,
)
from app.domain.engineering_semantics.semantic_rules import RULES_BY_ID


def validate_semantic_set(
    semantic_set: EngineeringSemanticSet, fact_set: EngineeringFactSet
) -> SemanticInterpretationFailure | None:
    """Return the first violation, or ``None`` if the set is sound."""

    if semantic_set.document_id != fact_set.document_id:
        return _failure(
            SemanticInterpretationFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The semantic set and its facts disagree about which "
            "document they describe.",
        )

    if semantic_set.content_checksum != fact_set.content_checksum:
        return _failure(
            SemanticInterpretationFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            "The semantic set and its facts disagree about which "
            "document version was observed.",
        )

    facts = {fact.fact_key: fact for fact in fact_set.facts}
    seen_keys: set[str] = set()
    seen_subjects: set[tuple[str, str]] = set()

    for statement in semantic_set.statements:
        violation = _validate_statement(statement, facts)

        if violation is not None:
            return violation

        if statement.statement_key in seen_keys:
            return _failure(
                SemanticInterpretationFailureCode.SEMANTIC_VALIDATION_FAILURE,
                f"Two statements share the key "
                f"'{statement.statement_key[:12]}'; semantic identity "
                "must be unique within a set.",
            )

        subject = (
            statement.subject_entity_key,
            statement.statement_type.value,
        )

        if subject in seen_subjects:
            # Two rated powers for one designation. The interpreter is
            # supposed to have declined that as ambiguous, so reaching
            # here is a defect - caught before it can be stored as
            # interpreted knowledge.
            return _failure(
                SemanticInterpretationFailureCode.AMBIGUOUS_SEMANTIC_MAPPING,
                f"Two '{statement.statement_type.value}' statements name "
                "the same subject; which one is meant cannot be decided.",
            )

        seen_keys.add(statement.statement_key)
        seen_subjects.add(subject)

    return None


def _validate_statement(
    statement: EngineeringSemanticStatement, facts: dict
) -> SemanticInterpretationFailure | None:
    rule = RULES_BY_ID.get(statement.semantic_rule_id)

    if rule is None or rule.rule_version != statement.semantic_rule_version:
        return _failure(
            SemanticInterpretationFailureCode.UNSUPPORTED_SEMANTIC_RULE,
            f"A statement cites rule '{statement.semantic_rule_id}' "
            f"version '{statement.semantic_rule_version}', which the "
            "catalogue does not declare.",
        )

    if rule.statement_type is not statement.statement_type:
        return _failure(
            SemanticInterpretationFailureCode.UNSUPPORTED_SEMANTIC_RULE,
            f"Rule '{rule.rule_id}' declares "
            f"'{rule.statement_type.value}' and produced "
            f"'{statement.statement_type.value}'.",
        )

    if not statement.supporting_fact_keys:
        return _failure(
            SemanticInterpretationFailureCode.INVALID_SUPPORT,
            "A statement cites no supporting fact; its meaning would "
            "rest on nothing traceable.",
        )

    if statement.subject_entity_key == statement.object_entity_key:
        return _failure(
            SemanticInterpretationFailureCode.SEMANTIC_VALIDATION_FAILURE,
            "A statement relates an entity to itself.",
        )

    return _validate_support(statement, facts)


def _validate_support(
    statement: EngineeringSemanticStatement, facts: dict
) -> SemanticInterpretationFailure | None:
    """
    Support must be real, and must actually carry the statement.

    Both checks matter. The first says the meaning rests on facts that
    exist; the second says those facts relate the very entities the
    statement names - a statement citing a fact about other equipment
    would be interpreted knowledge attached to the wrong thing.
    """

    for fact_key in statement.supporting_fact_keys:
        fact = facts.get(fact_key)

        if fact is None:
            return _failure(
                SemanticInterpretationFailureCode.INVALID_SUPPORT,
                f"A statement cites fact '{fact_key[:12]}', which is not "
                "in the source fact set.",
            )

        if (
            fact.subject_entity_key != statement.subject_entity_key
            or fact.object_entity_key != statement.object_entity_key
        ):
            return _failure(
                SemanticInterpretationFailureCode.INVALID_SUPPORT,
                "A statement cites a fact that relates different "
                "entities than the statement does.",
            )

    return None


def _failure(
    code: SemanticInterpretationFailureCode, message: str
) -> SemanticInterpretationFailure:
    return SemanticInterpretationFailure(code=code, message=message)
