"""
How a designation is folded before it is compared.

Three functions, all pure, all total, all deterministic. **No stemming,
no edit distance, no embeddings, no similarity, no substring matching**
- and no locale-dependent behaviour: ``casefold`` is applied, never
``lower`` with an implicit locale, and the alphanumeric test is
Unicode-aware but position-independent.

---

## Why not substring matching

The governed graph's own list endpoint offers a ``search`` parameter
backed by SQL ``ILIKE '%term%'``. Retrieval deliberately does **not**
use it:

- its collation is a property of the database, so the same query could
  answer differently on SQLite and PostgreSQL, and a deterministic
  retrieval contract cannot rest on that;
- a substring match cannot say *why* it matched in a way an engineer can
  check - `"T1"` inside `"QT10"` is a coincidence, not a designation.

Retrieval therefore reads governed rows filtered by indexed, exact
columns and folds designations here, where the rule is one readable
function.

## The three folds, and the order they are tried in

| Fold | `"C-295"` becomes | Matches |
|---|---|---|
| exact | `"C-295"` | `"C-295"` |
| `normalize_designation` | `"c-295"` | `" C-295 "`, `"c-295"` |
| `canonical_designation_key` | `"c295"` | `"C 295"`, `"c295"` |

Each is strictly weaker than the one above it, and each is a separate
``GovernedMatchStrategy`` so a result says which one was needed.
``canonical_designation_key`` reproduces the legacy
``lexical_matching.normalize_identifier`` behaviour exactly, so the
capability an engineer relied on survives the migration under a name
that says what it does.
"""

from __future__ import annotations

#: Bumped whenever a fold changes. Echoed on every result's diagnostics,
#: so a caller can tell which rules produced a given match - the same
#: discipline the semantic rule versions follow.
GOVERNED_NORMALIZATION_VERSION = "1.0"

#: A designation longer than this is not a designation. Bounds the work
#: a single query can ask for, and is checked at construction.
MAX_DESIGNATION_LENGTH = 120


def normalize_designation(text: str) -> str:
    """
    Case-folded, with surrounding and repeated whitespace collapsed.

    ``"  TR 1 "`` and ``"tr 1"`` fold to the same value; ``"TR1"`` does
    not, because removing the space between two tokens is a stronger
    claim - that is what ``canonical_designation_key`` is for.
    """

    return " ".join(text.split()).casefold()


def canonical_designation_key(text: str) -> str:
    """
    Case-folded, with every non-alphanumeric character removed.

    ``"C-295"``, ``"c 295"`` and ``"C295"`` all fold to ``"c295"``. This
    is the strongest fold retrieval performs, and it is still an
    *equality* test on a derived string - never a similarity, never a
    partial match.
    """

    return "".join(
        character for character in text.casefold() if character.isalnum()
    )


def is_blank(text: str) -> bool:
    """Whether a caller-supplied term carries no comparable content."""

    return not text.strip()
