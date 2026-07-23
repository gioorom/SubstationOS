from __future__ import annotations

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)


class AttributeDefinitionService:
    """
    Servizi di dominio per le definizioni
    globali degli attributi.
    """

    def __init__(
        self,
        catalog: AttributeCatalog,
    ) -> None:
        self._catalog = catalog

    def exists(
        self,
        attribute_id: str,
    ) -> bool:
        return attribute_id in self._catalog

    def get(
        self,
        attribute_id: str,
    ) -> AttributeDefinition | None:
        return self._catalog.get(attribute_id)

    def require(
        self,
        attribute_id: str,
    ) -> AttributeDefinition:
        return self._catalog.require(attribute_id)

    def find_by_unit(
        self,
        unit: str,
    ) -> tuple[AttributeDefinition, ...]:
        return self._catalog.find_by_unit(unit)

    def find_by_domain(
        self,
        domain: str,
    ) -> tuple[AttributeDefinition, ...]:
        return self._catalog.find_by_domain(domain)

    def all(
        self,
    ) -> tuple[AttributeDefinition, ...]:
        return self._catalog.all()