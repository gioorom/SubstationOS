from __future__ import annotations

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)


def test_engineering_index_entry_kind_covers_the_architecture_inventory() -> (
    None
):
    values = {kind.value for kind in EngineeringIndexEntryKind}

    assert values == {
        "equipment",
        "signal",
        "cable",
        "cabinet_or_frame",
        "protection",
        "drawing",
        "function",
        "cross_reference",
    }
