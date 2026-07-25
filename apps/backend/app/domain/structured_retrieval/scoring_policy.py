"""
The fixed, documented scoring weight table for Structured Retrieval
(Milestone 13). Every ``KnowledgeCandidateScore.total`` is the sum of
named ``KnowledgeCandidateScoreComponent`` weights drawn from this
module - no machine learning, no unexplained magic numbers, no weight
computed anywhere else. These values may be adjusted only with a clear
domain rationale recorded in the commit that changes them; bump
``SCORING_POLICY_VERSION`` whenever a weight changes, so
``RetrievalExecutionMetadata`` can record which policy produced a given
result.
"""

from __future__ import annotations

SCORING_POLICY_VERSION = "1.0"

# An exact match on a caller-supplied canonical entity reference - the
# strongest possible signal, since the caller named this exact entity.
WEIGHT_EXACT_CANONICAL_ID_MATCH = 100.0

# A match after separator/case normalization (e.g. "C-295" ~ "c295") -
# strong, but not as strong as an exact match.
WEIGHT_NORMALIZED_IDENTIFIER_MATCH = 80.0

# A relationship whose full natural key (subject, type, object) is
# implicated by the match - stronger than a bare type match.
WEIGHT_RELATIONSHIP_NATURAL_KEY_MATCH = 75.0

WEIGHT_RELATIONSHIP_TYPE_MATCH = 60.0
WEIGHT_ENTITY_TYPE_MATCH = 50.0
WEIGHT_ATTRIBUTE_NAME_MATCH = 40.0
WEIGHT_ATTRIBUTE_VALUE_MATCH = 35.0

# Per distinct matched lexical token - several distinct tokens each
# contribute their own component (see candidate_aggregation.py).
WEIGHT_LEXICAL_TOKEN_MATCH = 10.0

# A candidate discovered/confirmed via 1-hop neighborhood enrichment.
WEIGHT_NEIGHBORHOOD_SUPPORT = 5.0

# Per additional distinct criterion kind beyond the first that
# contributed to the same merged candidate - rewards convergent
# evidence without letting it dominate a strong primary match.
WEIGHT_MULTI_CRITERION_SUPPORT = 5.0
