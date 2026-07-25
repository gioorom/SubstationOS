from __future__ import annotations

import pytest

from app.domain.canonicalization.canonicalization_exceptions import (
    UnknownCanonicalEntityTypeError,
    UnknownCanonicalPredicateError,
    UnrecognizedEntityReferenceError,
)
from app.domain.canonicalization.canonicalization_normalizer import (
    normalize_attribute_name,
    normalize_entity_reference,
    normalize_predicate,
    normalize_value,
)


@pytest.mark.parametrize(
    "raw",
    ["Cable 295", "C-295", "C295"],
)
def test_normalize_entity_reference_folds_cable_synonyms(
    raw: str,
) -> None:
    reference = normalize_entity_reference(raw)

    assert reference.entity_type == "CABLE"
    assert reference.canonical_id == "C-295"
    assert reference.value == "CABLE:C-295"


@pytest.mark.parametrize(
    "raw",
    ["TR2", "TR-02", "Transformer 2"],
)
def test_normalize_entity_reference_folds_transformer_synonyms(
    raw: str,
) -> None:
    reference = normalize_entity_reference(raw)

    assert reference.entity_type == "TRANSFORMER"
    assert reference.canonical_id == "TR-02"
    assert reference.value == "TRANSFORMER:TR-02"


def test_normalize_entity_reference_rejects_an_unrecognized_shape() -> (
    None
):
    with pytest.raises(UnrecognizedEntityReferenceError):
        normalize_entity_reference("Main Busbar Room")


def test_normalize_entity_reference_rejects_blank_input() -> None:
    with pytest.raises(UnrecognizedEntityReferenceError):
        normalize_entity_reference("   ")


def test_normalize_entity_reference_rejects_an_unknown_type_prefix() -> (
    None
):
    with pytest.raises(UnknownCanonicalEntityTypeError):
        normalize_entity_reference("Widget 12")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("feeds", "FEEDS"),
        ("supplies", "FEEDS"),
        ("energizes", "FEEDS"),
        ("installed_in", "LOCATED_IN"),
        ("located_in", "LOCATED_IN"),
        ("Installed In", "LOCATED_IN"),
    ],
)
def test_normalize_predicate_folds_synonyms(
    raw: str,
    expected: str,
) -> None:
    assert normalize_predicate(raw).value == expected


def test_normalize_predicate_rejects_an_unknown_verb() -> None:
    with pytest.raises(UnknownCanonicalPredicateError):
        normalize_predicate("orbits")


def test_normalize_attribute_name_formats_as_snake_case() -> None:
    assert (
        normalize_attribute_name("Rated Voltage").value == "rated_voltage"
    )


def test_normalize_value_trims_whitespace() -> None:
    assert normalize_value("  132kV  ").value == "132kV"
