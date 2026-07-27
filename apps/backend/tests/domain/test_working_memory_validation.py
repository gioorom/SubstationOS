from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.conversation.conversation_models import ConversationId
from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionId,
)
from app.domain.working_memory.working_memory_models import (
    WorkingMemory,
    WorkingMemoryEntry,
    WorkingMemoryEntryType,
    WorkingMemoryId,
    WorkingMemoryLifetime,
    WorkingMemoryMetadata,
    WorkingMemoryPriority,
    WorkingMemorySource,
    WorkingMemoryStatistics,
    WorkingMemoryVersion,
)
from app.domain.working_memory.working_memory_validation import (
    WorkingMemoryValidator,
    validate_working_memory,
)

NOW = datetime(2026, 1, 1, 13, 0, 0)


def _entry(**overrides) -> WorkingMemoryEntry:
    defaults = dict(
        entry_id="0",
        entry_type=WorkingMemoryEntryType.OPEN_QUESTION,
        content="What does C-295 feed?",
        source=WorkingMemorySource.CONVERSATION_MESSAGE,
        priority=WorkingMemoryPriority.HIGH,
        lifetime=WorkingMemoryLifetime.TURN,
        sequence=0,
        created_at=NOW,
        engineering_response=None,
    )
    defaults.update(overrides)
    return WorkingMemoryEntry(**defaults)


def _working_memory(**overrides) -> WorkingMemory:
    entries = overrides.pop("entries", ())

    defaults = dict(
        working_memory_id=WorkingMemoryId(value="conv-1:working-memory"),
        conversation_id=ConversationId(value="conv-1"),
        session_id=EngineeringSessionId(value="sess-1"),
        project_id=1,
        entries=entries,
        metadata=WorkingMemoryMetadata(
            working_memory_version="1.0",
            working_memory_policy_version="1.0",
            project_id=1,
            conversation_id="conv-1",
            session_id="sess-1",
            built_at=NOW,
            package_version="1.0",
        ),
        statistics=WorkingMemoryStatistics(
            entry_count=len(entries),
            open_question_count=sum(
                1
                for e in entries
                if e.entry_type is WorkingMemoryEntryType.OPEN_QUESTION
            ),
            assumption_count=0,
            constraint_count=0,
            active_reference_count=0,
            recent_engineering_response_count=0,
        ),
        version=WorkingMemoryVersion(
            working_memory_version="1.0",
            working_memory_policy_version="1.0",
            package_version="1.0",
        ),
    )
    defaults.update(overrides)
    return WorkingMemory(**defaults)


def test_an_empty_working_memory_is_valid() -> None:
    result = validate_working_memory(_working_memory())

    assert result.valid is True
    assert result.errors == ()


def test_a_working_memory_with_one_valid_entry_is_valid() -> None:
    wm = _working_memory(entries=(_entry(),))

    result = validate_working_memory(wm)

    assert result.valid is True


def test_the_validator_class_delegates_to_the_same_function() -> None:
    wm = _working_memory()

    assert WorkingMemoryValidator.validate(wm) == validate_working_memory(wm)


def test_a_non_positive_project_id_is_rejected() -> None:
    wm = replace(_working_memory(), project_id=0)

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any("project_id is not positive" in e for e in result.errors)


def test_out_of_sequence_entries_are_rejected() -> None:
    entry = _entry(sequence=5)
    wm = _working_memory(entries=(entry,))

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any("expected sequence" in e for e in result.errors)


def test_a_priority_inconsistent_with_policy_is_rejected() -> None:
    entry = _entry(priority=WorkingMemoryPriority.LOW)
    wm = _working_memory(entries=(entry,))

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any("priority inconsistent" in e for e in result.errors)


def test_a_lifetime_inconsistent_with_policy_is_rejected() -> None:
    entry = _entry(lifetime=WorkingMemoryLifetime.SESSION)
    wm = _working_memory(entries=(entry,))

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any("lifetime inconsistent" in e for e in result.errors)


def test_a_non_response_entry_type_carrying_an_engineering_response_is_rejected() -> (
    None
):
    entry = _entry(engineering_response=object())
    wm = _working_memory(entries=(entry,))

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any(
        "carries an engineering_response reference but is not" in e
        for e in result.errors
    )


def test_a_recent_response_entry_missing_its_reference_is_rejected() -> None:
    entry = _entry(
        entry_type=WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE,
        content="status=complete",
        source=WorkingMemorySource.ENGINEERING_RESPONSE,
        priority=WorkingMemoryPriority.LOW,
        lifetime=WorkingMemoryLifetime.CONVERSATION,
        engineering_response=None,
    )
    wm = _working_memory(entries=(entry,))

    result = validate_working_memory(wm)

    assert result.valid is False
    assert any(
        "RECENT_ENGINEERING_RESPONSE entry with no engineering_response" in e
        for e in result.errors
    )


def test_incomplete_metadata_is_rejected() -> None:
    wm = _working_memory()
    broken_metadata = replace(wm.metadata, working_memory_version="")
    broken = replace(wm, metadata=broken_metadata)

    result = validate_working_memory(broken)

    assert result.valid is False
    assert any("Metadata is incomplete" in e for e in result.errors)


def test_version_inconsistent_with_metadata_is_rejected() -> None:
    wm = _working_memory()
    broken_version = replace(wm.version, working_memory_version="9.9")
    broken = replace(wm, version=broken_version)

    result = validate_working_memory(broken)

    assert result.valid is False
    assert any("inconsistent with metadata" in e for e in result.errors)


def test_entry_count_inconsistency_is_rejected() -> None:
    wm = _working_memory(entries=(_entry(),))
    broken_statistics = replace(wm.statistics, entry_count=99)
    broken = replace(wm, statistics=broken_statistics)

    result = validate_working_memory(broken)

    assert result.valid is False
    assert any("entry_count" in e for e in result.errors)


def test_open_question_count_inconsistency_is_rejected() -> None:
    wm = _working_memory(entries=(_entry(),))
    broken_statistics = replace(wm.statistics, open_question_count=99)
    broken = replace(wm, statistics=broken_statistics)

    result = validate_working_memory(broken)

    assert result.valid is False
    assert any("open_question_count" in e for e in result.errors)
