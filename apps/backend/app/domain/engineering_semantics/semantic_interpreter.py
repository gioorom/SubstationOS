"""
The semantic interpreter (Milestone 30.1) - the pure function that turns
facts into interpreted meaning.

```
EngineeringFactSet
   -> for each rule in the catalogue:
       -> keep the facts whose predicate the rule reads
       -> keep those whose object carries the required evidence type
       -> group by subject; apply the rule's cardinality policy
   -> EngineeringSemanticSet
```

## What it sees, and what it cannot

Its input is a fact set. This module imports no canonical text, no
evidence, no entities and no storage. The only thing it knows about a
quantity is the **evidence type recorded on the fact's support** -
enough to tell a power from a voltage, and deliberately not enough to
read the value.

That limit is the reason two power quantities on one subject produce
nothing: this layer cannot see whether the figures agree, and reaching
for them would mean depending on entities. A boundary that forces the
conservative answer is a boundary in the right place.

## Nothing is partially interpreted

A subject either receives a statement or does not. There is no
half-assigned meaning, and an ambiguous subject produces a diagnostic
rather than a statement with a softer status.
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
from app.domain.engineering_semantics.semantic_identity import (
    semantic_set_identity,
)
from app.domain.engineering_facts.fact_models import (
    EngineeringFact,
    EngineeringFactSet,
    FactStatus,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
    EngineeringSemanticStatement,
    SemanticAmbiguityReason,
    SemanticInterpretationDiagnostic,
    SemanticStatementStatus,
)
from app.domain.engineering_semantics.semantic_policy import (
    SEMANTIC_CONTRACT_VERSION,
    SEMANTIC_POLICY_VERSION,
)
from app.domain.engineering_semantics.semantic_rules import (
    SEMANTIC_RULES,
    SemanticRule,
    rule_applies_to,
    satisfies_evidence_requirement,
)

# A fact's status decides the statement's, exactly as an entity's decided
# the fact's. Interpretation adds meaning, never certainty.
_STATUS_FOR_FACT: dict[FactStatus, SemanticStatementStatus] = {
    FactStatus.CONSTRUCTED: SemanticStatementStatus.INTERPRETED,
    FactStatus.AMBIGUOUS: SemanticStatementStatus.AMBIGUOUS,
}


def interpret_facts(
    fact_set: EngineeringFactSet,
    *,
    semantic_policy_version: str = SEMANTIC_POLICY_VERSION,
) -> EngineeringSemanticSet:
    """
    Interpret one fact set.

    Pure and deterministic: the same facts under the same rules produce
    an equal semantic set, every time.
    """

    statements: list[EngineeringSemanticStatement] = []
    diagnostics: list[SemanticInterpretationDiagnostic] = []

    # Each rule is applied to the whole fact set independently, in the
    # catalogue's declared order. No rule reads another rule's
    # statements: composing two meanings into a third is inference, and
    # this layer assigns meaning to facts rather than reasoning over
    # meanings.
    for rule in SEMANTIC_RULES:
        rule_statements, rule_diagnostics = _apply(fact_set, rule)
        statements.extend(rule_statements)
        diagnostics.extend(rule_diagnostics)

    # The identity chain, carried forward where the derivation happens.
    # The upstream artifact already knows its own identity; this one is
    # composed from it and this stage's own contract, so anything built
    # through the domain knows what it came from.
    upstream = (
        None
        if fact_set.artifact_identity is None
        else ArtifactIdentity(
            value=fact_set.artifact_identity,
            kind=ArtifactKind.FACT_SET,
            contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
        )
    )
    identity = (
        None
        if upstream is None
        else semantic_set_identity(
            fact_set=upstream,
            semantic_policy_version=semantic_policy_version,
            semantic_contract_version=SEMANTIC_CONTRACT_VERSION,
        )
    )

    return EngineeringSemanticSet(
        artifact_identity=None if identity is None else identity.value,
        upstream_identity=fact_set.artifact_identity,
        document_id=fact_set.document_id,
        project_id=fact_set.project_id,
        content_checksum=fact_set.content_checksum,
        extraction_policy_version=fact_set.extraction_policy_version,
        resolution_policy_version=fact_set.resolution_policy_version,
        fact_policy_version=fact_set.fact_policy_version,
        semantic_policy_version=semantic_policy_version,
        statements=tuple(statements),
        diagnostics=tuple(diagnostics),
    )


def _apply(
    fact_set: EngineeringFactSet, rule: SemanticRule
) -> tuple[
    list[EngineeringSemanticStatement],
    list[SemanticInterpretationDiagnostic],
]:
    """
    One rule, over one fact set.

    Grouped by subject, because every cardinality policy in this
    catalogue is a statement about how many objects one subject may
    carry.
    """

    candidates: dict[str, list[EngineeringFact]] = {}

    for fact in fact_set.facts:
        if not rule_applies_to(rule, fact.predicate):
            # A predicate this catalogue does not name is not this
            # rule's business - ignored, not refused.
            continue

        if not satisfies_evidence_requirement(
            rule, _object_evidence_types(fact)
        ):
            # A voltage, a current or a cable section. The association is
            # real and this rule assigns it no meaning.
            continue

        candidates.setdefault(fact.subject_entity_key, []).append(fact)

    statements: list[EngineeringSemanticStatement] = []
    diagnostics: list[SemanticInterpretationDiagnostic] = []

    for subject_key, facts in candidates.items():
        if len(facts) > rule.max_supporting_objects:
            diagnostics.append(
                SemanticInterpretationDiagnostic(
                    reason=(
                        SemanticAmbiguityReason.MULTIPLE_CANDIDATE_QUANTITIES
                    ),
                    subject_entity_key=subject_key,
                    candidate_fact_keys=tuple(
                        fact.fact_key for fact in facts
                    ),
                )
            )
            continue

        statements.append(_statement(fact_set, rule, facts[0]))

    return statements, diagnostics


def _object_evidence_types(fact: EngineeringFact) -> tuple[str, ...]:
    """
    What kind of observation supports the object side of this fact.

    Read from the fact's own support - the evidence type Milestone 29.2
    recorded there - as a plain string, so this layer never imports the
    evidence vocabulary it is not permitted to depend on.
    """

    return tuple(
        reference.evidence_type.value
        for reference in fact.object_support
    )


def _statement(
    fact_set: EngineeringFactSet,
    rule: SemanticRule,
    fact: EngineeringFact,
) -> EngineeringSemanticStatement:
    return EngineeringSemanticStatement(
        statement_key=_statement_key(fact_set, rule, fact),
        statement_type=rule.statement_type,
        document_id=fact_set.document_id,
        project_id=fact_set.project_id,
        subject_entity_key=fact.subject_entity_key,
        object_entity_key=fact.object_entity_key,
        status=_STATUS_FOR_FACT[fact.status],
        semantic_contract_version=SEMANTIC_CONTRACT_VERSION,
        semantic_rule_id=rule.rule_id,
        semantic_rule_version=rule.rule_version,
        supporting_fact_keys=(fact.fact_key,),
    )


def _statement_key(
    fact_set: EngineeringFactSet,
    rule: SemanticRule,
    fact: EngineeringFact,
) -> str:
    """
    A deterministic identity for one interpreted meaning.

    SHA-256 over the document, the exact fact source, the triple, and the
    rule and contract versions. The same facts under the same rule always
    yield the same key - which lets the schema enforce idempotency - and
    a rule version bump yields different ones, which makes a
    reinterpretation a new set rather than a silent rewrite.
    """

    material = "|".join(
        (
            str(fact_set.document_id),
            fact_set.content_checksum,
            fact_set.resolution_policy_version,
            fact_set.fact_policy_version,
            fact.subject_entity_key,
            rule.statement_type.value,
            fact.object_entity_key,
            rule.rule_id,
            rule.rule_version,
            SEMANTIC_CONTRACT_VERSION,
        )
    )

    return hashlib.sha256(material.encode("utf-8")).hexdigest()
