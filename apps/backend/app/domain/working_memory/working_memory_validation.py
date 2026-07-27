"""
Validation for Working Memory (Milestone 21). Proves, after building,
that a ``WorkingMemory`` satisfies every structural invariant this
milestone requires: entries are sequenced contiguously from zero, each
entry's priority/lifetime matches the fixed policy assignment for its
type, only ``RECENT_ENGINEERING_RESPONSE`` entries carry an
``engineering_response`` reference, metadata is complete, and every
statistic/version field is internally consistent. **No semantic
validation** - never whether an entry's content is engineering-correct,
only whether the structure is well-formed. Never causes building to
raise - Working Memory always produces a structurally valid object by
construction; this is an inspectable, testable proof of that, not a
gate a caller must pass.
"""

from __future__ import annotations

from app.domain.working_memory.working_memory_models import (
    WorkingMemory,
    WorkingMemoryEntryType,
    WorkingMemoryValidationResult,
)
from app.domain.working_memory.working_memory_policy import (
    ENTRY_LIFETIME,
    ENTRY_PRIORITY,
)


def validate_working_memory(
    working_memory: WorkingMemory,
) -> WorkingMemoryValidationResult:
    errors: list[str] = []

    if working_memory.project_id <= 0:
        errors.append("project_id is not positive.")

    entries = working_memory.entries
    for index, entry in enumerate(entries):
        if entry.sequence != index:
            errors.append(
                f"Entry at position {index} does not have the expected "
                "sequence."
            )

        expected_priority = ENTRY_PRIORITY.get(entry.entry_type)
        if expected_priority is not None and entry.priority != expected_priority:
            errors.append(
                f"Entry at position {index} has a priority inconsistent "
                "with policy for its type."
            )

        expected_lifetime = ENTRY_LIFETIME.get(entry.entry_type)
        if expected_lifetime is not None and entry.lifetime != expected_lifetime:
            errors.append(
                f"Entry at position {index} has a lifetime inconsistent "
                "with policy for its type."
            )

        if (
            entry.entry_type is WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
            and entry.engineering_response is None
        ):
            errors.append(
                f"Entry at position {index} is a RECENT_ENGINEERING_RESPONSE "
                "entry with no engineering_response reference."
            )
        if (
            entry.entry_type is not WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
            and entry.engineering_response is not None
        ):
            errors.append(
                f"Entry at position {index} carries an engineering_response "
                "reference but is not a RECENT_ENGINEERING_RESPONSE entry."
            )

    metadata = working_memory.metadata
    if (
        not metadata.working_memory_version
        or not metadata.working_memory_policy_version
        or not metadata.package_version
        or metadata.project_id <= 0
        or not metadata.conversation_id
        or not metadata.session_id
        or metadata.built_at is None
    ):
        errors.append("Metadata is incomplete.")

    version = working_memory.version
    if (
        not version.working_memory_version
        or not version.working_memory_policy_version
        or not version.package_version
    ):
        errors.append("Version fields are incomplete.")
    elif (
        version.working_memory_version != metadata.working_memory_version
        or version.working_memory_policy_version
        != metadata.working_memory_policy_version
        or version.package_version != metadata.package_version
    ):
        errors.append("Version fields are inconsistent with metadata.")

    statistics = working_memory.statistics
    if statistics.entry_count != len(entries):
        errors.append(
            "Statistics entry_count is inconsistent with the assembled "
            "entries."
        )

    def _count(entry_type: WorkingMemoryEntryType) -> int:
        return sum(1 for entry in entries if entry.entry_type is entry_type)

    if statistics.open_question_count != _count(
        WorkingMemoryEntryType.OPEN_QUESTION
    ):
        errors.append(
            "Statistics open_question_count is inconsistent with the "
            "assembled entries."
        )
    if statistics.assumption_count != _count(WorkingMemoryEntryType.ASSUMPTION):
        errors.append(
            "Statistics assumption_count is inconsistent with the "
            "assembled entries."
        )
    if statistics.constraint_count != _count(WorkingMemoryEntryType.CONSTRAINT):
        errors.append(
            "Statistics constraint_count is inconsistent with the "
            "assembled entries."
        )
    if statistics.active_reference_count != _count(
        WorkingMemoryEntryType.ACTIVE_REFERENCE
    ):
        errors.append(
            "Statistics active_reference_count is inconsistent with the "
            "assembled entries."
        )
    if statistics.recent_engineering_response_count != _count(
        WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
    ):
        errors.append(
            "Statistics recent_engineering_response_count is inconsistent "
            "with the assembled entries."
        )

    return WorkingMemoryValidationResult(valid=not errors, errors=tuple(errors))


class WorkingMemoryValidator:
    """A thin, named façade over ``validate_working_memory`` - kept only
    for the same reason every sibling bounded context's own validator
    class is."""

    @staticmethod
    def validate(working_memory: WorkingMemory) -> WorkingMemoryValidationResult:
        return validate_working_memory(working_memory)
