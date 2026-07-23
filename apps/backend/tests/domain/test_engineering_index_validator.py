from __future__ import annotations

import pytest

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    InvalidIndexEntryIdentifierError,
    InvalidIndexEntryLocatorError,
    InvalidIndexEntryPageError,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_validator import (
    EngineeringIndexValidator,
)


@pytest.mark.parametrize("identifier", ["", "   ", "\t"])
def test_validate_identifier_rejects_blank_values(identifier: str) -> None:
    with pytest.raises(InvalidIndexEntryIdentifierError):
        EngineeringIndexValidator.validate_identifier(identifier)


def test_validate_identifier_accepts_a_real_identifier() -> None:
    EngineeringIndexValidator.validate_identifier("T1")


def test_validate_page_accepts_none() -> None:
    EngineeringIndexValidator.validate_page(None)


def test_validate_page_accepts_a_positive_page() -> None:
    EngineeringIndexValidator.validate_page(1)


@pytest.mark.parametrize("page", [0, -1, -100])
def test_validate_page_rejects_non_positive_pages(page: int) -> None:
    with pytest.raises(InvalidIndexEntryPageError):
        EngineeringIndexValidator.validate_page(page)


def test_validate_kind_accepts_every_known_kind() -> None:
    for kind in EngineeringIndexEntryKind:
        EngineeringIndexValidator.validate_kind(kind)


def test_validate_locator_accepts_a_page_locator_with_no_value() -> None:
    EngineeringIndexValidator.validate_locator(
        IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value=None)
    )


def test_validate_locator_accepts_a_positive_page_value() -> None:
    EngineeringIndexValidator.validate_locator(
        IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value="3")
    )


def test_validate_locator_rejects_a_non_numeric_page_value() -> None:
    with pytest.raises(InvalidIndexEntryLocatorError):
        EngineeringIndexValidator.validate_locator(
            IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE,
                value="not-a-number",
            )
        )


def test_validate_locator_rejects_a_non_positive_page_value() -> None:
    with pytest.raises(InvalidIndexEntryPageError):
        EngineeringIndexValidator.validate_locator(
            IndexEntryLocator(kind=IndexEntryLocatorKind.PAGE, value="0")
        )


@pytest.mark.parametrize(
    "kind",
    [
        IndexEntryLocatorKind.SHEET,
        IndexEntryLocatorKind.CELL_RANGE,
        IndexEntryLocatorKind.DRAWING_LAYOUT,
        IndexEntryLocatorKind.REGION,
        IndexEntryLocatorKind.OTHER,
    ],
)
def test_validate_locator_accepts_non_page_kinds_with_a_value(
    kind: IndexEntryLocatorKind,
) -> None:
    EngineeringIndexValidator.validate_locator(
        IndexEntryLocator(kind=kind, value="B12:C15")
    )


@pytest.mark.parametrize(
    "kind",
    [
        IndexEntryLocatorKind.SHEET,
        IndexEntryLocatorKind.CELL_RANGE,
        IndexEntryLocatorKind.DRAWING_LAYOUT,
        IndexEntryLocatorKind.REGION,
        IndexEntryLocatorKind.OTHER,
    ],
)
def test_validate_locator_accepts_non_page_kinds_with_no_value(
    kind: IndexEntryLocatorKind,
) -> None:
    EngineeringIndexValidator.validate_locator(
        IndexEntryLocator(kind=kind, value=None)
    )


def test_validate_locator_rejects_a_blank_value_for_a_non_page_kind() -> (
    None
):
    with pytest.raises(InvalidIndexEntryLocatorError):
        EngineeringIndexValidator.validate_locator(
            IndexEntryLocator(kind=IndexEntryLocatorKind.SHEET, value="  ")
        )
