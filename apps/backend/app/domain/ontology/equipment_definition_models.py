from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)


@dataclass(frozen=True, slots=True)
class EquipmentAttribute:
    """
    Attributo utilizzato da una definizione
    di apparecchiatura.
    """

    definition: AttributeDefinition
    required: bool = True
    default_value: object | None = None


@dataclass(frozen=True, slots=True)
class EquipmentDefinition:
    """
    Definizione completa di una tipologia
    di apparecchiatura.
    """

    id: str
    name: str
    category: str

    attributes: tuple[
        EquipmentAttribute,
        ...
    ] = field(default_factory=tuple)

    metadata: dict[str, object] = field(
        default_factory=dict
    )