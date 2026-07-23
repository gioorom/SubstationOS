from __future__ import annotations

from app.domain.ontology.equipment_definition_catalog import (
    EquipmentDefinitionCatalog,
)
from app.domain.ontology.equipment_definition_repository import (
    EquipmentDefinitionRepository,
)
from app.domain.ontology.equipment_definition_validator import (
    EquipmentDefinitionValidator,
)


class EquipmentDefinitionEngine:
    def __init__(
        self,
        repository: EquipmentDefinitionRepository,
    ) -> None:
        self._repository = repository

    def load(
        self,
    ) -> EquipmentDefinitionCatalog:
        definitions = (
            self._repository.load_equipment_definitions()
        )

        EquipmentDefinitionValidator.validate(
            definitions
        )

        return EquipmentDefinitionCatalog(
            definitions=tuple(
                definitions
            )
        )