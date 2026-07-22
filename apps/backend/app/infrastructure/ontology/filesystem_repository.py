from __future__ import annotations

from pathlib import Path

from app.domain.ontology.factory import EquipmentTypeFactory
from app.domain.ontology.models import EquipmentType
from app.domain.ontology.repository import OntologyRepository

from .yaml_loader import YamlOntologyLoader


class FilesystemEquipmentTypeRepository(OntologyRepository):
    """
    Repository che legge gli EquipmentType da una cartella
    contenente file YAML.
    """

    def __init__(
        self,
        equipment_directory: str | Path,
        loader: YamlOntologyLoader | None = None,
    ) -> None:
        self._equipment_directory = Path(equipment_directory)
        self._loader = loader or YamlOntologyLoader()

    def load_equipment_types(self) -> list[EquipmentType]:
        """
        Carica tutti gli EquipmentType presenti nella directory.
        """

        equipment_types: list[EquipmentType] = []

        for yaml_file in sorted(
            self._equipment_directory.glob("*.yaml")
        ):
            raw_data = self._loader.load(yaml_file)

            equipment = EquipmentTypeFactory.from_dict(raw_data)

            equipment_types.append(equipment)

        return equipment_types