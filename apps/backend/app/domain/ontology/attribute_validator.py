from __future__ import annotations

from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)


class AttributeDefinitionValidator:
    """
    Valida un insieme di definizioni di attributi.
    """

    @staticmethod
    def validate(
        attributes: list[AttributeDefinition],
    ) -> None:
        AttributeDefinitionValidator._validate_unique_ids(
            attributes
        )

    @staticmethod
    def _validate_unique_ids(
        attributes: list[AttributeDefinition],
    ) -> None:
        ids = [attribute.id for attribute in attributes]

        duplicates = {
            attribute_id
            for attribute_id in ids
            if ids.count(attribute_id) > 1
        }

        if duplicates:
            duplicate_list = ", ".join(
                sorted(duplicates)
            )

            raise ValueError(
                "Duplicate attribute definitions found: "
                f"{duplicate_list}"
            )