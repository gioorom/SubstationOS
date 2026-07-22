import pytest

from app.domain.ontology.attribute_factory import (
    AttributeDefinitionFactory,
)
from app.domain.ontology.models import AttributeDataType


def test_factory_creates_attribute_definition():
    """
    La factory deve costruire correttamente
    una definizione di attributo.
    """

    # Arrange
    data = {
        "id": "rated_voltage",
        "name": "Rated Voltage",
        "data_type": "float",
        "description": "Nominal voltage.",
        "unit": "kV",
        "metadata": {
            "domain": "electrical_rating",
        },
    }

    # Act
    attribute = AttributeDefinitionFactory.from_dict(data)

    # Assert
    assert attribute.id == "rated_voltage"
    assert attribute.name == "Rated Voltage"
    assert attribute.data_type == AttributeDataType.FLOAT
    assert attribute.unit == "kV"
    assert attribute.metadata["domain"] == "electrical_rating"


def test_factory_converts_allowed_values_to_tuple():
    """
    allowed_values deve essere immutabile
    nel modello di dominio.
    """

    # Arrange
    data = {
        "id": "frequency",
        "name": "Rated Frequency",
        "data_type": "float",
        "allowed_values": [50, 60],
    }

    # Act
    attribute = AttributeDefinitionFactory.from_dict(data)

    # Assert
    assert attribute.allowed_values == (50, 60)
    assert isinstance(attribute.allowed_values, tuple)


def test_factory_rejects_unknown_data_type():
    """
    Un data_type non supportato deve essere rifiutato.
    """

    # Arrange
    data = {
        "id": "rated_voltage",
        "name": "Rated Voltage",
        "data_type": "decimal",
    }

    # Act / Assert
    with pytest.raises(ValueError):
        AttributeDefinitionFactory.from_dict(data)