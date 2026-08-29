"""
Structural validation of a derived ``RetrievalConfiguration``, run before
the bridge ever returns one. Never validates engineering correctness, and
never judges whether the derived criteria were the "right" ones.

Its most important rule is ``_mode_agreement_errors``: the declared mode
must agree with the criteria fields the configuration actually carries,
so a prepared request cannot report one shape of retrieval and describe
another.

**What that rule protects changed in EPIC 31.2, and the rule survived
it.** It used to guard against the engine re-deriving a different mode
from the same fields. The engine derives no mode any more - its governed
planner reads the designation fields directly and issues typed governed
queries - so the rule now protects the *caller*, who reads the declared
mode on the prepared request and must not be told something the
configuration contradicts. The refusals below are unchanged, and each
one still states why.

The bounds below are stated here rather than imported. Legacy Structured
Retrieval, which once owned them, was retired by EPIC 31.4; and even
before that, a configuration violating them had to be reported as a
typed bridge failure the caller can read rather than raised several
steps later inside the engine.
"""

from __future__ import annotations

from app.domain.retrieval_bridge.retrieval_bridge_models import (
    RetrievalBridgeValidationResult,
    RetrievalConfiguration,
)
from app.domain.retrieval_bridge.retrieval_mode import (
    RetrievalMode,
)
#: The bounds a derived configuration must respect.
#:
#: **Stated here** since EPIC 31.4, which retired the package they were
#: imported from. The module docstring above always described them as
#: "restated rather than imported", and they now are: a configuration
#: that violates one must be reported as a typed bridge failure the
#: caller can read, which means the bridge has to own the numbers.
MIN_RESULT_LIMIT = 1
MAX_RESULT_LIMIT = 200
MAX_LEXICAL_TERM_COUNT = 8
MAX_LEXICAL_TERM_LENGTH = 64

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
