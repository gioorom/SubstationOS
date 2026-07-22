"""
Eccezioni del dominio Electrical Ontology.

Questo modulo definisce tutte le eccezioni utilizzate
dall'Ontology Engine.

Nessun componente del dominio dovrebbe mai sollevare
ValueError, RuntimeError o FileNotFoundError direttamente.
"""


class OntologyError(Exception):
    """
    Classe base di tutte le eccezioni dell'ontologia.
    """


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------


class OntologyLoadError(OntologyError):
    """
    Errore durante il caricamento dell'ontologia.
    """


class OntologyFileNotFoundError(OntologyLoadError):
    """
    File YAML non trovato.
    """


class InvalidOntologySchemaError(OntologyLoadError):
    """
    Il file YAML non rispetta lo schema previsto.
    """


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


class OntologyValidationError(OntologyError):
    """
    Errore di validazione dell'ontologia.
    """


class DuplicateEquipmentTypeError(OntologyValidationError):
    """
    Sono presenti due EquipmentType con lo stesso id.
    """


class InvalidEquipmentDefinitionError(OntologyValidationError):
    """
    Definizione di EquipmentType non valida.
    """


class UnknownCategoryError(OntologyValidationError):
    """
    Categoria sconosciuta.
    """


class UnknownRelationError(OntologyValidationError):
    """
    Relazione non riconosciuta.
    """


# ---------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------


class EquipmentTypeNotFoundError(OntologyError):
    """
    EquipmentType richiesto ma inesistente.
    """

    def __init__(self, equipment_type_id: str):
        self.equipment_type_id = equipment_type_id

        super().__init__(
            f"Equipment type '{equipment_type_id}' not found."
        )


class AttributeNotFoundError(OntologyError):
    """
    Attributo richiesto ma inesistente.
    """

    def __init__(
        self,
        equipment_type: str,
        attribute: str,
    ):
        self.equipment_type = equipment_type
        self.attribute = attribute

        super().__init__(
            f"Attribute '{attribute}' not found "
            f"for equipment '{equipment_type}'."
        )


class RelationNotSupportedError(OntologyError):
    """
    Relazione non supportata dal tipo di apparecchiatura.
    """

    def __init__(
        self,
        equipment_type: str,
        relation: str,
    ):
        self.equipment_type = equipment_type
        self.relation = relation

        super().__init__(
            f"Relation '{relation}' "
            f"is not supported by '{equipment_type}'."
        )