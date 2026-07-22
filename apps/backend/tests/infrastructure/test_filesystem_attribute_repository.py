from pathlib import Path

from app.infrastructure.ontology.filesystem_attribute_repository import (
    FilesystemAttributeRepository,
)

ATTRIBUTES_PATH = Path(
    "app/domain/ontology/attributes"
)


def test_repository_loads_attributes():
    """
    Il repository deve caricare tutte
    le definizioni degli attributi.
    """

    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    attributes = (
        repository.load_attribute_definitions()
    )

    assert len(attributes) == 4


def test_repository_loads_rated_voltage():
    """
    rated_voltage deve essere presente.
    """

    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    attributes = (
        repository.load_attribute_definitions()
    )

    ids = {
        attribute.id
        for attribute in attributes
    }

    assert "rated_voltage" in ids


def test_repository_loads_frequency():
    """
    frequency deve essere presente.
    """

    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    attributes = (
        repository.load_attribute_definitions()
    )

    frequency = next(
        a
        for a in attributes
        if a.id == "frequency"
    )

    assert frequency.unit == "Hz"
    assert frequency.allowed_values == (
        50,
        60,
    )


def test_repository_returns_domain_objects():
    """
    Il repository deve restituire
    oggetti di dominio.
    """

    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    attributes = (
        repository.load_attribute_definitions()
    )

    assert all(
        hasattr(attribute, "data_type")
        for attribute in attributes
    )