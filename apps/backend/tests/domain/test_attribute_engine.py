from app.domain.ontology.attribute_engine import (
    AttributeDefinitionEngine,
)
from app.infrastructure.ontology.filesystem_attribute_repository import (
    FilesystemAttributeRepository,
)

from pathlib import Path


ATTRIBUTES_PATH = Path(
    "app/domain/ontology/attributes"
)


def test_engine_loads_attribute_catalog():
    repository = FilesystemAttributeRepository(
        ATTRIBUTES_PATH
    )

    engine = AttributeDefinitionEngine(repository)

    catalog = engine.load()

    assert len(catalog) == 18
    assert "rated_voltage" in catalog
    assert catalog.require("frequency").unit == "Hz"