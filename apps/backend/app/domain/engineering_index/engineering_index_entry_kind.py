from __future__ import annotations

from enum import Enum


class EngineeringIndexEntryKind(str, Enum):
    """
    The kind of candidate mention an Engineering Index entry records, per
    Architecture Freeze v1.0
    (docs/architecture/project_intelligence_architecture.md §5). This is
    the fixed, architecture-defined inventory of what the Index tracks -
    it is not a general-purpose tagging scheme.
    """

    EQUIPMENT = "equipment"
    SIGNAL = "signal"
    CABLE = "cable"
    CABINET_OR_FRAME = "cabinet_or_frame"
    PROTECTION = "protection"
    DRAWING = "drawing"
    FUNCTION = "function"
    CROSS_REFERENCE = "cross_reference"
