"""
Application service for Engineering Semantic Interpretation (EPIC 2,
Milestone 30.1).

    Engineering Facts        (29.2, through its own repository port)
        -> Check the policy   this interpreter understands those facts
        -> Interpret          the semantic rule catalogue, a pure function
        -> Validate           every statement traces to facts in the source
        -> Persist or reuse   never overwriting an earlier set

**Its only input is a fact set.** It holds no canonical text repository,
no evidence repository, no entity repository and no parser. It never
reconstructs facts, resolves entities or invokes extraction - those
happened upstream, under their own rules and their own versions, and
redoing any of them here would create a second account of what a document
contains.

It writes no Knowledge Graph node or edge: Semantic Interpretation
assigns meaning, the Knowledge Graph stores interpreted knowledge, and
reasoning consumes it. Three responsibilities, three milestones.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_facts.engineering_fact_repository import (
    EngineeringFactRepository,
)
from app.domain.engineering_semantics.engineering_semantic_repository import (
    EngineeringSemanticRepository,
)
from app.domain.engineering_semantics.semantic_failures import (
    SemanticInterpretationFailure,
    SemanticInterpretationFailureCode,
)
from app.domain.engineering_semantics.semantic_interpreter import (
    interpret_facts,
)
from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
)
from app.domain.engineering_semantics.semantic_policy import (
    SEMANTIC_POLICY_VERSION,
    SUPPORTED_FACT_POLICY_VERSIONS,
    is_supported_fact_policy_version,
)
from app.domain.engineering_semantics.semantic_validation import (
    validate_semantic_set,
)


@dataclass(frozen=True, slots=True)
class SemanticInterpretationResult:
    """What one interpretation concluded."""

    succeeded: bool
    semantic_set: EngineeringSemanticSet | None = None
    reused: bool = False
    failure: SemanticInterpretationFailure | None = None

    @property
    def found_semantics(self) -> bool:
        """Whether anything was interpreted. ``False`` is a successful
        outcome: a document may hold associations none of which the
        catalogue assigns a meaning to."""

        return (
            self.semantic_set is not None
            and not self.semantic_set.is_empty
        )

    @property
    def has_ambiguities(self) -> bool:
        """Whether any subject had candidates the rules declined to
        interpret. Not a failure - the rules working."""

        return (
            self.semantic_set is not None
            and self.semantic_set.has_ambiguities
        )


def interpret_document_facts(
    fact_repository: EngineeringFactRepository,
    semantic_repository: EngineeringSemanticRepository,
    *,
    document_id: int,
    semantic_policy_version: str = SEMANTIC_POLICY_VERSION,
) -> SemanticInterpretationResult:
    """
    Interpret - or re-use - the engineering semantics of one document.

    Checks run in order and the first failure is returned.
    """

    fact_set = fact_repository.find_latest_for_document(document_id)

    if fact_set is None:
        return _failed(
            SemanticInterpretationFailureCode.FACT_SET_MISSING,
            f"Document '{document_id}' has no engineering facts; there "
            "is nothing to interpret.",
            detail="Semantic interpretation is the step after fact "
            "construction. Facts are its only input - it never reads "
            "canonical text, evidence or the original document.",
        )

    if fact_set.document_id != document_id:
        return _failed(
            SemanticInterpretationFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The facts returned for document '{document_id}' describe "
            f"document '{fact_set.document_id}'.",
            detail="Continuing would attach interpreted knowledge to the "
            "wrong document.",
        )

    if not is_supported_fact_policy_version(fact_set.fact_policy_version):
        return _failed(
            SemanticInterpretationFailureCode.UNSUPPORTED_FACT_VERSION,
            f"The facts for document '{document_id}' were constructed "
            f"under policy '{fact_set.fact_policy_version}', which this "
            "interpreter does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_FACT_POLICY_VERSIONS))
                + ". A newer policy may carry predicates this code would "
                "silently ignore, and a semantic set missing half its "
                "meaning is worse than a visible refusal."
            ),
        )

    existing = semantic_repository.find_for_source(
        document_id,
        fact_set.content_checksum,
        fact_set.resolution_policy_version,
        fact_set.fact_policy_version,
        semantic_policy_version,
    )

    if existing is not None:
        return SemanticInterpretationResult(
            succeeded=True, semantic_set=existing, reused=True
        )

    try:
        semantic_set = interpret_facts(
            fact_set, semantic_policy_version=semantic_policy_version
        )
    except Exception as error:  # noqa: BLE001 - see below
        # The interpreter is pure and total by design, so reaching here
        # means a rule defect rather than a data condition. Caught
        # anyway: a caller needs one honest answer instead of an
        # exception crossing the boundary, and the cause is carried in
        # ``detail`` rather than swallowed.
        return _failed(
            SemanticInterpretationFailureCode.SEMANTIC_VALIDATION_FAILURE,
            f"A semantic rule failed while interpreting document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    violation = validate_semantic_set(semantic_set, fact_set)

    if violation is not None:
        return _failed(
            violation.code, violation.message, detail=violation.detail
        )

    try:
        semantic_repository.save(semantic_set)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            SemanticInterpretationFailureCode.SEMANTIC_PERSISTENCE_FAILURE,
            f"The semantic set for document '{document_id}' was "
            "interpreted and could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return SemanticInterpretationResult(
        succeeded=True, semantic_set=semantic_set, reused=False
    )


def get_semantic_set(
    semantic_repository: EngineeringSemanticRepository, document_id: int
) -> EngineeringSemanticSet | None:
    """
    The current semantic set of one document - the **only** thing a
    future Knowledge Graph population milestone should consume.

    ``None`` means no interpretation has run. Not an error: most
    documents have not been interpreted.
    """

    return semantic_repository.find_latest_for_document(document_id)


def _failed(
    code: SemanticInterpretationFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> SemanticInterpretationResult:
    return SemanticInterpretationResult(
        succeeded=False,
        failure=SemanticInterpretationFailure(
            code=code, message=message, detail=detail
        ),
    )
