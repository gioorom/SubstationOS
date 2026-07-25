from __future__ import annotations

import pytest

from app.domain.project_knowledge_graph.graph_entity_id_codec import (
    encode_graph_entity_id,
    parse_graph_entity_id,
)
from app.domain.project_knowledge_graph.knowledge_graph_exceptions import (
    InvalidGraphEntityIdError,
)


def test_parse_splits_type_and_canonical_id() -> None:
    entity_id = parse_graph_entity_id(10, "CABLE:C-295")

    assert entity_id.project_id == 10
    assert entity_id.entity_type == "CABLE"
    assert entity_id.canonical_id == "C-295"


def test_encode_round_trips_with_parse() -> None:
    entity_id = parse_graph_entity_id(10, "CABLE:C-295")

    assert encode_graph_entity_id(entity_id) == "CABLE:C-295"


@pytest.mark.parametrize("raw", ["CABLE", "CABLE:", ":C-295", ""])
def test_parse_rejects_malformed_input(raw: str) -> None:
    with pytest.raises(InvalidGraphEntityIdError):
        parse_graph_entity_id(10, raw)
