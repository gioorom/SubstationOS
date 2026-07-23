from __future__ import annotations

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.equipment_definition_models import (
    EquipmentAttribute,
    EquipmentDefinition,
)


class EquipmentDefinitionFactory:
    """
    Factory per la creazione di EquipmentDefinition
    a partire da un dizionario.
    """

    @staticmethod
    def from_dict(
        data: dict,
        catalog: AttributeCatalog,
    ) -> EquipmentDefinition:
        attributes: list[EquipmentAttribute] = []

        for item in data.get(
            "attributes",
            [],
        ):
            definition = catalog.require(
                item["id"]
            )

            attributes.append(
                EquipmentAttribute(
                    definition=definition,
                    required=item.get(
                        "required",
                        True,
                    ),
                    default_value=item.get(
                        "default_value",
                    ),
                )
            )

        return EquipmentDefinition(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            attributes=tuple(attributes),
            metadata=data.get(
                "metadata",
                {},
            ),
        )