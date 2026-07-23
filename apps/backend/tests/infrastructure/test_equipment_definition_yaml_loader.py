from pathlib import Path

import pytest

from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
    OntologyFileNotFoundError,
    OntologyLoadError,
)
from app.infrastructure.ontology.equipment_definition_yaml_loader import (
    EquipmentDefinitionYamlLoader,
)


def test_loader_loads_yaml_file(
    tmp_path: Path,
):
    file_path = (
        tmp_path
        / "power_transformer.yaml"
    )

    file_path.write_text(
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

    loader = EquipmentDefinitionYamlLoader()

    data = loader.load(file_path)

    assert data["id"] == "power_transformer"
    assert data["category"] == "transformer"
    assert len(data["attributes"]) == 2


def test_loader_rejects_missing_file(
    tmp_path: Path,
):
    loader = EquipmentDefinitionYamlLoader()

    with pytest.raises(
        OntologyFileNotFoundError
    ):
        loader.load(
            tmp_path / "missing.yaml"
        )


def test_loader_rejects_invalid_yaml(
    tmp_path: Path,
):
    file_path = tmp_path / "invalid.yaml"

    file_path.write_text(
        "id: [invalid",
        encoding="utf-8",
    )

    loader = EquipmentDefinitionYamlLoader()

    with pytest.raises(OntologyLoadError):
        loader.load(file_path)


def test_loader_rejects_non_mapping_yaml(
    tmp_path: Path,
):
    file_path = tmp_path / "list.yaml"

    file_path.write_text(
        """
- power_transformer
- circuit_breaker
""".strip(),
        encoding="utf-8",
    )

    loader = EquipmentDefinitionYamlLoader()

    with pytest.raises(
        InvalidOntologySchemaError
    ):
        loader.load(file_path)