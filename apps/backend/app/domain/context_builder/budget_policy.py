"""
Versioned policy constants for Context Builder (EPIC 4, Milestone 14):
the default ``BudgetPolicy`` limits, the selection ordering version, and
the Context Builder artifact version itself - the same "fixed,
documented, version-stamped policy" convention Structured Retrieval's
``scoring_policy.py`` established. Bump the relevant ``*_VERSION``
constant whenever a default changes, so ``ContextMetadata`` can record
which policy produced a given ``ContextPackage``.
"""

from __future__ import annotations

CONTEXT_BUILDER_VERSION = "1.0"
BUDGET_POLICY_VERSION = "1.0"
SELECTION_POLICY_VERSION = "1.0"

# Conservative defaults, chosen so an unbounded upstream
# KnowledgeCandidateCollection (Structured Retrieval's own limit is up
# to 200) cannot silently balloon a ContextPackage - a caller may narrow
# these per request, never widen them beyond the bounds enforced in
# context_builder_validator.py.
DEFAULT_MAX_CANDIDATES = 100
DEFAULT_MAX_ENTITIES = 50
DEFAULT_MAX_RELATIONSHIPS = 50
DEFAULT_MAX_ATTRIBUTES = 50
DEFAULT_MAX_METADATA_ENTRIES = 20
DEFAULT_MAX_WARNINGS = 50
