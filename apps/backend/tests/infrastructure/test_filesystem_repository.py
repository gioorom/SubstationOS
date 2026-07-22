from pathlib import Path

from app.domain.ontology.models import (
    EquipmentCategory,
    EquipmentType,
)
from app.infrastructure.ontology.filesystem_repository import (
    FilesystemEquipmentTypeRepository,
)


ONTOLOGY_PATH = Path("app/domain/ontology/equipment_types")


def test_load_equipment_types():
    """
    Il repository deve caricare gli EquipmentType
    presenti nella cartella dell'ontologia.
    """

    # Arrange
    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    # Act
    equipment_types = repository.load_equipment_types()

    # Assert
    assert len(equipment_types) > 0

    assert all(
        isinstance(item, EquipmentType)
        for item in equipment_types
    )


def test_breaker_is_loaded():
    """
    Il breaker deve essere presente
    e correttamente popolato.
    """

    # Arrange
    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    # Act
    equipment_types = repository.load_equipment_types()

    breaker = next(
        equipment
        for equipment in equipment_types
        if equipment.id == "breaker"
    )

    # Assert
    assert breaker.name == "Circuit Breaker"
    assert (
        breaker.category
        == EquipmentCategory.PRIMARY_EQUIPMENT
    )


def test_all_equipment_ids_are_unique():
    """
    Tutti gli EquipmentType devono avere
    un identificativo univoco.
    """

    # Arrange
    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    # Act
    equipment_types = repository.load_equipment_types()

    ids = [
        equipment.id
        for equipment in equipment_types
    ]

    # Assert
    assert len(ids) == len(set(ids))


def test_transformer_is_loaded():
    """
    Il trasformatore deve essere presente.
    """

    # Arrange
    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    # Act
    equipment_types = repository.load_equipment_types()

    transformer = next(
        equipment
        for equipment in equipment_types
        if equipment.id == "transformer"
    )

    # Assert
    assert transformer.name == "Power Transformer"
    assert (
        transformer.category
        == EquipmentCategory.PRIMARY_EQUIPMENT
    )


def test_repository_contains_expected_equipment():
    """
    L'ontologia deve contenere almeno
    i componenti fondamentali della cabina.
    """

    # Arrange
    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    # Act
    equipment_types = repository.load_equipment_types()

    ids = {
        equipment.id
        for equipment in equipment_types
    }

    # Assert
    expected = {
        "breaker",
        "transformer",
        "current_transformer",
        "voltage_transformer",
        "busbar",
        "disconnector",
        "earthing_switch",
        "surge_arrester",
        "relay",
    }

    assert expected.issubset(ids)