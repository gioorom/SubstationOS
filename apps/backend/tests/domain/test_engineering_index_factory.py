from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    InvalidIndexEntryIdentifierError,
    InvalidIndexEntryLocatorError,
    InvalidIndexEntryPageError,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def test_create_builds_an_unpersisted_entry() -> None:
    entry = EngineeringIndexEntryFactory.create(
        project_id=1,
        document_id=2,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        created_at=CREATED_AT,
    )

    assert entry.id is None
    assert entry.project_id == 1
    assert entry.document_id == 2
    assert entry.kind is EngineeringIndexEntryKind.EQUIPMENT
    assert entry.identifier == "T1"
    assert entry.page is None
    assert entry.label is None
    assert entry.created_at == CREATED_AT


def test_create_accepts_an_optional_page_and_label() -> None:
    entry = EngineeringIndexEntryFactory.create(
        project_id=1,
        document_id=2,
        kind=EngineeringIndexEntryKind.CABLE,
        identifier="W-152",
        created_at=CREATED_AT,
        page=4,
        label="Cable schedule row 12",
    )

    assert entry.page == 4
    assert entry.label == "Cable schedule row 12"


def test_create_rejects_a_blank_identifier() -> None:
    with pytest.raises(InvalidIndexEntryIdentifierError):
        EngineeringIndexEntryFactory.create(
            project_id=1,
            document_id=2,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="   ",
            created_at=CREATED_AT,
        )


def test_create_rejects_a_non_positive_page() -> None:
    with pytest.raises(InvalidIndexEntryPageError):
        EngineeringIndexEntryFactory.create(
            project_id=1,
            document_id=2,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
            page=0,
        )


def test_create_defaults_to_a_page_locator_with_no_value() -> None:
    entry = EngineeringIndexEntryFactory.create(
        project_id=1,
        document_id=2,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        created_at=CREATED_AT,
    )

    assert entry.locator.kind is IndexEntryLocatorKind.PAGE
    assert entry.locator.value is None
    assert entry.page is None


def test_create_from_a_page_builds_a_page_locator() -> None:
    entry = EngineeringIndexEntryFactory.create(
        project_id=1,
        document_id=2,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        created_at=CREATED_AT,
        page=4,
    )

    assert entry.locator == IndexEntryLocator(
        kind=IndexEntryLocatorKind.PAGE,
        value="4",
    )
    assert entry.page == 4


def test_create_accepts_a_non_page_locator_for_a_spreadsheet_cell_range() -> (
    None
):
    entry = EngineeringIndexEntryFactory.create(
        project_id=1,
        document_id=2,
        kind=EngineeringIndexEntryKind.CABLE,
        identifier="W-152",
        created_at=CREATED_AT,
        locator=IndexEntryLocator(
            kind=IndexEntryLocatorKind.CELL_RANGE,
            value="B12:C15",
        ),
    )

    assert entry.locator_kind is IndexEntryLocatorKind.CELL_RANGE
    assert entry.locator_value == "B12:C15"
    assert entry.page is None


def test_create_rejects_an_invalid_locator() -> None:
    with pytest.raises(InvalidIndexEntryLocatorError):
        EngineeringIndexEntryFactory.create(
            project_id=1,
            document_id=2,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
            locator=IndexEntryLocator(
                kind=IndexEntryLocatorKind.SHEET,
                value="   ",
            ),
        )
