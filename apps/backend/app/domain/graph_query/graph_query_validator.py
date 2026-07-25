from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.graph_query.graph_query_exceptions import (
    CrossProjectGraphQueryError,
    InvalidAttributeNameError,
    InvalidEntityTypeError,
    UnsupportedTraversalDepthError,
)

_SUPPORTED_DEPTH = 1


class GraphQueryValidator:
    """
    Stateless validation rules for Graph Query, shared by the service
    (which needs to validate before performing repository reads).
    """

    @staticmethod
    def validate_entity_type(entity_type: str) -> None:
        if not entity_type or not entity_type.strip():
            raise InvalidEntityTypeError(entity_type)

    @staticmethod
    def validate_attribute_name(attribute: str) -> None:
        if not attribute or not attribute.strip():
            raise InvalidAttributeNameError(attribute)

    @staticmethod
    def validate_depth(depth: int) -> None:
        if depth != _SUPPORTED_DEPTH:
            raise UnsupportedTraversalDepthError(depth)

    @staticmethod
    def validate_same_project(
        expected_project_id: int,
        graph_entity_id: GraphEntityId,
    ) -> None:
        if graph_entity_id.project_id != expected_project_id:
            raise CrossProjectGraphQueryError(
                expected_project_id,
                graph_entity_id.project_id,
            )
