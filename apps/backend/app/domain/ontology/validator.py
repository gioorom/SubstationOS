from __future__ import annotations

from app.domain.ontology.exceptions import (
    DuplicateEquipmentTypeError,
    InvalidEquipmentDefinitionError,
)
from app.domain.ontology.models import EquipmentType


class OntologyValidator:
    """
    Valida la consistenza di una collezione di EquipmentType.
    """

    def validate(
        self,
        equipment_types: list[EquipmentType],
    ) -> None:
        self._validate_duplicate_ids(equipment_types)
        self._validate_names(equipment_types)
        self._validate_parents(equipment_types)

    @staticmethod
    def _validate_duplicate_ids(
        equipment_types: list[EquipmentType],
    ) -> None:
        seen: set[str] = set()

        for equipment in equipment_types:
            if equipment.id in seen:
                raise DuplicateEquipmentTypeError(
                    f"Duplicate equipment type: '{equipment.id}'."
                )

            seen.add(equipment.id)

    @staticmethod
    def _validate_names(
        equipment_types: list[EquipmentType],
    ) -> None:
        for equipment in equipment_types:
            if not equipment.name.strip():
                raise InvalidEquipmentDefinitionError(
                    f"Equipment '{equipment.id}' has an empty name."
                )

    @staticmethod
    def _validate_parents(
        equipment_types: list[EquipmentType],
    ) -> None:
        ids = {
            equipment.id
            for equipment in equipment_types
        }

        for equipment in equipment_types:
            if (
                equipment.parent is not None
                and equipment.parent not in ids
            ):
                raise InvalidEquipmentDefinitionError(
                    f"Equipment '{equipment.id}' references "
                    f"unknown parent '{equipment.parent}'."
                )