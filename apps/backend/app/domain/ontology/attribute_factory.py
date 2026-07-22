from __future__ import annotations

from typing import Any

from .attribute_models import AttributeDefinition
from .models import AttributeDataType


class AttributeDefinitionFactory:
    """
    Costruisce AttributeDefinition a partire
    da rappresentazioni non tipizzate.
    """

    @staticmethod
    def from_dict(
        data: dict[str, Any],
    ) -> AttributeDefinition:
        """
        Converte un dizionario in AttributeDefinition.
        """

        return AttributeDefinition(
            id=data["id"],
            name=data["name"],
            data_type=AttributeDataType(data["data_type"]),
            description=data.get("description"),
            unit=data.get("unit"),
            allowed_values=tuple(
                data.get("allowed_values", ())
            ),
            default_value=data.get("default_value"),
            metadata=dict(data.get("metadata", {})),
        )