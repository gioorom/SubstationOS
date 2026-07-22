from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
    OntologyFileNotFoundError,
    OntologyLoadError,
)


class AttributeYamlLoader:
    """
    Carica una definizione di attributo da un file YAML.

    Il loader legge e interpreta il file, ma non costruisce
    oggetti appartenenti al dominio.
    """

    def load(
        self,
        file_path: Path,
    ) -> dict[str, Any]:
        if not file_path.exists():
            raise OntologyFileNotFoundError(
                f"Attribute definition file not found: "
                f"'{file_path}'."
            )

        if not file_path.is_file():
            raise OntologyLoadError(
                f"Attribute definition path is not a file: "
                f"'{file_path}'."
            )

        try:
            with file_path.open(
                mode="r",
                encoding="utf-8",
            ) as stream:
                data = yaml.safe_load(stream)

        except yaml.YAMLError as error:
            raise InvalidOntologySchemaError(
                f"Invalid YAML in attribute definition file "
                f"'{file_path}'."
            ) from error

        except OSError as error:
            raise OntologyLoadError(
                f"Unable to read attribute definition file "
                f"'{file_path}'."
            ) from error

        if not isinstance(data, dict):
            raise InvalidOntologySchemaError(
                f"Attribute definition file '{file_path}' "
                "must contain a YAML mapping."
            )

        return data