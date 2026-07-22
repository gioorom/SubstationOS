from pathlib import Path

from app.infrastructure.ontology.yaml_loader import (
    YamlOntologyLoader,
)


def test_load_valid_yaml(tmp_path: Path):
    """
    Il loader deve restituire un dizionario
    quando il file YAML è valido.
    """

    yaml_file = tmp_path / "breaker.yaml"

    yaml_file.write_text(
        """
id: breaker
name: Circuit Breaker
category: primary_equipment
""",
        encoding="utf-8",
    )

    loader = YamlOntologyLoader()

    data = loader.load(yaml_file)

    assert data["id"] == "breaker"
    assert data["name"] == "Circuit Breaker"
    assert data["category"] == "primary_equipment"
    
    # primo test per verificare che il loader gestisca correttamente un file YAML valido.
    
import pytest

from app.domain.ontology.exceptions import (
    OntologyFileNotFoundError,
)


def test_missing_file():
    """
    Deve essere sollevata la nostra eccezione
    se il file non esiste.
    """

    loader = YamlOntologyLoader()

    with pytest.raises(OntologyFileNotFoundError):
        loader.load("file_inesistente.yaml")   
        
        # secondo test per verificare che il loader sollevi l'eccezzione OntologyFileNotFoundError quando il file YAML non esiste.
        
from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
)


def test_yaml_root_must_be_mapping(tmp_path: Path):
    """
    La radice del documento deve essere un dict.
    """

    yaml_file = tmp_path / "invalid.yaml"

    yaml_file.write_text(
        """
- breaker
- transformer
""",
        encoding="utf-8",
    )

    loader = YamlOntologyLoader()

    with pytest.raises(
        InvalidOntologySchemaError
    ):
        loader.load(yaml_file)
        
# terzo test per verificare che il loader sollevi l'eccezione InvalidOntologySchemaError quando la radice del documento YAML non è un dizionario.
        