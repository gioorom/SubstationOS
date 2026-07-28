"""
The fixed, documented relevance weight table for Document Retrieval -
the Engineering Index's read side. Every
``DocumentRelevance.total`` is the sum of named
``DocumentRelevanceComponent`` weights drawn from this module: no machine
learning, no embedding similarity, no unexplained magic numbers, and no
weight computed anywhere else.

Relevance here is *counted evidence*, never a guess about how useful a
document is to an engineer: how a requested identifier matched, how many
mentions the index recorded, and how many of the requested identifiers
the same document covers. Bump ``DOCUMENT_RELEVANCE_POLICY_VERSION``
whenever a weight or rule changes, so ``DocumentRetrievalMetadata`` can
record which policy produced a given result.
"""

from __future__ import annotations

DOCUMENT_RETRIEVAL_VERSION = "1.0"
DOCUMENT_RELEVANCE_POLICY_VERSION = "1.0"

# The requested identifier and a recorded mention's identifier are equal
# after case folding - the strongest signal, since the engineer named
# this exact designation ("87T", "T2").
WEIGHT_EXACT_IDENTIFIER_MATCH = 100.0

# The requested identifier appears *inside* a recorded mention's
# identifier (the substring match the Engineering Index repository
# performs). Real, but weaker: "T2" also occurs in "T21".
WEIGHT_PARTIAL_IDENTIFIER_MATCH = 40.0

# Applied once per document, scaled by the number of recorded mentions
# beyond the first. A document that mentions the equipment repeatedly is
# more likely to be the drawing an engineer wants than one that names it
# once - but repetition never outweighs an exact designation match.
WEIGHT_ADDITIONAL_MENTION = 2.0

# Applied once per document, scaled by the number of requested
# identifiers beyond the first that the same document covers - rewards
# convergent evidence without letting it dominate a strong primary
# match.
WEIGHT_MULTI_TERM_SUPPORT = 10.0
