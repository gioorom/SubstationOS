import pytest

from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.attribute_validator import (
    AttributeDefinitionValidator,
)
from app.domain.ontology.models import (
    AttributeDataType,
)


def create_attribute(
    attribute_id: str,
) -> AttributeDefinition:
    return AttributeDefinition(
        id=attribute_id,
        name=attribute_id,
        data_type=AttributeDataType.STRING,
    )


def test_validator_accepts_unique_ids():
    attributes = [
        create_attribute("rated_voltage"),
        create_attribute("frequency"),
    ]

    AttributeDefinitionValidator.validate(
        attributes
    )


def test_validator_rejects_duplicate_ids():
    attributes = [
        create_attribute("rated_voltage"),
        create_attribute("rated_voltage"),
    ]

    with pytest.raises(ValueError):
        AttributeDefinitionValidator.validate(
            attributes
        )