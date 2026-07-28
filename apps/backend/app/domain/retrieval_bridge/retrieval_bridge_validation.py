"""
Structural validation of a derived ``RetrievalConfiguration``, run before
the bridge ever returns one. Never validates engineering correctness, and
never judges whether the derived criteria were the "right" ones.

Its most important rule is ``_mode_agreement_errors``: the engine's own
retrieval step handler re-derives a ``RetrievalMode`` from which criteria
fields are set, so a configuration whose declared mode disagrees with
what the engine will derive would be quietly misleading - the bridge
would report one thing and the engine do another. That disagreement is
made structurally impossible here rather than left to convention.

The bounds below deliberately mirror Structured Retrieval's own
(``structured_retrieval_validator.py``). They are restated rather than
imported because a configuration that violates them must be reported as
a typed bridge failure the caller can read, not raised as a
``StructuredRetrievalError`` several steps later inside the engine.
"""

from __future__ import annotations

from app.domain.retrieval_bridge.retrieval_bridge_models import (
    RetrievalBridgeValidationResult,
    RetrievalConfiguration,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)
from app.domain.structured_retrieval.structured_retrieval_validator import (
    MAX_LEXICAL_TERM_COUNT,
    MAX_LEXICAL_TERM_LENGTH,
    MAX_RESULT_LIMIT,
    MIN_RESULT_LIMIT,
)

_SUPPORTED_NEIGHBORHOOD_DEPTH = 1


def _mode_agreement_errors(
    configuration: RetrievalConfiguration,
) -> list[str]:
    """The mode the engine's ``BuildRetrievalRequestStepHandler`` will
    derive from these fields must be the mode declared here."""

    errors: list[str] = []

    # This bridge never derives a bare entity type, and must not: with a
    # canonical reference present, Structured Retrieval's ENTITY_LOOKUP
    # mode admits the canonical-id criterion *only*, so an entity type
    # would make the request invalid; without one, the engine would derive
    # ENTITY_TYPE_SEARCH from it and silently widen a lexical search to
    # every entity of that type. Neither is acceptable, so the rule is
    # unconditional. The resolved type is still reported, on the
    # RequestDesignation.
    if configuration.entity_type:
        errors.append(
            "entity_type must never be derived: it either invalidates an "
            "entity lookup or silently widens a lexical search."
        )

    if configuration.attribute_name:
        errors.append(
            "attribute_name is set, but nothing in classifier evidence "
            "identifies an attribute - it must never be derived."
        )

    if configuration.canonical_entity_id:
        if configuration.mode is not RetrievalMode.ENTITY_LOOKUP:
            errors.append(
                "A configuration carrying a canonical entity reference "
                "must declare ENTITY_LOOKUP - the engine derives that "
                "mode from the reference regardless of what is declared."
            )
        if configuration.lexical_terms:
            errors.append(
                "A canonical entity lookup must carry no lexical terms - "
                "the engine would ignore them, so reporting them would "
                "misrepresent what is searched."
            )
        return errors

    if configuration.mode is not RetrievalMode.LEXICAL_SEARCH:
        errors.append(
            "A configuration carrying no canonical entity reference must "
            "declare LEXICAL_SEARCH."
        )

    if not configuration.lexical_terms:
        errors.append(
            "A lexical configuration must carry at least one term - an "
            "empty search would retrieve everything."
        )

    return errors


def validate_configuration(
    configuration: RetrievalConfiguration,
) -> RetrievalBridgeValidationResult:
    errors: list[str] = _mode_agreement_errors(configuration)

    if not (MIN_RESULT_LIMIT <= configuration.limit <= MAX_RESULT_LIMIT):
        errors.append(
            f"limit {configuration.limit} is outside the supported range "
            f"{MIN_RESULT_LIMIT}-{MAX_RESULT_LIMIT}."
        )

    if len(configuration.lexical_terms) > MAX_LEXICAL_TERM_COUNT:
        errors.append(
            f"{len(configuration.lexical_terms)} lexical terms were "
            f"derived; at most {MAX_LEXICAL_TERM_COUNT} are supported."
        )

    for term in configuration.lexical_terms:
        if not term or not term.strip():
            errors.append("A blank lexical term was derived.")
            break
        if len(term) > MAX_LEXICAL_TERM_LENGTH:
            errors.append(
                f"Lexical term '{term}' exceeds the maximum length of "
                f"{MAX_LEXICAL_TERM_LENGTH} characters."
            )
            break

    if configuration.include_neighborhood:
        if configuration.neighborhood_depth != _SUPPORTED_NEIGHBORHOOD_DEPTH:
            errors.append(
                "Neighborhood expansion is supported only at depth "
                f"{_SUPPORTED_NEIGHBORHOOD_DEPTH}."
            )
    elif configuration.neighborhood_depth != 0:
        errors.append(
            "neighborhood_depth must be 0 when neighborhood expansion is "
            "not requested."
        )

    return RetrievalBridgeValidationResult(
        valid=not errors, errors=tuple(errors)
    )
