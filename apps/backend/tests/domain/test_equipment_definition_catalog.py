import pytest

from app.domain.ontology.equipment_definition_catalog import (
    EquipmentDefinitionCatalog,
)
from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)
from app.domain.ontology.exceptions import (
    EquipmentDefinitionNotFoundError,
)


def create_catalog() -> EquipmentDefinitionCatalog:
    return EquipmentDefinitionCatalog(
        definitions=(
            EquipmentDefinition(
                id="power_transformer",
                name="Power Transformer",
                category="transformer",
            ),
        )
    )


def test_catalog_require_returns_existing_definition():
    catalog = create_catalog()

    definition = catalog.require(
        "power_transformer"
    )

    assert definition.name == "Power Transformer"


def test_catalog_require_raises_for_missing_definition():
    catalog = create_catalog()

    with pytest.raises(
        EquipmentDefinitionNotFoundError
    ):
        catalog.require("unknown")
