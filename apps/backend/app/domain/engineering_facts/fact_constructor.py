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

from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
)
from app.domain.engineering_facts.fact_identity import (
    fact_set_identity,
)
from app.domain.engineering_entities.entity_models import (
    EngineeringEntity,
    EngineeringEntitySet,
    EntityStatus,
    EntityType,
    EvidenceReference,
)
from app.domain.engineering_facts.fact_construction_rules import (
    CONSTRUCTION_RULES,
    CardinalityPolicy,
    FactConstructionRule,
    StructuralScope,
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

#: The structural unit an index is keyed by. A line is three numbers; a
#: token is those three plus its own start and end, which is why one
#: variable-length tuple types both rather than two aliases that would
#: have to be kept in step.
_Unit = tuple[int, ...]

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

    facts: list[EngineeringFact] = []
    diagnostics: list[FactConstructionDiagnostic] = []

    # The catalogue is applied in its declared order, and each rule is
    # applied independently. A rule never sees another rule's facts:
    # composing two associations into a third is inference, and it
    # belongs to a reasoning layer that reads governed knowledge, not to
    # a constructor that reads entities.
    for rule in CONSTRUCTION_RULES:
        rule_facts, rule_diagnostics = _apply(entity_set, rule)
        facts.extend(rule_facts)
        diagnostics.extend(rule_diagnostics)

    # The identity chain, carried forward where the derivation happens.
    # The upstream artifact already knows its own identity; this one is
    # composed from it and this stage's own contract, so anything built
    # through the domain knows what it came from.
    upstream = (
        None
        if entity_set.artifact_identity is None
        else ArtifactIdentity(
            value=entity_set.artifact_identity,
            kind=ArtifactKind.ENTITY_SET,
            contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
        )
    )
    identity = (
        None
        if upstream is None
        else fact_set_identity(
            entity_set=upstream,
            fact_policy_version=fact_policy_version,
            fact_contract_version=FACT_CONTRACT_VERSION,
        )
    )

    return EngineeringFactSet(
        artifact_identity=None if identity is None else identity.value,
        upstream_identity=entity_set.artifact_identity,
        document_id=entity_set.document_id,
        project_id=entity_set.project_id,
        content_checksum=entity_set.content_checksum,
        extraction_policy_version=entity_set.extraction_policy_version,
        resolution_policy_version=entity_set.resolution_policy_version,
        fact_policy_version=fact_policy_version,
        facts=tuple(facts),
        diagnostics=tuple(diagnostics),
    )


def _apply(
    entity_set: EngineeringEntitySet, rule: FactConstructionRule
) -> tuple[list[EngineeringFact], list[FactConstructionDiagnostic]]:
    """
    One rule, over one entity set.

    The cardinality policy decides what an over-full unit means, and the
    two policies mean different things by it. On a line, two designations
    and a quantity is a **real ambiguity worth reporting** - the document
    said something and this system could not tell what. Within a token
    the same shape cannot arise from any document, so there is nothing to
    report and no diagnostic is produced: a diagnostic for an impossible
    state would be noise that outlived everyone who could explain it.
    """

    subjects = _by_unit(entity_set, rule.subject_type, rule.scope)
    objects = _by_unit(entity_set, rule.object_type, rule.scope)

    support: dict[tuple[str, str], list[FactSupport]] = {}
    pairs: dict[tuple[str, str], tuple] = {}
    diagnostics: list[FactConstructionDiagnostic] = []

    for unit in sorted(set(subjects) & set(objects)):
        unit_subjects = subjects[unit]
        unit_objects = objects[unit]

        if len(unit_subjects) > 1:
            # Which subject the object belongs to cannot be determined.
            # Guessing would put a rating on the wrong equipment -
            # invisible in a graph, expensive in a substation.
            if rule.scope is StructuralScope.LINE:
                diagnostics.append(
                    _diagnostic(unit, unit_subjects, unit_objects)
                )

            continue

        if (
            rule.cardinality is CardinalityPolicy.ONE_SUBJECT_ONE_OBJECT
            and len(unit_objects) != 1
        ):
            continue

        subject, subject_references = next(iter(unit_subjects.values()))

        for obj, object_references in unit_objects.values():
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

    facts = [
        _fact(entity_set, rule, subject, obj, tuple(support[pair]))
        for pair, (subject, obj) in pairs.items()
    ]

    return facts, diagnostics


def _by_unit(
    entity_set: EngineeringEntitySet,
    entity_type: EntityType,
    scope: StructuralScope,
) -> dict[
    _Unit,
    dict[str, tuple[EngineeringEntity, list[EvidenceReference]]],
]:
    """
    Every entity of a type, indexed by each structural unit its
    observations occur in, and then by entity.

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
        _Unit,
        dict[str, tuple[EngineeringEntity, list[EvidenceReference]]],
    ] = {}

    for entity in entity_set.of_type(entity_type):
        for reference in entity.evidence:
            unit = _unit_key(reference, scope)
            in_unit = index.setdefault(unit, {})
            _, references = in_unit.setdefault(
                entity.entity_key, (entity, [])
            )
            references.append(reference)

    return index


def _unit_key(reference: EvidenceReference, scope: StructuralScope) -> _Unit:
    """
    Which structural unit one observation occupies.

    Both keys are read straight off the reference, which recorded them at
    extraction time. Nothing is recomputed and nothing is approximated -
    a unit key derived by this module would be a second opinion about
    where an observation was, and the first one is the only one entitled
    to an opinion.
    """

    line = (
        reference.page_number,
        reference.paragraph_index,
        reference.line_index,
    )

    if scope is StructuralScope.LINE:
        return line

    return line + (reference.token_start, reference.token_end)


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
    line: _Unit,
    subjects: dict,
    objects: dict,
) -> FactConstructionDiagnostic:
    page, paragraph, line_index = line[:3]

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
