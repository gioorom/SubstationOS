from __future__ import annotations

from abc import ABC, abstractmethod

from .models import EquipmentType


class OntologyRepository(ABC):
    """
    Contratto per qualsiasi sorgente dati dell'ontologia.

    Il dominio non conosce se i dati provengono da:
    - filesystem
    - database
    - API REST
    - Neo4j
    - Git
    - cloud storage

    Conosce solamente questa interfaccia.
    """

    @abstractmethod
    def load_equipment_types(self) -> list[EquipmentType]:
        """
        Carica tutti gli EquipmentType disponibili.

        Returns
        -------
        list[EquipmentType]
            Elenco completo dei tipi di apparecchiatura.
        """
        raise NotImplementedError