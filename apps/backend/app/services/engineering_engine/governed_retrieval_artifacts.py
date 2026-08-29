"""
The two typed artifacts the engine's governed retrieval steps exchange.

They live in their own module because both the handlers that produce
them and the ``WorkflowExecutionContext`` that carries them need the
types, and a module that imported both would close a cycle. Same reason
``step_handler.py`` holds the handler contract: the shared vocabulary
sits below everything that speaks it.

Neither type is a domain model. They are **application artifacts** - the
engine's own record of what it decided to ask and what came back - and
the governed knowledge inside them is untouched
``GovernedRetrievalResult``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedRetrievalQuery,
    GovernedRetrievalResult,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
)


@dataclass(frozen=True, slots=True)
class GovernedRetrievalPlan:
    """
    What the engine will ask the governed graph, decided once, before any
    read - inspectable and unit-testable on its own, exactly as the
    legacy ``RetrievalQueryPlan`` was.

    ``unsupported_criteria`` names request fields that have no governed
    counterpart. They are **reported, never silently dropped**: a caller
    that asked for an attribute search deserves to see that the governed
    graph has no attribute bag rather than an empty result it will read
    as "there is no such equipment".
    """

    project_id: int
    queries: tuple[GovernedRetrievalQuery, ...]
    unsupported_criteria: tuple[str, ...]

    @property
    def resolves_nothing(self) -> bool:
        return not self.queries


@dataclass(frozen=True, slots=True)
class GovernedRetrievalOutcome:
    """
    Everything one engine retrieval step produced.

    A **tuple** of results rather than one, because a request may name
    more than one designation and each is resolved as its own governed
    query - so each keeps its own outcome, its own diagnostics and its
    own explanation. Merging them into a single result would lose which
    designation was ambiguous.
    """

    results: tuple[GovernedRetrievalResult, ...]

    @property
    def is_empty(self) -> bool:
        return all(
            result.outcome is GovernedMatchOutcome.NO_MATCH
            for result in self.results
        )

    @property
    def has_ambiguity(self) -> bool:
        """Whether any resolved subject matched more than one governed
        object - the fact the engine must not hide."""

        return any(result.is_ambiguous for result in self.results)

    @property
    def ambiguous_queries(
        self,
    ) -> tuple[GovernedRetrievalQuery, ...]:
        return tuple(
            result.query for result in self.results if result.is_ambiguous
        )
