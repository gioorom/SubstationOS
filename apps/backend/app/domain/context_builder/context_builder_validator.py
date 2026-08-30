from __future__ import annotations

from app.domain.context_builder.context_builder_exceptions import (
    BlankMetadataEntryKeyError,
    InvalidBudgetPolicyValueError,
    InvalidProjectIdError,
)

MIN_MAX_ITEMS = 1
MAX_MAX_ITEMS = 1000

MIN_PER_KIND_LIMIT = 0
MAX_PER_KIND_LIMIT = 1000

MIN_METADATA_ENTRIES_LIMIT = 0
MAX_METADATA_ENTRIES_LIMIT = 500

MIN_WARNINGS_LIMIT = 0
MAX_WARNINGS_LIMIT = 500


class ContextBuilderValidator:
    """
    Stateless validation rules for Governed Context Assembly, shared by
    ``ContextBuildRequestFactory``.

    Deliberately does **not** reject a set of governed results for being
    larger than the budget, or empty: budget overflow is routine,
    expected, warned-about behaviour (see ``item_selection.py`` and
    ``context_warnings.py``), and an empty governed result is a real
    engineering answer - the graph holds nothing approved about what was
    asked - never a validation error.
    """

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_budget_policy(
        *,
        max_items: int,
        max_assets: int,
        max_quantities: int,
        max_relationships: int,
        max_locations: int,
        max_metadata_entries: int,
        max_warnings: int,
    ) -> None:
        _validate_bound("max_items", max_items, MIN_MAX_ITEMS, MAX_MAX_ITEMS)
        _validate_bound(
            "max_assets", max_assets, MIN_PER_KIND_LIMIT, MAX_PER_KIND_LIMIT
        )
        _validate_bound(
            "max_quantities",
            max_quantities,
            MIN_PER_KIND_LIMIT,
            MAX_PER_KIND_LIMIT,
        )
        _validate_bound(
            "max_relationships",
            max_relationships,
            MIN_PER_KIND_LIMIT,
            MAX_PER_KIND_LIMIT,
        )
        _validate_bound(
            "max_metadata_entries",
            max_metadata_entries,
            MIN_METADATA_ENTRIES_LIMIT,
            MAX_METADATA_ENTRIES_LIMIT,
        )
        _validate_bound(
            "max_warnings",
            max_warnings,
            MIN_WARNINGS_LIMIT,
            MAX_WARNINGS_LIMIT,
        )

    @staticmethod
    def validate_metadata_entries(
        entries: tuple[tuple[str, str], ...],
    ) -> None:
        for key, _value in entries:
            if not key or not key.strip():
                raise BlankMetadataEntryKeyError()


def _validate_bound(
    field_name: str, value: int, minimum: int, maximum: int
) -> None:
    if not (minimum <= value <= maximum):
        raise InvalidBudgetPolicyValueError(
            field_name, value, minimum, maximum
        )
