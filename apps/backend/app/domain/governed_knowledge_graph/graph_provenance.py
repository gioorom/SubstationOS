"""
Why the graph believes something.

**Every node and every edge carries provenance, and there is no way to
construct one without it.** That is the difference between a governed
knowledge graph and a property graph: an answer here can always be
followed back to the statement it came from, the engineer who approved
it, the rules that produced it and the document it was read out of.

An edge is never anonymous. A node is never anonymous. If provenance
cannot be stated, construction raises rather than storing a fact nobody
can trace - a missing answer is visibly missing, whereas an untraceable
one looks exactly like a good one.

---

## What is recorded, and what is not

Recorded: **identity**. Statement key, review id, reviewer, rule and
policy versions, support fingerprint, document, checksum.

Not recorded: the statement itself, the facts, the entities, the
evidence, or their text. The graph is a *projection*; the artefacts stay
in the pipeline that produced them, which remains their single account.
A copy here would be a second one, and the day the two disagreed nobody
could say which was authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.governed_knowledge_graph.graph_exceptions import (
    InvalidGraphProvenanceError,
)


@dataclass(frozen=True, slots=True)
class GraphProvenance:
    """
    The complete origin of one piece of governed knowledge.

    Every field is copied from an artefact somebody else governs: the
    statement, its review, or the semantic set they belong to. This
    context computes none of them.
    """

    #: The semantic statement this knowledge was promoted from.
    statement_key: str

    #: Which document, and which bytes of it.
    document_id: int
    content_checksum: str

    #: The review that authorised the promotion, and who passed it.
    review_id: int
    reviewer_user_id: int
    reviewer_display_name: str
    reviewed_at: datetime

    #: The rule that assigned the meaning.
    semantic_rule_id: str
    semantic_rule_version: str
    semantic_contract_version: str

    #: The upstream policy chain: evidence to entities, entities to
    #: facts, facts to meaning.
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str

    #: The support chain, as identity rather than as content.
    support_fingerprint: str

    #: The project this knowledge belongs to, for visibility. ``None``
    #: for a canonical-library document that belongs to no project.
    project_id: int | None = None

    def __post_init__(self) -> None:
        required = {
            "statement_key": self.statement_key,
            "content_checksum": self.content_checksum,
            "semantic_rule_id": self.semantic_rule_id,
            "semantic_rule_version": self.semantic_rule_version,
            "semantic_contract_version": self.semantic_contract_version,
            "resolution_policy_version": self.resolution_policy_version,
            "fact_policy_version": self.fact_policy_version,
            "semantic_policy_version": self.semantic_policy_version,
            "support_fingerprint": self.support_fingerprint,
            "reviewer_display_name": self.reviewer_display_name,
        }

        missing = sorted(name for name, value in required.items() if not value)

        if missing:
            raise InvalidGraphProvenanceError(
                "Graph knowledge must state where it came from; missing: "
                f"{', '.join(missing)}."
            )

        if self.document_id <= 0:
            raise InvalidGraphProvenanceError(
                "Graph knowledge must name the document it came from."
            )

        if self.review_id <= 0:
            raise InvalidGraphProvenanceError(
                "Graph knowledge must name the review that authorised it."
            )

    @property
    def rule_identity(self) -> str:
        """``rated_power_from_…@1.0`` - what interpreted the statement."""

        return f"{self.semantic_rule_id}@{self.semantic_rule_version}"

    @property
    def pipeline_identity(self) -> tuple[str, str, str, str]:
        """
        The whole upstream chain, as one comparable value.

        Two pieces of knowledge sharing this were derived under the same
        bytes and the same rules.
        """

        return (
            self.content_checksum,
            self.resolution_policy_version,
            self.fact_policy_version,
            self.semantic_policy_version,
        )

    def describe(self) -> str:
        """One line, for an audit event's detail."""

        return (
            f"statement {self.statement_key} approved in review "
            f"{self.review_id} under {self.rule_identity}"
        )
