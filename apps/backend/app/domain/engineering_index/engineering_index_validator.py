from __future__ import annotations

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    InvalidIndexEntryIdentifierError,
    InvalidIndexEntryLocatorError,
    InvalidIndexEntryPageError,
    UnsupportedIndexEntryKindError,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)


class EngineeringIndexValidator:
    """
    Stateless validation rules for Engineering Index entries, shared by
    the factory (at registration) and any future caller constructing an
    entry directly.
    """

    @staticmethod
    def validate_identifier(identifier: str) -> None:
        if not identifier or not identifier.strip():
            raise InvalidIndexEntryIdentifierError(identifier)

    @staticmethod
    def validate_page(page: int | None) -> None:
        if page is not None and page < 1:
            raise InvalidIndexEntryPageError(page)

    @staticmethod
    def validate_kind(kind: EngineeringIndexEntryKind) -> None:
        if kind not in EngineeringIndexEntryKind:
            raise UnsupportedIndexEntryKindError(str(kind))

    @staticmethod
    def validate_locator(locator: IndexEntryLocator) -> None:
        if locator.kind is IndexEntryLocatorKind.PAGE:
            if locator.value is None:
                return

            try:
                page = int(locator.value)
            except ValueError as error:
                raise InvalidIndexEntryLocatorError(
                    locator.kind,
                    locator.value,
                ) from error

            EngineeringIndexValidator.validate_page(page)
        elif locator.value is not None and not locator.value.strip():
            raise InvalidIndexEntryLocatorError(
                locator.kind,
                locator.value,
            )
