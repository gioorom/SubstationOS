"""
The fixed, documented policy for Working Memory (Milestone 21): version
stamps, the recency window, and the entry priority/lifetime assignment
tables - the same "fixed, documented policy table" convention every
upstream bounded context in this pipeline establishes. Bump the
relevant ``*_VERSION`` constant whenever an assignment changes, so
``WorkingMemoryMetadata``/``WorkingMemoryVersion`` can record which
policy produced a given ``WorkingMemory``.
"""

from __future__ import annotations

from app.domain.working_memory.working_memory_models import (
    WorkingMemoryEntryType,
    WorkingMemoryLifetime,
    WorkingMemoryPriority,
)

WORKING_MEMORY_VERSION = "1.0"
WORKING_MEMORY_POLICY_VERSION = "1.0"
WORKING_MEMORY_PACKAGE_VERSION = "1.0"

# How many of the most recently produced EngineeringResponses (across
# the owning EngineeringSession and the Conversation's own turns,
# ordered by their own metadata.assembled_at) are ever considered -
# fixed and documented, never a per-request choice.
RECENT_ENGINEERING_RESPONSE_LIMIT = 5

# Fixed priority/lifetime assignment per entry type - never derived
# from an entry's own content. Every WorkingMemoryEntryType has an
# entry here, including the reserved types this milestone's builder
# never actually produces, so a future capability that does produce
# them inherits a documented assignment rather than inventing one.
ENTRY_PRIORITY: dict[WorkingMemoryEntryType, WorkingMemoryPriority] = {
    WorkingMemoryEntryType.CURRENT_OBJECTIVE: WorkingMemoryPriority.HIGH,
    WorkingMemoryEntryType.CURRENT_EQUIPMENT: WorkingMemoryPriority.MEDIUM,
    WorkingMemoryEntryType.CURRENT_ELECTRICAL_AREA: WorkingMemoryPriority.MEDIUM,
    WorkingMemoryEntryType.ASSUMPTION: WorkingMemoryPriority.MEDIUM,
    WorkingMemoryEntryType.OPEN_QUESTION: WorkingMemoryPriority.HIGH,
    WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE: WorkingMemoryPriority.LOW,
    WorkingMemoryEntryType.ACTIVE_REFERENCE: WorkingMemoryPriority.MEDIUM,
    WorkingMemoryEntryType.CURRENT_TASK: WorkingMemoryPriority.HIGH,
    WorkingMemoryEntryType.CONSTRAINT: WorkingMemoryPriority.HIGH,
}

ENTRY_LIFETIME: dict[WorkingMemoryEntryType, WorkingMemoryLifetime] = {
    WorkingMemoryEntryType.CURRENT_OBJECTIVE: WorkingMemoryLifetime.SESSION,
    WorkingMemoryEntryType.CURRENT_EQUIPMENT: WorkingMemoryLifetime.SESSION,
    WorkingMemoryEntryType.CURRENT_ELECTRICAL_AREA: WorkingMemoryLifetime.SESSION,
    WorkingMemoryEntryType.ASSUMPTION: WorkingMemoryLifetime.CONVERSATION,
    WorkingMemoryEntryType.OPEN_QUESTION: WorkingMemoryLifetime.TURN,
    WorkingMemoryEntryType.RECENT_ENGINEERING_RESPONSE: WorkingMemoryLifetime.CONVERSATION,
    WorkingMemoryEntryType.ACTIVE_REFERENCE: WorkingMemoryLifetime.CONVERSATION,
    WorkingMemoryEntryType.CURRENT_TASK: WorkingMemoryLifetime.SESSION,
    WorkingMemoryEntryType.CONSTRAINT: WorkingMemoryLifetime.CONVERSATION,
}
