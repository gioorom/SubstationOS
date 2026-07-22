from __future__ import annotations

from app.domain.ontology.models import Ontology
from app.domain.ontology.repository import OntologyRepository
from app.domain.ontology.validator import OntologyValidator


class OntologyEngine:
    """
    Punto di ingresso del dominio Ontology.

    Coordina repository e validator e restituisce
    un'istanza completa dell'Ontology.
    """

    def __init__(
        self,
        repository: OntologyRepository,
        validator: OntologyValidator | None = None,
        *,
        name: str = "Electrical Ontology",
        version: str = "0.1.0",
    ) -> None:
        self._repository = repository
        self._validator = validator or OntologyValidator()
        self._name = name
        self._version = version

    def load(self) -> Ontology:
        """
        Carica, valida e costruisce l'ontologia.
        """

        equipment_types = self._repository.load_equipment_types()

        self._validator.validate(equipment_types)

        return Ontology(
            name=self._name,
            version=self._version,
            equipment_types={
                equipment.id: equipment
                for equipment in equipment_types
            },
        )