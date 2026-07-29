from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_semantics.semantic_failures import (
    SemanticInterpretationFailureCode,
)
from app.domain.engineering_semantics.semantic_models import (
    SemanticAmbiguityReason,
    SemanticStatementStatus,
)
from app.domain.engineering_semantics.semantic_statement_types import (
    SemanticStatementType,
)

# --- Response ------------------------------------------------------------


class SemanticStatementRead(BaseModel):
    """
    One interpreted engineering meaning.

    ``HAS_RATED_POWER`` is assigned because a declared, versioned rule
    maps an association with a power quantity onto it. The figure itself
    is **not** here: it lives on the quantity entity, and a copy would be
    a second source of truth for a rated value.
    """

    statement_key: str
    statement_type: SemanticStatementType
    subject_entity_key: str
    object_entity_key: str
    status: SemanticStatementStatus
    semantic_contract_version: str
    semantic_rule_id: str
    semantic_rule_version: str
    supporting_fact_keys: tuple[str, ...]

    model_config = ConfigDict(from_attributes=True)


class SemanticDiagnosticRead(BaseModel):
    """
    A subject that had candidates and received no statement.

    Deliberately not shaped like a statement: no object and no statement
    type, because which quantity carries the meaning is exactly what
    could not be decided.
    """

    reason: SemanticAmbiguityReason
    subject_entity_key: str
    candidate_fact_keys: tuple[str, ...]

    model_config = ConfigDict(from_attributes=True)


class SemanticSetSummaryRead(BaseModel):
    """What a semantic set *is*, without its statements - the whole
    upstream source identity plus the rules that interpreted it."""

    document_id: int
    project_id: int | None
    content_checksum: str
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    statement_count: int
    has_ambiguities: bool

    model_config = ConfigDict(from_attributes=True)


class SemanticSetRead(SemanticSetSummaryRead):
    """The full set: every statement with its supporting fact keys, and
    every diagnostic."""

    statements: tuple[SemanticStatementRead, ...]
    diagnostics: tuple[SemanticDiagnosticRead, ...]

    model_config = ConfigDict(from_attributes=True)


class SemanticFailureRead(BaseModel):
    code: SemanticInterpretationFailureCode
    message: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class SemanticInterpretationResultRead(BaseModel):
    """
    The outcomes a caller must be able to tell apart.

    | `succeeded` | `reused` | `found_semantics` | Means |
    |---|---|---|---|
    | true | false | true | interpretation completed |
    | true | false | false | completed, and nothing had a declared meaning |
    | true | true | either | an existing set was reused |
    | false | - | - | interpretation failed; `failure` says why |

    ``has_ambiguities`` reports subjects the rules declined - not a
    failure, and not a statement.
    """

    succeeded: bool
    reused: bool
    found_semantics: bool
    has_ambiguities: bool
    semantic_set: SemanticSetSummaryRead | None
    failure: SemanticFailureRead | None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, result) -> "SemanticInterpretationResultRead":
        return cls(
            succeeded=result.succeeded,
            reused=result.reused,
            found_semantics=result.found_semantics,
            has_ambiguities=result.has_ambiguities,
            semantic_set=(
                None
                if result.semantic_set is None
                else SemanticSetSummaryRead.model_validate(
                    result.semantic_set
                )
            ),
            failure=(
                None
                if result.failure is None
                else SemanticFailureRead.model_validate(result.failure)
            ),
        )
