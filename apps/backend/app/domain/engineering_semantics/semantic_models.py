"""
Engineering Semantic Statements (EPIC 2, Milestone 30.1) - interpreted
engineering meaning, supported by facts.

## The support chain

A semantic statement owns **no provenance**. It cites facts, and every
layer beneath cites the one below it:

```
Semantic Statement
   -> Engineering Fact          (by fact key)
        -> Engineering Entity   (by entity key)
             -> Engineering Evidence   (by evidence key)
                  -> Canonical Text    (page, paragraph, line, tokens)
                       -> Canonical PDF (span character ranges)
                            -> Original Document
```

That chain is why an engineer disputing "TR1 has rated power 630 kVA" can
be shown the characters on the page that produced it. Each link is a key
into an immutable record, never a copy - a statement that duplicated its
fact's payload would become a second source of truth that could go stale.

## What a statement is not

It is not a graph edge. The Knowledge Graph stores interpreted knowledge
and reasoning consumes it; both are later milestones. This layer produces
the interpretation and stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)


class SemanticStatementStatus(str, Enum):
    """
    A statement's status is **derived from its supporting fact**, never
    invented.

    Interpretation adds meaning; it never adds certainty. A rated power
    read from a figure the extractor could not parse exactly is still a
    rated power statement - and still says the value is unsettled.
    """

    INTERPRETED = "interpreted"
    # The rule applied and a supporting fact is itself ambiguous -
    # typically a quantity whose number could not be read exactly. The
    # meaning holds; the figure does not.
    AMBIGUOUS = "ambiguous"


class SemanticAmbiguityReason(str, Enum):
    """
    Why a subject that had candidates received no statement.

    Recorded as a **diagnostic**, never as a statement, and stored in its
    own table so that a consumer reading statements cannot see it at all.
    """

    # One designation is associated with two or more power quantities.
    # Which is the rating cannot be decided: a fact carries entity keys,
    # not values, so this layer cannot even see whether the two figures
    # agree - and reading them would mean reaching into entities, which
    # is not its business. Interpreting either would be a coin flip on an
    # equipment rating.
    MULTIPLE_CANDIDATE_QUANTITIES = "multiple_candidate_quantities"


@dataclass(frozen=True, slots=True)
class EngineeringSemanticStatement:
    """
    One interpreted engineering meaning.

    Entities and facts are referenced **by key only**. No fact payload is
    copied in: the association, its support and its provenance live on
    the fact, which stays the single account of why the two entities are
    related at all.

    ``statement_key`` is deterministic - a SHA-256 over the document, the
    exact fact source, the triple, and the rule and contract versions. The
    same facts under the same rule always produce the same key, and a
    rule version bump always produces different ones.
    """

    statement_key: str
    statement_type: SemanticStatementType
    document_id: int
    project_id: int | None
    subject_entity_key: str
    object_entity_key: str
    status: SemanticStatementStatus
    semantic_contract_version: str
    semantic_rule_id: str
    semantic_rule_version: str
    supporting_fact_keys: tuple[str, ...] = ()

    @property
    def support_count(self) -> int:
        return len(self.supporting_fact_keys)


@dataclass(frozen=True, slots=True)
class SemanticInterpretationDiagnostic:
    """
    A subject that had candidates and received no statement.

    Deliberately not shaped like a statement: it names no object and no
    statement type, because which quantity carries the meaning is exactly
    what could not be decided.
    """

    reason: SemanticAmbiguityReason
    subject_entity_key: str
    candidate_fact_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngineeringSemanticSet:
    """
    Every statement interpreted from one fact set.

    The version fields identify the exact source and rules: which
    document, which bytes, which extraction policy read them, which
    resolution and construction policies produced the facts, and which
    semantic policy interpreted them.

    ``extraction_policy_version`` is ``None`` only for a set stored
    before that provenance was recorded, or interpreted from a fact set
    that is itself unknown. Unknown is not a value: such a set can never
    prove a later reuse is valid, and is recomputed rather than
    trusted. A set
    whose provenance is unknown could not be trusted by the milestone
    that turns interpreted knowledge into a graph.

    Deliberately **no timestamp** - two interpretations of the same facts
    under the same rules must compare equal.
    """

    document_id: int
    project_id: int | None
    content_checksum: str
    extraction_policy_version: str | None
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    statements: tuple[EngineeringSemanticStatement, ...] = ()
    diagnostics: tuple[SemanticInterpretationDiagnostic, ...] = ()

    #: This artifact's deterministic identity, and the identity of the
    #: artifact it was derived from. ``None`` only for a row stored
    #: before the identity chain existed: unknown is not a value, and an
    #: artifact that cannot say what it was derived from can never prove
    #: a reuse is valid. See ``app/domain/artifact_identity``.
    artifact_identity: str | None = None
    upstream_identity: str | None = None

    @property
    def statement_count(self) -> int:
        return len(self.statements)

    @property
    def is_empty(self) -> bool:
        return not self.statements

    @property
    def has_ambiguities(self) -> bool:
        return bool(self.diagnostics)

    def statement(
        self, statement_key: str
    ) -> EngineeringSemanticStatement | None:
        for statement in self.statements:
            if statement.statement_key == statement_key:
                return statement

        return None

    def of_type(
        self, statement_type: SemanticStatementType
    ) -> tuple[EngineeringSemanticStatement, ...]:
        return tuple(
            statement
            for statement in self.statements
            if statement.statement_type is statement_type
        )
