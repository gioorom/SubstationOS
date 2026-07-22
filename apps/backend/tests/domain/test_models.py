import pytest

from app.domain.ontology.exceptions import (
    EquipmentTypeNotFoundError,
)
from app.domain.ontology.models import (
    AttributeDataType,
    EquipmentAttribute,
    EquipmentCategory,
    EquipmentRelation,
    EquipmentType,
    Ontology,
)


def create_breaker() -> EquipmentType:
    """
    Crea un EquipmentType riutilizzabile nei test.
    """

    return EquipmentType(
        id="breaker",
        name="Circuit Breaker",
        category=EquipmentCategory.PRIMARY_EQUIPMENT,
        aliases=(
            "CB",
            "Interruttore",
        ),
        attributes=(
            EquipmentAttribute(
                key="rated_voltage",
                name="Rated Voltage",
                data_type=AttributeDataType.FLOAT,
                unit="kV",
                required=True,
            ),
        ),
        relations=(
            EquipmentRelation(
                relation_type="protected_by",
                target_types=("relay",),
            ),
        ),
    )


def create_ontology() -> Ontology:
    """
    Crea una piccola ontologia per i test unitari.
    """

    breaker = create_breaker()

    disconnector = EquipmentType(
        id="disconnector",
        name="Disconnector",
        category=EquipmentCategory.PRIMARY_EQUIPMENT,
        parent="switching_device",
        aliases=("Sezionatore",),
    )

    switching_device = EquipmentType(
        id="switching_device",
        name="Switching Device",
        category=EquipmentCategory.PRIMARY_EQUIPMENT,
    )

    relay = EquipmentType(
        id="relay",
        name="Protection Relay",
        category=EquipmentCategory.PROTECTION,
        aliases=("Relè",),
    )

    return Ontology(
        name="Test Electrical Ontology",
        version="0.1.0",
        equipment_types={
            breaker.id: breaker,
            disconnector.id: disconnector,
            switching_device.id: switching_device,
            relay.id: relay,
        },
    )


def test_equipment_type_has_alias_case_insensitive():
    """
    La ricerca degli alias non deve distinguere
    maiuscole e minuscole.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    result = breaker.has_alias("cb")

    # Assert
    assert result is True


def test_equipment_type_has_alias_ignores_whitespace():
    """
    La ricerca degli alias deve ignorare
    gli spazi iniziali e finali.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    result = breaker.has_alias("  Interruttore  ")

    # Assert
    assert result is True


def test_equipment_type_returns_attribute_by_key():
    """
    Deve essere possibile recuperare
    un attributo tramite la sua chiave.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    attribute = breaker.get_attribute("rated_voltage")

    # Assert
    assert attribute is not None
    assert attribute.name == "Rated Voltage"
    assert attribute.unit == "kV"
    assert attribute.required is True


def test_equipment_type_attribute_search_is_case_insensitive():
    """
    La ricerca degli attributi non deve distinguere
    maiuscole e minuscole.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    attribute = breaker.get_attribute("RATED_VOLTAGE")

    # Assert
    assert attribute is not None
    assert attribute.key == "rated_voltage"


def test_equipment_type_returns_none_for_unknown_attribute():
    """
    Un attributo inesistente deve restituire None.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    attribute = breaker.get_attribute("unknown_attribute")

    # Assert
    assert attribute is None


def test_equipment_type_supports_relation():
    """
    Deve essere possibile verificare
    una relazione supportata.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    result = breaker.supports_relation("protected_by")

    # Assert
    assert result is True


def test_equipment_type_relation_search_is_case_insensitive():
    """
    La ricerca delle relazioni non deve distinguere
    maiuscole e minuscole.
    """

    # Arrange
    breaker = create_breaker()

    # Act
    result = breaker.supports_relation("PROTECTED_BY")

    # Assert
    assert result is True


def test_ontology_get_returns_equipment_type():
    """
    Ontology.get() deve restituire
    il tipo richiesto.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    breaker = ontology.get("breaker")

    # Assert
    assert breaker is not None
    assert breaker.id == "breaker"


def test_ontology_get_returns_none_for_unknown_id():
    """
    Ontology.get() deve restituire None
    per un identificativo sconosciuto.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    equipment = ontology.get("unknown")

    # Assert
    assert equipment is None


def test_ontology_require_returns_equipment_type():
    """
    Ontology.require() deve restituire
    il tipo richiesto quando esiste.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    breaker = ontology.require("breaker")

    # Assert
    assert breaker.id == "breaker"


def test_ontology_require_raises_custom_exception():
    """
    Ontology.require() deve sollevare
    EquipmentTypeNotFoundError se il tipo non esiste.
    """

    # Arrange
    ontology = create_ontology()

    # Act / Assert
    with pytest.raises(EquipmentTypeNotFoundError):
        ontology.require("unknown")


@pytest.mark.parametrize(
    ("search_value", "expected_id"),
    [
        ("breaker", "breaker"),
        ("Circuit Breaker", "breaker"),
        ("CB", "breaker"),
        ("cb", "breaker"),
        ("Interruttore", "breaker"),
        ("Protection Relay", "relay"),
        ("Relè", "relay"),
    ],
)
def test_ontology_find_by_alias(
    search_value: str,
    expected_id: str,
):
    """
    Ontology.find_by_alias() deve cercare
    per id, nome e alias.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    equipment = ontology.find_by_alias(search_value)

    # Assert
    assert equipment is not None
    assert equipment.id == expected_id


def test_ontology_find_by_alias_returns_none():
    """
    Una ricerca senza corrispondenze
    deve restituire None.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    equipment = ontology.find_by_alias("non_existing_equipment")

    # Assert
    assert equipment is None


def test_ontology_get_children():
    """
    Deve essere possibile recuperare
    i figli diretti di un EquipmentType.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    children = ontology.get_children("switching_device")

    # Assert
    assert len(children) == 1
    assert children[0].id == "disconnector"


def test_ontology_get_by_category():
    """
    Deve essere possibile filtrare
    gli EquipmentType per categoria.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    protection_equipment = ontology.get_by_category(
        EquipmentCategory.PROTECTION
    )

    # Assert
    assert len(protection_equipment) == 1
    assert protection_equipment[0].id == "relay"


def test_ontology_len():
    """
    len(ontology) deve restituire
    il numero di EquipmentType.
    """

    # Arrange
    ontology = create_ontology()

    # Act
    result = len(ontology)

    # Assert
    assert result == 4


def test_ontology_contains_equipment_type():
    """
    L'operatore 'in' deve verificare
    la presenza di un identificativo.
    """

    # Arrange
    ontology = create_ontology()

    # Act / Assert
    assert "breaker" in ontology
    assert "unknown" not in ontology