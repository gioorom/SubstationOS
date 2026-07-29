"""
The fact constructor (Milestone 29.2) - the pure function that turns an
entity set into associations.

```
EngineeringEntitySet
   -> index every entity's observations by the line they occur on
   -> for each line: apply the declared cardinality policy
   -> accumulate the support for each associated pair
   -> EngineeringFactSet
```

## What it sees, and what it cannot

Its input is an entity set. This module imports no canonical text, no
parser and no storage - it could not look at the document if it wanted
to. The only structural information it uses is the location each entity
already carries on its contributing evidence, recorded at extraction
time.

## Support accumulates; the fact key excludes the line

A fact is identified by its triple, not by where it was seen, and its
support is everything that put the pair together. So a designation
written twice on one line contributes **both** observations to one fact
rather than producing two - and were a pair ever to co-occur on two
lines, that would likewise be one association observed twice.

With the rules that ship today the second case does not arise: each
quantity observation resolves to its own entity (Milestone 29.1's
``quantity_identity``), so a quantity entity exists on exactly one line.
Accumulating support rather than overwriting it is what keeps that an
implementation detail of the entity rules rather than an assumption baked
into this one.

## Ambiguity produces nothing

A line with two or more designations yields no fact and one diagnostic.
The diagnostic is not a fact with a softer status - it names no subject
and no object, because which is which is precisely what could not be
determined.

A pair refused on an ambiguous line may still be confirmed from a
different, unambiguous line. That is correct: the rule was satisfied
there, and the diagnostic still records where it was not.
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
from app.domain.engineering_facts.fact_construction_rules import (
    SAME_LINE_ASSOCIATION_RULE,
    FactConstructionRule,
)
from app.domain.engineering_facts.fact_models import (
    AmbiguityReason,
    EngineeringFact,
    EngineeringFactSet,
    FactConstructionDiagnostic,
    FactStatus,
    FactSupport,
    SupportRole,
)
from app.domain.engineering_facts.fact_policy import (
    FACT_CONTRACT_VERSION,
    FACT_POLICY_VERSION,
)

_Line = tuple[int, int, int]

# An entity's own status decides the fact's, exactly as an evidence
# status decided the entity's. Grouping never adds certainty: a fact
# built on an ambiguous quantity is an ambiguous fact.
_STATUS_FOR_ENTITY: dict[EntityStatus, FactStatus] = {
    EntityStatus.RESOLVED: FactStatus.CONSTRUCTED,
    EntityStatus.AMBIGUOUS: FactStatus.AMBIGUOUS,
}


def construct_facts(
    entity_set: EngineeringEntitySet,
    *,
    fact_policy_version: str = FACT_POLICY_VERSION,
) -> EngineeringFactSet:
    """
    Construct associations from one entity set.

    Pure and deterministic: the same entities under the same rules
    produce an equal fact set, every time.
    """

    rule = SAME_LINE_ASSOCIATION_RULE
    subjects = _by_line(entity_set, rule.subject_type)
    objects = _by_line(entity_set, rule.object_type)

    support: dict[tuple[str, str], list[FactSupport]] = {}
    pairs: dict[tuple[str, str], tuple] = {}
    diagnostics: list[FactConstructionDiagnostic] = []

    for line in sorted(set(subjects) & set(objects)):
        line_subjects = subjects[line]
        line_objects = objects[line]

        if len(line_subjects) > 1:
            # Which designation the quantity belongs to cannot be
            # determined. Guessing would put a rating on the wrong
            # equipment - invisible in a graph, expensive in a
            # substation.
            diagnostics.append(
                _diagnostic(line, line_subjects, line_objects)
            )
            continue

        subject, subject_references = next(iter(line_subjects.values()))

        for obj, object_references in line_objects.values():
            pair = (subject.entity_key, obj.entity_key)
            pairs.setdefault(pair, (subject, obj))
            support.setdefault(pair, []).extend(
                [
                    _support(reference, SupportRole.SUBJECT)
                    for reference in subject_references
                ]
                + [
                    _support(reference, SupportRole.OBJECT)
                    for reference in object_references
                ]
            )

    facts = tuple(
        _fact(
            entity_set,
            rule,
            subject,
            obj,
            tuple(support[pair]),
        )
        for pair, (subject, obj) in pairs.items()
    )

    return EngineeringFactSet(
        document_id=entity_set.document_id,
        project_id=entity_set.project_id,
        content_checksum=entity_set.content_checksum,
        resolution_policy_version=entity_set.resolution_policy_version,
        fact_policy_version=fact_policy_version,
        facts=facts,
        diagnostics=tuple(diagnostics),
    )


def _by_line(
    entity_set: EngineeringEntitySet, entity_type: EntityType
) -> dict[
    _Line,
    dict[str, tuple[EngineeringEntity, list[EvidenceReference]]],
]:
    """
    Every entity of a type, indexed by each line its observations occur
    on, and then by entity.

    Indexed **by entity rather than by observation** on purpose. A
    designation written twice on one line - ``Trasformatore TR1, sigla
    TR1, 630 kVA`` - is one subject observed twice, not two subjects.
    Counting observations would report that line as ambiguous and decline
    a perfectly determinate association.

    An entity observed on three lines appears under three keys: it can
    take part in an association on any line where it was actually seen,
    and nowhere else.
    """

    index: dict[
        _Line,
        dict[str, tuple[EngineeringEntity, list[EvidenceReference]]],
    ] = {}

    for entity in entity_set.of_type(entity_type):
        for reference in entity.evidence:
            line = (
                reference.page_number,
                reference.paragraph_index,
                reference.line_index,
            )
            on_line = index.setdefault(line, {})
            _, references = on_line.setdefault(
                entity.entity_key, (entity, [])
            )
            references.append(reference)

    return index


def _fact(
    entity_set: EngineeringEntitySet,
    rule: FactConstructionRule,
    subject: EngineeringEntity,
    obj: EngineeringEntity,
    support: tuple[FactSupport, ...],
) -> EngineeringFact:
    return EngineeringFact(
        fact_key=_fact_key(entity_set, rule, subject, obj),
        document_id=entity_set.document_id,
        project_id=entity_set.project_id,
        subject_entity_key=subject.entity_key,
        predicate=rule.predicate,
        object_entity_key=obj.entity_key,
        status=_status(subject, obj),
        fact_version=FACT_CONTRACT_VERSION,
        construction_rule_id=rule.rule_id,
        construction_rule_version=rule.rule_version,
        support=support,
    )


def _status(
    subject: EngineeringEntity, obj: EngineeringEntity
) -> FactStatus:
    """Ambiguous if either contributing entity is - grouping never adds
    certainty that the evidence did not carry."""

    if EntityStatus.AMBIGUOUS in (subject.status, obj.status):
        return FactStatus.AMBIGUOUS

    return _STATUS_FOR_ENTITY[subject.status]


def _support(
    reference: EvidenceReference, role: SupportRole
) -> FactSupport:
    return FactSupport(
        evidence_key=reference.evidence_key,
        role=role,
        evidence_type=reference.evidence_type,
        observed_text=reference.observed_text,
        page_number=reference.page_number,
        paragraph_index=reference.paragraph_index,
        line_index=reference.line_index,
        token_start=reference.token_start,
        token_end=reference.token_end,
    )


def _diagnostic(
    line: _Line,
    subjects: dict,
    objects: dict,
) -> FactConstructionDiagnostic:
    page, paragraph, line_index = line

    return FactConstructionDiagnostic(
        reason=AmbiguityReason.MULTIPLE_SUBJECTS,
        page_number=page,
        paragraph_index=paragraph,
        line_index=line_index,
        subject_entity_keys=tuple(subjects),
        object_entity_keys=tuple(objects),
    )


def _fact_key(
    entity_set: EngineeringEntitySet,
    rule: FactConstructionRule,
    subject: EngineeringEntity,
    obj: EngineeringEntity,
) -> str:
    """
    A deterministic identity for one association.

    SHA-256 over the document, the exact entity source, the triple, and
    the rule and contract versions. The same entities under the same
    rules always yield the same key - which lets the schema enforce
    idempotency - and a rule or contract version bump yields different
    ones, which makes a re-construction a new set rather than a silent
    rewrite.

    The **line is deliberately absent**: an association observed on two
    lines is one association observed twice, and including the line would
    split it into two facts saying the same thing.
    """

    material = "|".join(
        (
            str(entity_set.document_id),
            entity_set.content_checksum,
            entity_set.resolution_policy_version,
            subject.entity_key,
            rule.predicate.value,
            obj.entity_key,
            rule.rule_id,
            rule.rule_version,
            FACT_CONTRACT_VERSION,
        )
    )

    return hashlib.sha256(material.encode("utf-8")).hexdigest()
