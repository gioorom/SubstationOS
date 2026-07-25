"""
Encodes/decodes the entity-local portion of a ``GraphEntityId``
(``entity_type:canonical_id``, e.g. ``"CABLE:C-295"``) for use as a
single, URL-safe path segment. ``project_id`` is never encoded here -
it is always the surrounding route's own ``{project_id}`` segment, so
it is not duplicated in the entity id segment.
"""

from __future__ import annotations

from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    InvalidGraphEntityIdError,
)


def parse_graph_entity_id(project_id: int, raw: str) -> GraphEntityId:
    entity_type, separator, canonical_id = raw.partition(":")

    if not separator or not entity_type or not canonical_id:
        raise InvalidGraphEntityIdError(raw)

    return GraphEntityId(
        project_id=project_id,
        entity_type=entity_type,
        canonical_id=canonical_id,
    )


def encode_graph_entity_id(graph_entity_id: GraphEntityId) -> str:
    return f"{graph_entity_id.entity_type}:{graph_entity_id.canonical_id}"
