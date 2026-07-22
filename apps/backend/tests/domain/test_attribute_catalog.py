import pytest

from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_exceptions import (
    AttributeDefinitionNotFoundError,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.models import (
    AttributeDataType,
)


def create_catalog() -> AttributeCatalog:
    return AttributeCatalog(
        attributes=(
            AttributeDefinition(
                id="rated_voltage",
                name="Rated Voltage",
                data_type=AttributeDataType.FLOAT,
                unit="kV",
                metadata={
                    "domain": "electrical_rating",
                },
            ),
            AttributeDefinition(
                id="frequency",
                name="Rated Frequency",
                data_type=AttributeDataType.FLOAT,
                unit="Hz",
                metadata={
                    "domain": "electrical_rating",
                },
            ),
        )
    )


def test_catalog_get():
    catalog = create_catalog()

    attribute = catalog.get("rated_voltage")

    assert attribute is not None
    assert attribute.name == "Rated Voltage"


def test_catalog_get_is_case_insensitive():
    catalog = create_catalog()

    attribute = catalog.get(" RATED_VOLTAGE ")

    assert attribute is not None
    assert attribute.id == "rated_voltage"


def test_catalog_get_returns_none():
    catalog = create_catalog()

    assert catalog.get("unknown") is None


def test_catalog_require():
    catalog = create_catalog()

    attribute = catalog.require("frequency")

    assert attribute.unit == "Hz"


def test_catalog_require_raises():
    catalog = create_catalog()

    with pytest.raises(
        AttributeDefinitionNotFoundError
    ):
        catalog.require("unknown")


def test_catalog_find_by_unit():
    catalog = create_catalog()

    attributes = catalog.find_by_unit("kV")

    assert len(attributes) == 1
    assert attributes[0].id == "rated_voltage"


def test_catalog_find_by_domain():
    catalog = create_catalog()

    attributes = catalog.find_by_domain(
        "electrical_rating"
    )

    assert len(attributes) == 2


def test_catalog_all():
    catalog = create_catalog()

    attributes = catalog.all()

    assert len(attributes) == 2
    assert isinstance(attributes, tuple)


def test_catalog_len():
    catalog = create_catalog()

    assert len(catalog) == 2


def test_catalog_contains():
    catalog = create_catalog()

    assert "rated_voltage" in catalog
    assert "unknown" not in catalog