from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.equipment_definition_factory import (
    EquipmentDefinitionFactory,
)
from app.domain.ontology.models import (
    AttributeDataType,
)


def create_catalog() -> AttributeCatalog:
    return AttributeCatalog(
        attributes=(
            AttributeDefinition(
                id="rated_voltage",
                name="Rated Voltage",
                data_type=AttributeDataType.FLOAT,
                unit="kV",
            ),
            AttributeDefinition(
                id="frequency",
                name="Frequency",
                data_type=AttributeDataType.FLOAT,
                unit="Hz",
            ),
        )
    )


def test_factory_creates_equipment_definition():
    catalog = create_catalog()

    equipment = (
        EquipmentDefinitionFactory.from_dict(
            {
                "id": "power_transformer",
                "name": "Power Transformer",
                "category": "transformer",
                "attributes": [
                    {
                        "id": "rated_voltage",
                    },
                    {
                        "id": "frequency",
                        "required": False,
                    },
                ],
            },
            catalog,
        )
    )

    assert equipment.id == "power_transformer"
    assert equipment.category == "transformer"
    assert len(equipment.attributes) == 2


def test_factory_sets_required_flag():
    catalog = create_catalog()

    equipment = (
        EquipmentDefinitionFactory.from_dict(
            {
                "id": "power_transformer",
                "name": "Power Transformer",
                "category": "transformer",
                "attributes": [
                    {
                        "id": "frequency",
                        "required": False,
                    }
                ],
            },
            catalog,
        )
    )

    assert (
        equipment.attributes[0].required
        is False
    )


def test_factory_sets_default_value():
    catalog = create_catalog()

    equipment = (
        EquipmentDefinitionFactory.from_dict(
            {
                "id": "power_transformer",
                "name": "Power Transformer",
                "category": "transformer",
                "attributes": [
                    {
                        "id": "rated_voltage",
                        "default_value": 132,
                    }
                ],
            },
            catalog,
        )
    )

    assert (
        equipment.attributes[0].default_value
        == 132
    )