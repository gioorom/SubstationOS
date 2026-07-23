from pathlib import Path

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.models import (
    AttributeDataType,
)
from app.infrastructure.ontology.filesystem_equipment_definition_repository import (
    FilesystemEquipmentDefinitionRepository,
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


def test_repository_loads_definition(
    tmp_path: Path,
):
    file = (
        tmp_path
        / "power_transformer.yaml"
    )

    file.write_text(
        """
id: power_transformer
name: Power Transformer
category: transformer

attributes:
  - id: rated_voltage
  - id: frequency
    required: false
""".strip(),
        encoding="utf-8",
    )

    repository = (
        FilesystemEquipmentDefinitionRepository(
            tmp_path,
            create_catalog(),
        )
    )

    definitions = (
        repository.load_equipment_definitions()
    )

    assert len(definitions) == 1
    assert (
        definitions[0].id
        == "power_transformer"
    )
    assert (
        len(definitions[0].attributes)
        == 2
    )