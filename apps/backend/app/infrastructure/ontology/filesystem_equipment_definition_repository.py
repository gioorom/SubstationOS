from __future__ import annotations

from pathlib import Path

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.equipment_definition_factory import (
    EquipmentDefinitionFactory,
)
from app.domain.ontology.equipment_definition_models import (
    EquipmentDefinition,
)
from app.domain.ontology.equipment_definition_repository import (
    EquipmentDefinitionRepository,
)

from .equipment_definition_yaml_loader import (
    EquipmentDefinitionYamlLoader,
)


class FilesystemEquipmentDefinitionRepository(
    EquipmentDefinitionRepository,
):
    """
    Repository filesystem delle
    definizioni di apparecchiature.
    """

    def __init__(
        self,
        root: Path,
        catalog: AttributeCatalog,
        loader: EquipmentDefinitionYamlLoader | None = None,
    ) -> None:
        self._root = root
        self._catalog = catalog
        self._loader = (
            loader
            or EquipmentDefinitionYamlLoader()
        )

    def load_equipment_definitions(
        self,
    ) -> list[EquipmentDefinition]:
        definitions: list[
            EquipmentDefinition
        ] = []

        for file_path in sorted(
            self._root.glob("*.yaml")
        ):
            data = self._loader.load(
                file_path
            )

            definitions.append(
                EquipmentDefinitionFactory.from_dict(
                    data,
                    self._catalog,
                )
            )

        return definitions