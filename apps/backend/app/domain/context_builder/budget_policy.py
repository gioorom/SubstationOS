"""
Versioned policy constants for Governed Context Assembly (EPIC 31.3).

The default ``BudgetPolicy`` limits, the selection ordering version, and
the Context Assembly artifact version itself - the same "fixed,
documented, version-stamped policy" convention the rest of the platform
follows.

---

## When each version must change

- ``CONTEXT_ASSEMBLY_VERSION`` - the assembled ``ContextPackage`` could
  differ for unchanged governed input: a new field, a changed grouping,
  a different warning set.
- ``SELECTION_POLICY_VERSION`` - the order or the admission rule
  changes.
- ``BUDGET_POLICY_VERSION`` - a default limit changes.

Each is a statement about **behaviour**, never about a deployment: two
installations running the same code report the same versions, and a
``ContextPackage`` carries them so a reader can tell which rules
assembled it.

``2.0`` across the board is EPIC 31.3: Context Assembly consumes
governed retrieval results instead of legacy knowledge candidates, so an
identical upstream question can produce a materially different package
and the version says so.
"""

from __future__ import annotations

CONTEXT_ASSEMBLY_VERSION = "2.0"
BUDGET_POLICY_VERSION = "2.0"
SELECTION_POLICY_VERSION = "2.0"

# Conservative defaults, chosen so an unbounded set of governed results
# (each governed query may return up to 200) cannot silently balloon a
# ContextPackage - a caller may narrow these per request, never widen
# them beyond the bounds enforced in context_builder_validator.py.
DEFAULT_MAX_ITEMS = 100
DEFAULT_MAX_ASSETS = 50
DEFAULT_MAX_QUANTITIES = 50
DEFAULT_MAX_RELATIONSHIPS = 50

#: Governed structural locations (EPIC 32.P1) admitted to one context.
#:
#: Lower than the others on purpose. A location is a place several assets
#: point at, so a context that retrieved twenty assets rarely reaches
#: twenty distinct locations - and a context carrying more locations than
#: equipment is describing a building rather than answering an
#: engineering question.
DEFAULT_MAX_LOCATIONS = 20
DEFAULT_MAX_METADATA_ENTRIES = 20
DEFAULT_MAX_WARNINGS = 50
