"""
Statistics for Working Memory (Milestone 21). Summarizes the
already-composed entries into one ``WorkingMemoryStatistics`` value
object - never a recomputation of anything an earlier stage already
decided. O(n) in the number of entries (a small, bounded collection).
"""

from __future__ import annotations

from app.domain.working_memory.working_memory_models import (
    WorkingMemoryEntry,
    WorkingMemoryEntryType,
    WorkingMemoryStatistics,
)


def build_statistics(
    entries: tuple[WorkingMemoryEntry, ...],
) -> WorkingMemoryStatistics:
    def _count(entry_type: WorkingMemoryEntryType) -> int:
        return sum(1 for entry in entries if entry.entry_type is entry_type)

    return WorkingMemoryStatistics(
        entry_count=len(entries),
        open_question_count=_count(WorkingMemoryEntryType.OPEN_QUESTION),
        assumption_count=_count(WorkingMemoryEntryType.ASSUMPTION),
        constraint_count=_count(WorkingMemoryEntryType.CONSTRAINT),
        active_reference_count=_count(WorkingMemoryEntryType.ACTIVE_REFERENCE),
        recent_engineering_response_count=_count(
            WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE
        ),
    )
