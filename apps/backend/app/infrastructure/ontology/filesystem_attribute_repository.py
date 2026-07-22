from __future__ import annotations

from pathlib import Path

from app.domain.ontology.attribute_factory import (
    AttributeDefinitionFactory,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.attribute_repository import (
    AttributeDefinitionRepository,
)

from .attribute_yaml_loader import AttributeYamlLoader


class FilesystemAttributeRepository(
    AttributeDefinitionRepository,
):
    """
    Repository filesystem delle definizioni globali
    degli attributi.
    """

    def __init__(
        self,
        root: Path,
        loader: AttributeYamlLoader | None = None,
    ) -> None:
        self._root = root
        self._loader = loader or AttributeYamlLoader()

    def load_attribute_definitions(
        self,
    ) -> list[AttributeDefinition]:
        attributes: list[AttributeDefinition] = []

        for file_path in sorted(
            self._root.glob("*.yaml")
        ):
            data = self._loader.load(file_path)

            attributes.append(
                AttributeDefinitionFactory.from_dict(
                    data
                )
            )

        return attributes