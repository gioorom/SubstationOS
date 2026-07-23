from pathlib import Path

import pytest

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.equipment_definition_engine import (
    EquipmentDefinitionEngine,
)
from app.domain.ontology.exceptions import (
    DuplicateEquipmentDefinitionError,
)
from app.domain.ontology.models import (
    AttributeDataType,
)
from app.infrastructure.ontology.filesystem_equipment_definition_repository import (
    FilesystemEquipmentDefinitionRepository,
)


def create_catalog():
    return AttributeCatalog(
        attributes=(
            AttributeDefinition(
                id="rated_voltage",
                name="Rated Voltage",
                data_type=AttributeDataType.FLOAT,
                unit="kV",
            ),
        )
    )


def test_engine_loads_catalog(
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
""".strip(),
        encoding="utf-8",
    )

    repository = (
        FilesystemEquipmentDefinitionRepository(
            tmp_path,
            create_catalog(),
        )
    )

    engine = (
        EquipmentDefinitionEngine(
            repository
        )
    )

    catalog = engine.load()

    assert len(catalog) == 1
    assert (
        "power_transformer"
        in catalog
    )
    assert (
        catalog.require(
            "power_transformer"
        ).name
        == "Power Transformer"
    )


def test_engine_rejects_duplicate_definitions(
    tmp_path: Path,
):
    first_file = (
        tmp_path
        / "power_transformer.yaml"
    )

    first_file.write_text(
        """
id: power_transformer
name: Power Transformer
category: transformer
""".strip(),
        encoding="utf-8",
    )

    second_file = (
        tmp_path
        / "power_transformer_duplicate.yaml"
    )

    second_file.write_text(
        """
id: Power_Transformer
name: Power Transformer Duplicate
category: transformer
""".strip(),
        encoding="utf-8",
    )

    repository = (
        FilesystemEquipmentDefinitionRepository(
            tmp_path,
            create_catalog(),
        )
    )

    engine = (
        EquipmentDefinitionEngine(
            repository
        )
    )

    with pytest.raises(
        DuplicateEquipmentDefinitionError
    ):
        engine.load()