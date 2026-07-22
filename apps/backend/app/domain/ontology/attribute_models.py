from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AttributeDataType


@dataclass(frozen=True, slots=True)
class AttributeDefinition:
    """
    Definisce un attributo riutilizzabile all'interno dell'ontologia.

    Esempi:
    - rated_voltage;
    - rated_current;
    - frequency;
    - breaking_capacity.

    La definizione dell'attributo è indipendente dagli EquipmentType
    che la utilizzano.
    """

    id: str
    name: str
    data_type: AttributeDataType
    description: str | None = None
    unit: str | None = None
    allowed_values: tuple[Any, ...] = ()
    default_value: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)