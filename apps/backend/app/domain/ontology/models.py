from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .exceptions import EquipmentTypeNotFoundError


class AttributeDataType(str, Enum):
    """
    Tipi di dato supportati dagli attributi dell'ontologia.
    """

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"


class EquipmentCategory(str, Enum):
    """
    Categorie principali degli oggetti presenti nel dominio elettrico.
    """

    PRIMARY_EQUIPMENT = "primary_equipment"
    SECONDARY_EQUIPMENT = "secondary_equipment"
    CONDUCTOR = "conductor"
    PROTECTION = "protection"
    MEASUREMENT = "measurement"
    CONTROL = "control"
    COMMUNICATION = "communication"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EquipmentAttribute:
    """
    Definisce un attributo associabile a un tipo di apparecchiatura.

    Esempi:
    - tensione nominale;
    - corrente nominale;
    - rapporto di trasformazione;
    - classe di precisione.
    """

    key: str
    name: str
    data_type: AttributeDataType
    description: str | None = None
    unit: str | None = None
    required: bool = False
    allowed_values: tuple[Any, ...] = ()
    default_value: Any | None = None


@dataclass(frozen=True, slots=True)
class EquipmentSymbol:
    """
    Rappresenta un simbolo grafico associato a un EquipmentType.

    Lo stesso componente può avere simboli diversi a seconda dello standard
    o della convenzione grafica utilizzata.
    """

    standard: str
    identifier: str
    description: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EquipmentRelation:
    """
    Definisce una relazione ammessa tra due tipi di apparecchiatura.

    Esempi:
    - connected_to;
    - protected_by;
    - measures;
    - controls.
    """

    relation_type: str
    target_types: tuple[str, ...]
    description: str | None = None
    required: bool = False
    multiple: bool = True


@dataclass(frozen=True, slots=True)
class EquipmentType:
    """
    Definisce un tipo astratto di apparecchiatura elettrica.

    Non rappresenta una singola apparecchiatura installata, ma il concetto
    generale, ad esempio breaker, transformer o current_transformer.
    """

    id: str
    name: str
    category: EquipmentCategory
    description: str | None = None
    parent: str | None = None
    aliases: tuple[str, ...] = ()
    attributes: tuple[EquipmentAttribute, ...] = ()
    symbols: tuple[EquipmentSymbol, ...] = ()
    relations: tuple[EquipmentRelation, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_alias(self, value: str) -> bool:
        """
        Verifica se il valore corrisponde a uno degli alias del componente.

        Il confronto non distingue maiuscole e minuscole.
        """

        normalized_value = value.strip().casefold()

        return any(
            alias.strip().casefold() == normalized_value
            for alias in self.aliases
        )

    def get_attribute(self, key: str) -> EquipmentAttribute | None:
        """
        Restituisce la definizione dell'attributo richiesto, se presente.
        """

        normalized_key = key.strip().casefold()

        for attribute in self.attributes:
            if attribute.key.strip().casefold() == normalized_key:
                return attribute

        return None

    def supports_relation(self, relation_type: str) -> bool:
        """
        Verifica se il tipo di apparecchiatura supporta una relazione.
        """

        normalized_relation = relation_type.strip().casefold()

        return any(
            relation.relation_type.strip().casefold() == normalized_relation
            for relation in self.relations
        )


@dataclass(frozen=True, slots=True)
class Ontology:
    """
    Rappresenta una versione completa dell'ontologia elettrica caricata.
    """

    name: str
    version: str
    equipment_types: dict[str, EquipmentType]
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, equipment_type_id: str) -> EquipmentType | None:
        """
        Recupera un EquipmentType tramite il suo identificativo.
        """

        return self.equipment_types.get(equipment_type_id)

    def require(self, equipment_type_id: str) -> EquipmentType:
        """
        Recupera un EquipmentType oppure solleva
        EquipmentTypeNotFoundError.
        """

        equipment_type = self.get(equipment_type_id)

        if equipment_type is None:
            raise EquipmentTypeNotFoundError(equipment_type_id)

        return equipment_type

    def find_by_alias(self, value: str) -> EquipmentType | None:
        """
        Cerca un tipo di apparecchiatura usando nome, identificativo o alias.
        """

        normalized_value = value.strip().casefold()

        for equipment_type in self.equipment_types.values():
            if equipment_type.id.casefold() == normalized_value:
                return equipment_type

            if equipment_type.name.strip().casefold() == normalized_value:
                return equipment_type

            if equipment_type.has_alias(value):
                return equipment_type

        return None

    def get_children(
        self,
        parent_id: str,
    ) -> tuple[EquipmentType, ...]:
        """
        Restituisce tutti i tipi che dichiarano parent_id
        come genitore diretto.
        """

        return tuple(
            equipment_type
            for equipment_type in self.equipment_types.values()
            if equipment_type.parent == parent_id
        )

    def get_by_category(
        self,
        category: EquipmentCategory,
    ) -> tuple[EquipmentType, ...]:
        """
        Restituisce i tipi appartenenti a una determinata categoria.
        """

        return tuple(
            equipment_type
            for equipment_type in self.equipment_types.values()
            if equipment_type.category == category
        )

    def __len__(self) -> int:
        """
        Restituisce il numero di EquipmentType presenti nell'ontologia.
        """

        return len(self.equipment_types)

    def __contains__(self, equipment_type_id: str) -> bool:
        """
        Verifica se un EquipmentType è presente nell'ontologia.
        """

        return equipment_type_id in self.equipment_types