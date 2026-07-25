from __future__ import annotations

import pytest

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_exceptions import (
    CrossProjectGraphQueryError,
    InvalidAttributeNameError,
    InvalidEntityTypeError,
    UnsupportedTraversalDepthError,
)
from app.domain.graph_query.graph_query_validator import (
    GraphQueryValidator,
)


def test_validate_entity_type_accepts_a_real_type() -> None:
    GraphQueryValidator.validate_entity_type("CABLE")


@pytest.mark.parametrize("entity_type", ["", "   "])
def test_validate_entity_type_rejects_blank_values(
    entity_type: str,
) -> None:
    with pytest.raises(InvalidEntityTypeError):
        GraphQueryValidator.validate_entity_type(entity_type)


def test_validate_attribute_name_accepts_a_real_name() -> None:
    GraphQueryValidator.validate_attribute_name("rated_voltage")


@pytest.mark.parametrize("attribute", ["", "   "])
def test_validate_attribute_name_rejects_blank_values(
    attribute: str,
) -> None:
    with pytest.raises(InvalidAttributeNameError):
        GraphQueryValidator.validate_attribute_name(attribute)


def test_validate_depth_accepts_one() -> None:
    GraphQueryValidator.validate_depth(1)


@pytest.mark.parametrize("depth", [0, 2, -1])
def test_validate_depth_rejects_anything_else(depth: int) -> None:
    with pytest.raises(UnsupportedTraversalDepthError):
        GraphQueryValidator.validate_depth(depth)


def test_validate_same_project_accepts_a_matching_entity() -> None:
    GraphQueryValidator.validate_same_project(
        10,
        GraphEntityId(project_id=10, entity_type="CABLE", canonical_id="C-295"),
    )


def test_validate_same_project_rejects_a_mismatch() -> None:
    with pytest.raises(CrossProjectGraphQueryError):
        GraphQueryValidator.validate_same_project(
            10,
            GraphEntityId(
                project_id=20, entity_type="CABLE", canonical_id="C-295"
            ),
        )
