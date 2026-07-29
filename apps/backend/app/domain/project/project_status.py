"""
The delivery phase of the real installation a Project represents.

**Orthogonal to** ``ProjectLifecycleState``, and this module exists to
keep them that way. They answer different questions:

- ``ProjectStatus``          - where the *works* are.
- ``ProjectLifecycleState``  - whether the *record* is editable.

A project can be ``ENERGIZED`` and ``ARCHIVED`` at the same time: the
substation is live and the file is closed. Merging the two would make
that state unrepresentable, and it is a completely ordinary one.

Declared in the domain rather than imported from ``app.models.project``
because it is a domain vocabulary that happens to be persisted, not a
persistence detail that happens to be exposed. A test asserts this set
equals the stored one so the two cannot drift.
"""

from __future__ import annotations

from enum import Enum


class ProjectStatus(str, Enum):
    """The delivery phase of the installation, in order."""

    PLANNING = "planning"
    ENGINEERING = "engineering"
    CONSTRUCTION = "construction"
    COMMISSIONING = "commissioning"
    ENERGIZED = "energized"
    CLOSED = "closed"
