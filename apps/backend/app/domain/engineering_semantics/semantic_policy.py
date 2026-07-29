"""
The fixed policy of semantic interpretation (Milestone 30.1).

Everything here is recorded on a stored semantic set so a historical
interpretation stays explainable, and none of it is a knob to tune per
run.
"""

from __future__ import annotations

from app.domain.engineering_facts.fact_policy import FACT_POLICY_VERSION

# The semantic policy's own version. Bumped when the *catalogue* changes
# - a rule added, a rule version raised, a statement type declared - so a
# stored set always says which body of engineering judgement produced it.
SEMANTIC_POLICY_VERSION = "1.0"

# The version of the statement contract itself - the shape of a
# statement. Recorded alongside the rule version because the two change
# for different reasons.
SEMANTIC_CONTRACT_VERSION = "1.0"

# Fact construction policies this interpreter understands. A fact set
# built under a newer policy is refused rather than interpreted on a
# best-effort basis: it may carry predicates this code would silently
# ignore, and a semantic set missing half its meaning is worse than a
# visible refusal.
SUPPORTED_FACT_POLICY_VERSIONS: frozenset[str] = frozenset(
    {FACT_POLICY_VERSION}
)


def is_supported_fact_policy_version(version: str) -> bool:
    return version in SUPPORTED_FACT_POLICY_VERSIONS
