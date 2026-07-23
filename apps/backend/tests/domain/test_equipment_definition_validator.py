import pytest

from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)
from app.domain.ontology.equipment_definition_validator import (
    EquipmentDefinitionValidator,
)
from app.domain.ontology.exceptions import (
    DuplicateEquipmentDefinitionError,
)


def create_equipment(
    equipment_id: str,
) -> EquipmentDefinition:
    return EquipmentDefinition(
        id=equipment_id,
        name=equipment_id,
        category="primary_equipment",
    )


def test_validator_accepts_empty_collection():
    EquipmentDefinitionValidator.validate([])


def test_validator_accepts_unique_ids():
    definitions = [
        create_equipment("power_transformer"),
        create_equipment("circuit_breaker"),
    ]

    EquipmentDefinitionValidator.validate(
        definitions
    )


def test_validator_rejects_duplicate_ids():
    definitions = [
        create_equipment("power_transformer"),
        create_equipment("power_transformer"),
    ]

    with pytest.raises(
        DuplicateEquipmentDefinitionError
    ):
        EquipmentDefinitionValidator.validate(
            definitions
        )


def test_validator_rejects_case_insensitive_duplicate_ids():
    definitions = [
        create_equipment("Power_Transformer"),
        create_equipment("power_transformer"),
    ]

    with pytest.raises(
        DuplicateEquipmentDefinitionError
    ):
        EquipmentDefinitionValidator.validate(
            definitions
        )
