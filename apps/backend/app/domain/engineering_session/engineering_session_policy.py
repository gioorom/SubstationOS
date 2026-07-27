"""
The fixed, documented version stamps for Engineering Session
(Milestone 19) - the same "fixed, documented policy table" convention
Structured Retrieval's ``scoring_policy.py``, Context Builder's
``budget_policy.py``, Prompt Builder's ``composition_policy.py``, and
Engineering Response's ``engineering_response_policy.py`` all
established. Bump the relevant ``*_VERSION`` constant whenever the
state machine or timeline event vocabulary changes, so
``EngineeringSessionMetadata``/``EngineeringSessionVersion`` can record
which policy produced a given ``EngineeringSession``.
"""

from __future__ import annotations

ENGINEERING_SESSION_VERSION = "1.0"
SESSION_POLICY_VERSION = "1.0"
SESSION_PACKAGE_VERSION = "1.0"
