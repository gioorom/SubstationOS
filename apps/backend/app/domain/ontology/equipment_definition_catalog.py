from __future__ import annotations

from dataclasses import dataclass

from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)
from app.domain.ontology.exceptions import (
    EquipmentDefinitionNotFoundError,
)


@dataclass(frozen=True, slots=True)
class EquipmentDefinitionCatalog:
    definitions: tuple[
        EquipmentDefinition,
        ...
    ]

    def get(
        self,
        equipment_id: str,
    ) -> EquipmentDefinition | None:
        normalized_id = (
            equipment_id.strip().lower()
        )

        return next(
            (
                definition
                for definition in self.definitions
                if definition.id.lower()
                == normalized_id
            ),
            None,
        )

    def require(
        self,
        equipment_id: str,
    ) -> EquipmentDefinition:
        definition = self.get(
            equipment_id
        )

        if definition is None:
            raise EquipmentDefinitionNotFoundError(
                equipment_id
            )

        return definition

    def all(
        self,
    ) -> tuple[
        EquipmentDefinition,
        ...
    ]:
        return self.definitions

    def __len__(
        self,
    ) -> int:
        return len(
            self.definitions
        )

    def __contains__(
        self,
        equipment_id: object,
    ) -> bool:
        if not isinstance(
            equipment_id,
            str,
        ):
            return False

        return (
            self.get(
                equipment_id
            )
            is not None
        )