from __future__ import annotations

from app.domain.context_builder.context_builder_exceptions import (
    BlankMetadataEntryKeyError,
    InvalidBudgetPolicyValueError,
    InvalidProjectIdError,
)

MIN_MAX_CANDIDATES = 1
MAX_MAX_CANDIDATES = 1000

MIN_PER_KIND_LIMIT = 0
MAX_PER_KIND_LIMIT = 1000

MIN_METADATA_ENTRIES_LIMIT = 0
MAX_METADATA_ENTRIES_LIMIT = 500

MIN_WARNINGS_LIMIT = 0
MAX_WARNINGS_LIMIT = 500


class ContextBuilderValidator:
    """Stateless validation rules for Context Builder, shared by
    ``ContextBuildRequestFactory``. Deliberately does not reject a
    ``KnowledgeCandidateCollection`` for being larger than the budget,
    or empty - budget overflow is routine, expected, warned-about
    behavior (see ``candidate_selection.py``/``context_warnings.py``),
    never a validation error."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_budget_policy(
        *,
        max_candidates: int,
        max_entities: int,
        max_relationships: int,
        max_attributes: int,
        max_metadata_entries: int,
        max_warnings: int,
    ) -> None:
        _validate_bound(
            "max_candidates",
            max_candidates,
            MIN_MAX_CANDIDATES,
            MAX_MAX_CANDIDATES,
        )
        _validate_bound(
            "max_entities", max_entities, MIN_PER_KIND_LIMIT, MAX_PER_KIND_LIMIT
        )
        _validate_bound(
            "max_relationships",
            max_relationships,
            MIN_PER_KIND_LIMIT,
            MAX_PER_KIND_LIMIT,
        )
        _validate_bound(
            "max_attributes",
            max_attributes,
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
