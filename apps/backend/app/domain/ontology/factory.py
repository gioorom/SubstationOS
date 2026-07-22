from __future__ import annotations

from typing import Any

from .models import (
    EquipmentCategory,
    EquipmentType,
)


class EquipmentTypeFactory:
    """
    Factory responsabile della creazione di EquipmentType
    a partire da dati grezzi (dict).
    """

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EquipmentType:
        """
        Costruisce un EquipmentType da un dizionario.

        In questa prima versione vengono popolati solamente
        i campi essenziali.
        """

        return EquipmentType(
            id=data["id"],
            name=data["name"],
            category=EquipmentCategory(data["category"]),
            description=data.get("description"),
            parent=data.get("parent"),
            aliases=tuple(data.get("aliases", ())),
            tags=tuple(data.get("tags", ())),
        )