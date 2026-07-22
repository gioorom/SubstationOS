from __future__ import annotations

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_repository import (
    AttributeDefinitionRepository,
)
from app.domain.ontology.attribute_validator import (
    AttributeDefinitionValidator,
)


class AttributeDefinitionEngine:
    def __init__(
        self,
        repository: AttributeDefinitionRepository,
    ) -> None:
        self._repository = repository

    def load(self) -> AttributeCatalog:
        attributes = (
            self._repository.load_attribute_definitions()
        )

        AttributeDefinitionValidator.validate(
            attributes
        )

        return AttributeCatalog(
            attributes=tuple(attributes),
        )