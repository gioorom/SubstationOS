from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.graph_builder.graph_builder_models import (
    GraphNodeOperation,
    GraphOperationBatchScope,
    GraphRelationshipOperation,
)


class GraphEntityIdRead(BaseModel):
    project_id: int
    entity_type: str
    canonical_id: str
    value: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphRelationshipTypeRead(BaseModel):
    value: str

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphOperationRead(BaseModel):
    """
    One graph operation, flattened for the API response. Sparse by
    ``operation_category``, mirroring how ``GraphOperationRecord``
    itself stores a ``GraphNodeOperation``/``GraphRelationshipOperation``
    - a node operation populates ``entity_id``/``attribute``/``value``;
    a relationship operation populates ``subject_id``/
    ``relationship_type``/``object_id``.
    """

    operation_category: str
    kind: str
    source_fact_id: int

    entity_id: GraphEntityIdRead | None = None
    attribute: str | None = None
    value: str | None = None

    subject_id: GraphEntityIdRead | None = None
    relationship_type: GraphRelationshipTypeRead | None = None
    object_id: GraphEntityIdRead | None = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _flatten_domain_operation(cls, data: object) -> object:
        if isinstance(data, GraphNodeOperation):
            return {
                "operation_category": "node",
                "kind": data.kind.value,
                "source_fact_id": data.source_fact_id,
                "entity_id": data.entity_id,
                "attribute": data.attribute,
                "value": data.value,
            }

        if isinstance(data, GraphRelationshipOperation):
            return {
                "operation_category": "relationship",
                "kind": data.kind.value,
                "source_fact_id": data.source_fact_id,
                "subject_id": data.subject_id,
                "relationship_type": data.relationship_type,
                "object_id": data.object_id,
            }

        return data


class GraphOperationBatchSourceRead(BaseModel):
    scope: GraphOperationBatchScope
    scope_id: int

    model_config = ConfigDict(
        from_attributes=True,
    )


class GraphOperationBatchRead(BaseModel):
    id: int | None
    project_id: int | None
    source: GraphOperationBatchSourceRead
    operations: list[GraphOperationRead]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
