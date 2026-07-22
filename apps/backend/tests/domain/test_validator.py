import pytest

from app.domain.ontology.exceptions import (
    DuplicateEquipmentTypeError,
    InvalidEquipmentDefinitionError,
    UnknownRelationError,
)
from app.domain.ontology.models import (
    EquipmentCategory,
    EquipmentRelation,
    EquipmentType,
)
from app.domain.ontology.validator import OntologyValidator


def create_equipment_type(
    *,
    equipment_id: str,
    name: str,
    parent: str | None = None,
    relations: tuple[EquipmentRelation, ...] = (),
) -> EquipmentType:
    """
    Crea un EquipmentType minimale per i test del validator.
    """

    return EquipmentType(
        id=equipment_id,
        name=name,
        category=EquipmentCategory.PRIMARY_EQUIPMENT,
        parent=parent,
        relations=relations,
    )


def test_validator_accepts_valid_equipment_types():
    """
    Il validator non deve sollevare eccezioni
    quando le definizioni sono valide.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="switching_device",
            name="Switching Device",
        ),
        create_equipment_type(
            equipment_id="breaker",
            name="Circuit Breaker",
            parent="switching_device",
        ),
    ]

    validator = OntologyValidator()

    # Act
    validator.validate(equipment_types)

    # Assert
    assert True


def test_validator_rejects_duplicate_ids():
    """
    Il validator deve rifiutare
    EquipmentType con identificativi duplicati.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="breaker",
            name="Circuit Breaker",
        ),
        create_equipment_type(
            equipment_id="breaker",
            name="Another Circuit Breaker",
        ),
    ]

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(DuplicateEquipmentTypeError):
        validator.validate(equipment_types)


def test_validator_rejects_empty_equipment_id():
    """
    L'identificativo di un EquipmentType
    non può essere vuoto.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="",
            name="Circuit Breaker",
        ),
    ]

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(InvalidEquipmentDefinitionError):
        validator.validate(equipment_types)


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        " ",
        "   ",
    ],
)
def test_validator_rejects_empty_name(
    invalid_name: str,
):
    """
    Il nome di un EquipmentType
    non può essere vuoto o composto solo da spazi.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="breaker",
            name=invalid_name,
        ),
    ]

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(InvalidEquipmentDefinitionError):
        validator.validate(equipment_types)


def test_validator_accepts_existing_parent():
    """
    Il validator deve accettare
    un riferimento parent esistente.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="switching_device",
            name="Switching Device",
        ),
        create_equipment_type(
            equipment_id="breaker",
            name="Circuit Breaker",
            parent="switching_device",
        ),
    ]

    validator = OntologyValidator()

    # Act
    validator.validate(equipment_types)

    # Assert
    assert True


def test_validator_rejects_unknown_parent():
    """
    Il validator deve rifiutare
    un riferimento parent inesistente.
    """

    # Arrange
    equipment_types = [
        create_equipment_type(
            equipment_id="breaker",
            name="Circuit Breaker",
            parent="unknown_parent",
        ),
    ]

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(InvalidEquipmentDefinitionError):
        validator.validate(equipment_types)


def test_validator_accepts_relation_with_existing_target():
    """
    Il validator deve accettare relazioni
    verso EquipmentType esistenti.
    """

    # Arrange
    relay = create_equipment_type(
        equipment_id="relay",
        name="Protection Relay",
    )

    breaker = create_equipment_type(
        equipment_id="breaker",
        name="Circuit Breaker",
        relations=(
            EquipmentRelation(
                relation_type="protected_by",
                target_types=("relay",),
            ),
        ),
    )

    validator = OntologyValidator()

    # Act
    validator.validate([breaker, relay])

    # Assert
    assert True


def test_validator_rejects_relation_with_unknown_target():
    """
    Il validator deve rifiutare relazioni
    verso EquipmentType inesistenti.
    """

    # Arrange
    breaker = create_equipment_type(
        equipment_id="breaker",
        name="Circuit Breaker",
        relations=(
            EquipmentRelation(
                relation_type="protected_by",
                target_types=("unknown_relay",),
            ),
        ),
    )

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(UnknownRelationError):
        validator.validate([breaker])


def test_validator_rejects_empty_relation_type():
    """
    Il tipo di relazione non può essere vuoto.
    """

    # Arrange
    relay = create_equipment_type(
        equipment_id="relay",
        name="Protection Relay",
    )

    breaker = create_equipment_type(
        equipment_id="breaker",
        name="Circuit Breaker",
        relations=(
            EquipmentRelation(
                relation_type="",
                target_types=("relay",),
            ),
        ),
    )

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(InvalidEquipmentDefinitionError):
        validator.validate([breaker, relay])


def test_validator_rejects_relation_without_targets():
    """
    Una relazione deve dichiarare
    almeno un target type.
    """

    # Arrange
    breaker = create_equipment_type(
        equipment_id="breaker",
        name="Circuit Breaker",
        relations=(
            EquipmentRelation(
                relation_type="protected_by",
                target_types=(),
            ),
        ),
    )

    validator = OntologyValidator()

    # Act / Assert
    with pytest.raises(InvalidEquipmentDefinitionError):
        validator.validate([breaker])