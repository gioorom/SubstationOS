from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)


class EquipmentDefinitionRepository(ABC):
    """
    Repository delle definizioni
    di apparecchiature.
    """

    @abstractmethod
    def load_equipment_definitions(
        self,
    ) -> list[EquipmentDefinition]:
        """
        Carica tutte le definizioni.
        """