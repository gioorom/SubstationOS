from __future__ import annotations

from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)
from app.domain.ontology.exceptions import (
    DuplicateEquipmentDefinitionError,
)


class EquipmentDefinitionValidator:
    """
    Valida un insieme di definizioni di apparecchiature.
    """

    @staticmethod
    def validate(
        equipment_definitions: list[EquipmentDefinition],
    ) -> None:
        EquipmentDefinitionValidator._validate_unique_ids(
            equipment_definitions
        )

    @staticmethod
    def _validate_unique_ids(
        equipment_definitions: list[EquipmentDefinition],
    ) -> None:
        ids = [
            definition.id.strip().lower()
            for definition in equipment_definitions
        ]

        duplicates = {
            equipment_id
            for equipment_id in ids
            if ids.count(equipment_id) > 1
        }

        if duplicates:
            duplicate_list = ", ".join(
                sorted(duplicates)
            )

            raise DuplicateEquipmentDefinitionError(
                duplicate_list
            )
