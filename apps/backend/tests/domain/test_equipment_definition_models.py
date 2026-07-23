from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.equipment_definition_models import (
    EquipmentAttribute,
    EquipmentDefinition,
)
from app.domain.ontology.models import (
    AttributeDataType,
)


def create_attribute() -> AttributeDefinition:
    return AttributeDefinition(
        id="rated_voltage",
        name="Rated Voltage",
        data_type=AttributeDataType.FLOAT,
        unit="kV",
    )


def test_equipment_attribute():
    definition = create_attribute()

    attribute = EquipmentAttribute(
        definition=definition,
    )

    assert attribute.required
    assert (
        attribute.definition.id
        == "rated_voltage"
    )


def test_equipment_attribute_default_value():
    definition = create_attribute()

    attribute = EquipmentAttribute(
        definition=definition,
        required=False,
        default_value=132,
    )

    assert not attribute.required
    assert attribute.default_value == 132


def test_equipment_definition():
    definition = create_attribute()

    equipment = EquipmentDefinition(
        id="power_transformer",
        name="Power Transformer",
        category="transformer",
        attributes=(
            EquipmentAttribute(
                definition=definition,
            ),
        ),
    )

    assert equipment.id == "power_transformer"
    assert equipment.category == "transformer"
    assert len(equipment.attributes) == 1


def test_equipment_definition_metadata():
    equipment = EquipmentDefinition(
        id="power_transformer",
        name="Power Transformer",
        category="transformer",
        metadata={
            "iec": "60076",
        },
    )

    assert (
        equipment.metadata["iec"]
        == "60076"
    )