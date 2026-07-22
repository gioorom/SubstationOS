from __future__ import annotations

from abc import ABC, abstractmethod

from .attribute_models import AttributeDefinition


class AttributeDefinitionRepository(ABC):
    """
    Contratto per il caricamento delle definizioni globali
    degli attributi dell'ontologia.
    """

    @abstractmethod
    def load_attribute_definitions(
        self,
    ) -> list[AttributeDefinition]:
        """
        Carica tutte le definizioni degli attributi disponibili.
        """

        raise NotImplementedError