from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.prompt_builder.prompt_builder_exceptions import (
    InvalidProjectIdError,
    ProjectIdMismatchError,
)
from app.domain.prompt_builder.prompt_composition import (
    PROMPT_SECTION_ORDER,
)
from app.services import context_builder_service, prompt_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    results_for,
)

PROJECT_ID = 4
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


def _context_package(count: int, **overrides):
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, results=_assets(count), now=NOW, **overrides
    )
    return result.package


def test_build_prompt_package_assembles_a_full_package():
    package = _context_package(3)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert result.project_id == PROJECT_ID
    assert result.package.project_id == PROJECT_ID
    assert result.validation.valid is True


def test_build_prompt_package_on_an_empty_context_package_is_valid():
    package = _context_package(0)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert result.package.statistics.knowledge_item_count == 0
    assert result.validation.valid is True
    disabled = {s.section_type for s in result.package.sections if not s.enabled}
    assert len(disabled) >= 2  # SELECTED_KNOWLEDGE and EVIDENCE_REFERENCES


def test_build_prompt_package_rejects_an_invalid_project_id():
    package = _context_package(1)
    with pytest.raises(InvalidProjectIdError):
        prompt_builder_service.build_prompt_package(
            project_id=0, context_package=package, now=NOW
        )


def test_build_prompt_package_rejects_a_mismatched_project_id():
    package = _context_package(1)
    with pytest.raises(ProjectIdMismatchError):
        prompt_builder_service.build_prompt_package(
            project_id=PROJECT_ID + 1, context_package=package, now=NOW
        )


def test_build_prompt_package_always_has_every_section_regardless_of_budget():
    package = _context_package(5, max_items=1)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert len(result.package.sections) == len(PROMPT_SECTION_ORDER)
    assert result.validation.valid is True


def test_build_prompt_package_is_deterministic():
    package = _context_package(4)
    first = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    second = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert first.package == second.package
