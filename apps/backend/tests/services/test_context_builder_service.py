from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.context_builder.context_builder_exceptions import (
    InvalidProjectIdError,
)
from app.services import context_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    results_for,
)

PROJECT_ID = 3
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _assets(count: int):
    """``count`` distinct approved governed assets, one per governed
    query - which is what several designations legitimately produce."""

    return results_for(
        tuple(
            asset_item(
                f"node-c-{index:03d}",
                f"C-{index:03d}",
                statement_key=f"statement-{index}",
                project_id=PROJECT_ID,
            )
            for index in range(count)
        ),
        project_id=PROJECT_ID,
    )


def test_build_context_package_assembles_a_full_package_within_budget():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=_assets(3), now=NOW
    )
    assert result.project_id == PROJECT_ID
    assert result.package.project_id == PROJECT_ID
    assert len(result.package.selected_items) == 3
    assert result.package.budget.exceeded is False


def test_build_context_package_reports_budget_overflow():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=_assets(5),
        max_items=2,
        now=NOW,
    )
    assert len(result.package.selected_items) == 2
    assert result.package.statistics.discarded_item_count == 3
    assert result.package.budget.exceeded is True


def test_build_context_package_on_an_empty_collection_is_a_valid_empty_package():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=_assets(0), now=NOW
    )
    assert result.package.selected_items == ()
    assert result.package.statistics.selected_item_count == 0
    assert result.package.warnings == ()


def test_build_context_package_on_a_full_collection_selects_everything_within_default_budget():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=_assets(10), now=NOW
    )
    assert len(result.package.selected_items) == 10
    assert result.package.budget.exceeded is False


def test_build_context_package_rejects_an_invalid_project_id():
    with pytest.raises(InvalidProjectIdError):
        context_builder_service.build_context_package(
            project_id=0, results=_assets(1), now=NOW
        )


def test_build_context_package_is_deterministic():
    collection = _assets(6)
    first = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=collection, now=NOW
    )
    second = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=collection, now=NOW
    )
    first_ids = [item.item_id for item in first.package.selected_items]
    second_ids = [item.item_id for item in second.package.selected_items]
    assert first_ids == second_ids
    assert first.package.coverage == second.package.coverage


def test_build_context_package_echoes_metadata_entries_and_retrieval_versions():
    """
    The retrieval versions come from the governed results themselves,
    never from an argument: which normalization folded a designation is
    a fact about the retrieval that ran, and a caller able to assert it
    could make a context claim rules it was not built under.
    """

    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=_assets(1),
        metadata_entries=(("subject", "C-000"),),
        now=NOW,
    )
    metadata = result.package.metadata

    assert metadata.retrieval_matching_policy_version == "1.0"
    assert metadata.retrieval_normalization_version == "1.0"
    assert metadata.entries[0].key == "subject"
    assert metadata.entries[0].value == "C-000"
