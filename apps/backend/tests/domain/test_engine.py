from pathlib import Path

from app.domain.ontology.engine import OntologyEngine
from app.domain.ontology.models import (
    EquipmentCategory,
    Ontology,
)
from app.infrastructure.ontology.filesystem_repository import (
    FilesystemEquipmentTypeRepository,
)


ONTOLOGY_PATH = Path("app/domain/ontology/equipment_types")


def create_engine() -> OntologyEngine:
    """
    Restituisce un OntologyEngine configurato
    per utilizzare il dataset ufficiale.
    """

    repository = FilesystemEquipmentTypeRepository(
        ONTOLOGY_PATH
    )

    return OntologyEngine(repository)


def test_engine_returns_ontology():
    """
    Il metodo load() deve restituire
    un oggetto Ontology.
    """

    # Arrange
    engine = create_engine()

    # Act
    ontology = engine.load()

    # Assert
    assert isinstance(ontology, Ontology)


def test_engine_loads_all_equipment():
    """
    L'ontologia deve contenere almeno
    i componenti fondamentali.
    """

    # Arrange
    engine = create_engine()

    # Act
    ontology = engine.load()

    # Assert
    assert len(ontology) >= 9


def test_engine_can_find_breaker():
    """
    Il breaker deve essere recuperabile
    tramite il metodo get().
    """

    # Arrange
    engine = create_engine()

    # Act
    ontology = engine.load()

    breaker = ontology.get("breaker")

    # Assert
    assert breaker is not None
    assert breaker.name == "Circuit Breaker"


def test_engine_can_find_alias():
    """
    Gli alias devono essere ricercabili.
    """

    # Arrange
    engine = create_engine()

    # Act
    ontology = engine.load()

    equipment = ontology.find_by_alias("CB")

    # Assert
    assert equipment is not None
    assert equipment.id == "breaker"


def test_engine_category_filter():
    """
    Deve essere possibile filtrare
    per categoria.
    """

    # Arrange
    engine = create_engine()

    # Act
    ontology = engine.load()

    primary = ontology.get_by_category(
        EquipmentCategory.PRIMARY_EQUIPMENT
    )

    # Assert
    assert len(primary) > 0