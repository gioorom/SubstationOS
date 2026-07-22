from pathlib import Path

import pytest

from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
    OntologyFileNotFoundError,
)
from app.infrastructure.ontology.attribute_yaml_loader import (
    AttributeYamlLoader,
)


def test_loader_reads_valid_attribute_yaml(
    tmp_path: Path,
):
    """
    Il loader deve restituire un dizionario
    quando il file YAML contiene una definizione valida.
    """

    # Arrange
    file_path = tmp_path / "rated_voltage.yaml"

    file_path.write_text(
        "\n".join(
            [
                "id: rated_voltage",
                "name: Rated Voltage",
                "data_type: float",
                "unit: kV",
            ]
        ),
        encoding="utf-8",
    )

    loader = AttributeYamlLoader()

    # Act
    data = loader.load(file_path)

    # Assert
    assert data["id"] == "rated_voltage"
    assert data["name"] == "Rated Voltage"
    assert data["data_type"] == "float"
    assert data["unit"] == "kV"


def test_loader_rejects_missing_file(
    tmp_path: Path,
):
    """
    Il loader deve sollevare un'eccezione specifica
    quando il file non esiste.
    """

    # Arrange
    file_path = tmp_path / "missing.yaml"
    loader = AttributeYamlLoader()

    # Act / Assert
    with pytest.raises(OntologyFileNotFoundError):
        loader.load(file_path)


def test_loader_rejects_non_mapping_yaml(
    tmp_path: Path,
):
    """
    Una definizione di attributo deve essere
    rappresentata da una mappa YAML.
    """

    # Arrange
    file_path = tmp_path / "invalid.yaml"

    file_path.write_text(
        "\n".join(
            [
                "- rated_voltage",
                "- rated_current",
            ]
        ),
        encoding="utf-8",
    )

    loader = AttributeYamlLoader()

    # Act / Assert
    with pytest.raises(InvalidOntologySchemaError):
        loader.load(file_path)


def test_loader_rejects_invalid_yaml(
    tmp_path: Path,
):
    """
    Il loader deve tradurre gli errori di parsing YAML
    in InvalidOntologySchemaError.
    """

    # Arrange
    file_path = tmp_path / "invalid_syntax.yaml"

    file_path.write_text(
        "\n".join(
            [
                "id: rated_voltage",
                "name: [invalid",
            ]
        ),
        encoding="utf-8",
    )

    loader = AttributeYamlLoader()

    # Act / Assert
    with pytest.raises(InvalidOntologySchemaError):
        loader.load(file_path)