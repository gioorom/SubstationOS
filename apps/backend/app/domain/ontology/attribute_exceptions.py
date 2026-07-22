from __future__ import annotations

from app.domain.ontology.exceptions import OntologyError


class AttributeDefinitionNotFoundError(OntologyError):
    """
    Definizione globale di attributo richiesta ma inesistente.
    """

    def __init__(self, attribute_id: str) -> None:
        self.attribute_id = attribute_id

        super().__init__(
            f"Attribute definition '{attribute_id}' not found."
        )