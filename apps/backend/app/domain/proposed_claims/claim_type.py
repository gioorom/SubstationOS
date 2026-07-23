from __future__ import annotations

from enum import Enum


class ClaimType(str, Enum):
    """
    The shape of engineering statement a ``ProposedClaim`` asserts.
    Determines which of ``subject``/``predicate``/``object`` are
    required (``ProposedClaimValidator.validate_shape``) - a Proposed
    Claim is not a free-form triple, it is one of a fixed set of
    statement shapes the Review Workflow and, later, the Knowledge
    Graph know how to interpret.

    ``RELATIONSHIP`` - subject, predicate, and object are all entity
    references, e.g. "Cable C-295" "FEEDS" "Transformer TR-02".
    ``ATTRIBUTE`` - subject is an entity, predicate names an attribute,
    object is the asserted value, e.g. "Transformer TR-02"
    "rated_voltage" "132kV".
    ``EXISTENCE`` - only the subject is asserted, e.g. "Transformer
    TR-02" appears in this project's documents at all. Predicate and
    object are not applicable.
    """

    RELATIONSHIP = "relationship"
    ATTRIBUTE = "attribute"
    EXISTENCE = "existence"


# Claim types whose predicate and object are required, not optional.
_TYPES_REQUIRING_PREDICATE_AND_OBJECT: frozenset[ClaimType] = frozenset(
    {
        ClaimType.RELATIONSHIP,
        ClaimType.ATTRIBUTE,
    }
)


def requires_predicate_and_object(claim_type: ClaimType) -> bool:
    return claim_type in _TYPES_REQUIRING_PREDICATE_AND_OBJECT
