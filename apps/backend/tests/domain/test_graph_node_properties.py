from __future__ import annotations

from app.domain.project_knowledge_graph.graph_node_models import (
    GraphNodeProperties,
)


def test_merged_with_adds_a_new_key() -> None:
    properties = GraphNodeProperties()

    merged = properties.merged_with("rated_voltage", "132kV")

    assert merged.as_dict() == {"rated_voltage": "132kV"}


def test_merged_with_overwrites_an_existing_key() -> None:
    properties = GraphNodeProperties(
        values=(("rated_voltage", "132kV"),)
    )

    merged = properties.merged_with("rated_voltage", "150kV")

    assert merged.as_dict() == {"rated_voltage": "150kV"}


def test_merged_with_preserves_unrelated_keys() -> None:
    properties = GraphNodeProperties(
        values=(("rated_voltage", "132kV"),)
    )

    merged = properties.merged_with("rated_current", "630A")

    assert merged.as_dict() == {
        "rated_voltage": "132kV",
        "rated_current": "630A",
    }


def test_merged_with_never_produces_duplicate_keys() -> None:
    properties = GraphNodeProperties()

    merged = properties.merged_with("a", "1").merged_with("a", "2")

    keys = [key for key, _ in merged.values]
    assert keys.count("a") == 1
    assert merged.as_dict()["a"] == "2"


def test_original_properties_are_unchanged() -> None:
    properties = GraphNodeProperties()

    properties.merged_with("a", "1")

    assert properties.as_dict() == {}
