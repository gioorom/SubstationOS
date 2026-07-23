from pathlib import Path

from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.infrastructure.ontology.filesystem_attribute_repository import (
    FilesystemAttributeRepository,
)


ATTRIBUTES_PATH = Path(
    "app/domain/ontology/attributes"
)


def load_attributes() -> list[AttributeDefinition]:
    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    return repository.load_attribute_definitions()


def test_repository_loads_all_attributes():
    attributes = load_attributes()

    assert len(attributes) == 18


def test_repository_loads_expected_attribute_ids():
    attributes = load_attributes()

    ids = {
        attribute.id
        for attribute in attributes
    }

    assert ids == {
        "breaking_capacity",
        "frequency",
        "installation_type",
        "insulation_level",
        "lightning_impulse_withstand_voltage",
        "manufacturer",
        "model",
        "neutral_configuration",
        "number_of_phases",
        "peak_withstand_current",
        "power_frequency_withstand_voltage",
        "rated_current",
        "rated_voltage",
        "serial_number",
        "short_time_withstand_current",
        "short_time_withstand_duration",
        "technology",
        "year_of_manufacture",
    }


def test_repository_loads_frequency():
    attributes = load_attributes()

    frequency = next(
        attribute
        for attribute in attributes
        if attribute.id == "frequency"
    )

    assert frequency.unit == "Hz"
    assert frequency.allowed_values == (
        50,
        60,
    )


def test_repository_loads_number_of_phases():
    attributes = load_attributes()

    number_of_phases = next(
        attribute
        for attribute in attributes
        if attribute.id == "number_of_phases"
    )

    assert number_of_phases.allowed_values == (
        1,
        3,
    )
    assert number_of_phases.default_value == 3


def test_repository_returns_domain_objects():
    attributes = load_attributes()

    assert all(
        isinstance(
            attribute,
            AttributeDefinition,
        )
        for attribute in attributes
    )