"""
The closed vocabulary of Governed Structured Retrieval (EPIC 31.2).

Five query types, eight match strategies, two scopes, four result kinds
and three outcomes. Every one of them is a member of a closed enum
because a retrieval whose whole value is that an engineer can read *why*
an answer came back must not be able to produce a reason nobody planned.

**Nothing here is a score.** The governed graph carries no confidence,
weight or probability (ADR-0024), and neither does retrieval over it. A
result is ranked by *which strategy matched it*, and that strategy is a
statement about the governed data, not a number about how much to trust
it.
"""

from __future__ import annotations

from enum import Enum


class GovernedQueryType(str, Enum):
    """
    Which engineering question a query asks.

    Each member corresponds to a capability the governed graph actually
    has. There is no ``ATTRIBUTE_SEARCH`` and no ``LEXICAL_SEARCH``: the
    first searched a property bag the governed graph deliberately does
    not have, and the second scanned every string on every node - see
    ``governed_structured_retrieval.md`` for what each of the legacy
    modes became.
    """

    #: "Which governed assets does this designation name?"
    ASSET_BY_DESIGNATION = "asset_by_designation"

    #: "What quantities does governed knowledge assert about this asset?"
    QUANTITY_FOR_ASSET = "quantity_for_asset"

    #: "Which governed relationships exist, of this kind, in this scope?"
    RELATIONSHIPS = "relationships"

    #: "What governed knowledge came out of this document?"
    DOCUMENT_KNOWLEDGE = "document_knowledge"

    #: "What is this governed object, and where did it come from?" The
    #: provenance query: every result already carries its provenance, so
    #: asking for provenance *is* asking for the object by identity.
    GOVERNED_IDENTITY = "governed_identity"


class RetrievalScope(str, Enum):
    """
    Which governed knowledge a query may see.

    ``CURRENT_ONLY`` is the default everywhere and the only scope the
    Engineering Engine uses. Historical knowledge is what the platform
    *used* to assert; letting it answer a current engineering question
    would be the silent staleness the whole lifecycle model exists to
    prevent, so reading it is always an explicit act.
    """

    CURRENT_ONLY = "current_only"
    CURRENT_AND_HISTORICAL = "current_and_historical"


class GovernedMatchStrategy(str, Enum):
    """
    Why a governed object is in the result.

    Exactly one per result, and it answers "why did this match?" without
    cross-referencing the query. Ordered by
    ``governed_match_policy.STRATEGY_PRECEDENCE``: an object matched on
    its governed identity outranks one matched on a designation folded
    down to its alphanumerics, because the first is a fact about the
    graph and the second is a fact about two strings.
    """

    #: The query named this object's governed id.
    GOVERNED_IDENTITY = "governed_identity"

    #: The governed label equals the requested designation, character
    #: for character.
    EXACT_DESIGNATION = "exact_designation"

    #: The labels are equal once case and surrounding whitespace are
    #: folded ("TR1" / "tr1 ").
    NORMALIZED_DESIGNATION = "normalized_designation"

    #: The pipeline's own normalized value for the entity equals the
    #: folded designation. A governed field, never a re-derivation.
    NORMALIZED_VALUE = "normalized_value"

    #: The labels are equal once every non-alphanumeric character is
    #: dropped as well ("C-295" / "c 295" / "C295").
    CANONICAL_DESIGNATION = "canonical_designation"

    #: Reached by following a governed relationship from an asset the
    #: query resolved.
    RELATIONSHIP_TRAVERSAL = "relationship_traversal"

    #: Selected because it is a governed relationship of the requested
    #: kind.
    EDGE_KIND = "edge_kind"

    #: Selected because its provenance names the requested document.
    DOCUMENT_SCOPE = "document_scope"


class GovernedResultKind(str, Enum):
    """
    What one result *is*.

    Mirrors the governed vocabulary rather than inventing a parallel one:
    every node kind produces a result kind and every edge kind produces
    ``RELATIONSHIP``, so a member with no governed counterpart would be a
    concept no promotion can create.

    Relationships of **different edge kinds share one result kind**. A
    result says what it is - a governed relationship - and its
    ``edge_kind`` says which one; splitting the vocabulary per edge kind
    would make every future relationship a change to this enum and to
    every consumer that switches on it.
    """

    ASSET = "asset"
    QUANTITY = "quantity"
    RELATIONSHIP = "relationship"

    #: A governed structural location - ``+E01``. From a
    #: ``STRUCTURAL_LOCATION`` node.
    STRUCTURAL_LOCATION = "structural_location"


class GovernedMatchOutcome(str, Enum):
    """
    How many governed objects satisfied the query, before any limit.

    The Engineering Engine reads this rather than counting results,
    because "one" and "one of several" are different engineering
    situations and a caller that only counted a truncated page could not
    tell them apart.

    For a list-shaped query (``RELATIONSHIPS``, ``DOCUMENT_KNOWLEDGE``)
    ``MULTIPLE_MATCHES`` is the expected answer and says nothing about
    ambiguity - see ``governed_structured_retrieval.md``.
    """

    NO_MATCH = "no_match"
    UNIQUE_MATCH = "unique_match"
    MULTIPLE_MATCHES = "multiple_matches"
