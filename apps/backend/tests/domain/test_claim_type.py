from __future__ import annotations

import pytest

from app.domain.proposed_claims.claim_type import (
    ClaimType,
    requires_predicate_and_object,
)


def test_claim_type_covers_the_three_statement_shapes() -> None:
    values = {claim_type.value for claim_type in ClaimType}

    assert values == {"relationship", "attribute", "existence"}


@pytest.mark.parametrize(
    "claim_type",
    [ClaimType.RELATIONSHIP, ClaimType.ATTRIBUTE],
)
def test_requires_predicate_and_object_is_true_for_relationship_and_attribute(
    claim_type: ClaimType,
) -> None:
    assert requires_predicate_and_object(claim_type) is True


def test_requires_predicate_and_object_is_false_for_existence() -> None:
    assert requires_predicate_and_object(ClaimType.EXISTENCE) is False
