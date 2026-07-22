from __future__ import annotations

from dataclasses import dataclass

from app.domain.ontology.attribute_exceptions import (
    AttributeDefinitionNotFoundError,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)


@dataclass(frozen=True, slots=True)
class AttributeCatalog:
    attributes: tuple[AttributeDefinition, ...]

    def get(
        self,
        attribute_id: str,
    ) -> AttributeDefinition | None:
        normalized_id = attribute_id.strip().lower()

        return next(
            (
                attribute
                for attribute in self.attributes
                if attribute.id.lower() == normalized_id
            ),
            None,
        )

    def require(
        self,
        attribute_id: str,
    ) -> AttributeDefinition:
        attribute = self.get(attribute_id)

        if attribute is None:
            raise AttributeDefinitionNotFoundError(
                attribute_id
            )

        return attribute

    def find_by_unit(
        self,
        unit: str,
    ) -> tuple[AttributeDefinition, ...]:
        normalized_unit = unit.strip().lower()

        return tuple(
            attribute
            for attribute in self.attributes
            if (
                attribute.unit is not None
                and attribute.unit.lower() == normalized_unit
            )
        )

    def find_by_domain(
        self,
        domain: str,
    ) -> tuple[AttributeDefinition, ...]:
        normalized_domain = domain.strip().lower()

        return tuple(
            attribute
            for attribute in self.attributes
            if str(
                attribute.metadata.get("domain", "")
            ).lower()
            == normalized_domain
        )

    def all(self) -> tuple[AttributeDefinition, ...]:
        return self.attributes

    def __len__(self) -> int:
        return len(self.attributes)

    def __contains__(
        self,
        attribute_id: object,
    ) -> bool:
        if not isinstance(attribute_id, str):
            return False

        return self.get(attribute_id) is not None