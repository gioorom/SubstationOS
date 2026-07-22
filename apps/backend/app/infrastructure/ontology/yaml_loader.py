from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
    OntologyFileNotFoundError,
    OntologyLoadError,
)


class YamlOntologyLoader:
    """
    Adattatore infrastrutturale responsabile della lettura di file YAML.

    La classe converte un file YAML in una struttura Python composta da
    dizionari, liste e valori primitivi.

    Non costruisce oggetti di dominio e non esegue validazioni semantiche.
    """

    def load(self, file_path: str | Path) -> dict[str, Any]:
        """
        Legge un file YAML e ne restituisce il contenuto come dizionario.

        Parameters
        ----------
        file_path:
            Percorso del file YAML da caricare.

        Returns
        -------
        dict[str, Any]
            Contenuto del file YAML.

        Raises
        ------
        OntologyFileNotFoundError
            Se il file non esiste.
        InvalidOntologySchemaError
            Se la radice del documento YAML non è un mapping.
        OntologyLoadError
            Se il file non può essere letto o contiene YAML non valido.
        """

        path = Path(file_path)

        if not path.exists():
            raise OntologyFileNotFoundError(
                f"Ontology YAML file not found: '{path}'."
            )

        if not path.is_file():
            raise OntologyLoadError(
                f"Ontology YAML path is not a file: '{path}'."
            )

        try:
            with path.open("r", encoding="utf-8") as yaml_file:
                content = yaml.safe_load(yaml_file)

        except yaml.YAMLError as exc:
            raise OntologyLoadError(
                f"Invalid YAML in ontology file '{path}': {exc}"
            ) from exc

        except OSError as exc:
            raise OntologyLoadError(
                f"Unable to read ontology file '{path}': {exc}"
            ) from exc

        if content is None:
            return {}

        if not isinstance(content, dict):
            raise InvalidOntologySchemaError(
                f"Ontology YAML root must be a mapping in file '{path}'."
            )

        return content