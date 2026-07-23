from app.domain.ontology.attribute_catalog import (
    AttributeCatalog,
)
from app.domain.ontology.attribute_models import (
    AttributeDefinition,
)
from app.domain.ontology.attribute_service import (
    AttributeDefinitionService,
)
from app.domain.ontology.models import (
    AttributeDataType,
)


def create_service() -> AttributeDefinitionService:
    catalog = AttributeCatalog(
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
                name="Frequency",
                data_type=AttributeDataType.FLOAT,
                unit="Hz",
                metadata={
                    "domain": "electrical_rating",
                },
            ),
        )
    )

    return AttributeDefinitionService(
        catalog
    )


def test_exists():
    service = create_service()

    assert service.exists("rated_voltage")
    assert not service.exists("unknown")


def test_get():
    service = create_service()

    attribute = service.get("frequency")

    assert attribute is not None
    assert attribute.unit == "Hz"


def test_require():
    service = create_service()

    attribute = service.require(
        "rated_voltage"
    )

    assert attribute.name == "Rated Voltage"


def test_find_by_unit():
    service = create_service()

    attributes = service.find_by_unit("kV")

    assert len(attributes) == 1


def test_find_by_domain():
    service = create_service()

    attributes = service.find_by_domain(
        "electrical_rating"
    )

    assert len(attributes) == 2


def test_all():
    service = create_service()

    assert len(service.all()) == 2