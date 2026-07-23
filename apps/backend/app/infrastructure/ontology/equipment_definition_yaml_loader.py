from __future__ import annotations

from pathlib import Path

import yaml

from app.domain.ontology.exceptions import (
    InvalidOntologySchemaError,
    OntologyFileNotFoundError,
    OntologyLoadError,
)


class EquipmentDefinitionYamlLoader:
    """
    Carica una definizione di apparecchiatura
    da un file YAML.
    """

    def load(
        self,
        file_path: Path,
    ) -> dict:
        if not file_path.exists():
            raise OntologyFileNotFoundError(
                str(file_path)
            )

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = yaml.safe_load(file)

        except yaml.YAMLError as exc:
            raise OntologyLoadError(
                str(file_path)
            ) from exc

        except OSError as exc:
            raise OntologyLoadError(
                str(file_path)
            ) from exc

        if not isinstance(data, dict):
            raise InvalidOntologySchemaError(
                str(file_path)
            )

        return data