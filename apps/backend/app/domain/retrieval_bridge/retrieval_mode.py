"""
The shape of retrieval a prepared engineering request declares.

**Moved here by EPIC 31.4**, from
``structured_retrieval.structured_retrieval_models``. The concept
outlived the package that first defined it: legacy Structured Retrieval
is retired, and the Retrieval Bridge - which is live, authoritative and
serves ``POST /projects/{id}/engineering-requests/prepare`` - is the only
context that still has anything to say about a retrieval *mode*.

Moved rather than aliased. An alias pointing back at a retired module
would have kept the retired package importable and made the retirement a
rename; this is the concept's real owner now, and the enum is defined
here outright.

---

## What this enum is, and what it is not

It is **the bridge's declaration of what kind of retrieval its derived
configuration asks for**, reported to the caller on the prepared
request. It is a description of the *request*.

It is **not** an instruction to the Engineering Engine. Since EPIC 31.2
the engine derives no mode at all: its governed retrieval planner reads
the designation fields directly and issues typed governed queries
(``governed_retrieval_step_handlers.build_plan``). A mode the engine
consumed would be a mode that could disagree with what it did.

## Why the members did not change

The six members are the six shapes the bridge's policy table can
legitimately produce or refuse, and the bridge's own validation rules are
written against them (`retrieval_bridge_validation`). Reducing the set to
the two the bridge currently emits would delete the vocabulary those
refusals are expressed in - "this bridge never derives a bare entity
type" needs ``ENTITY_TYPE_SEARCH`` to exist in order to refuse it.
"""

from __future__ import annotations

from enum import Enum


class RetrievalMode(str, Enum):
    """Which shape of retrieval a prepared request declares - always
    stated explicitly, never inferred from free text."""

    ENTITY_LOOKUP = "entity_lookup"
    ENTITY_TYPE_SEARCH = "entity_type_search"
    ATTRIBUTE_SEARCH = "attribute_search"
    RELATIONSHIP_SEARCH = "relationship_search"
    LEXICAL_SEARCH = "lexical_search"
    COMBINED = "combined"
