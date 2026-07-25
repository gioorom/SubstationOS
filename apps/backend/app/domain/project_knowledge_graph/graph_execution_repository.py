from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.project_knowledge_graph.graph_execution_models import (
    GraphExecution,
)


class GraphExecutionRepository(ABC):
    """
    Port for persisting and retrieving ``GraphExecution`` audit records,
    and for the fingerprint-to-execution mapping that makes batch
    execution idempotent (``get_successful_by_fingerprint``).

    Like ``GraphStore``, ``save``/``update`` deliberately do not commit
    their own transaction - see ``GraphUnitOfWork``. This lets one
    ``GraphExecution`` write and its batch's graph mutations commit or
    roll back together, as one atomic unit.
    """

    @abstractmethod
    def save(self, execution: GraphExecution) -> GraphExecution:
        """Insert a new execution (``id`` must be ``None``) and return
        it with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def update(self, execution: GraphExecution) -> GraphExecution:
        """Persist an execution's new state (``id`` must already be
        set) - used only for the ``PENDING`` -> ``SUCCEEDED``
        transition within one attempt."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, execution_id: int) -> GraphExecution | None:
        raise NotImplementedError

    @abstractmethod
    def get_successful_by_fingerprint(
        self,
        batch_fingerprint: str,
    ) -> GraphExecution | None:
        """
        Return the ``SUCCEEDED`` execution already recorded for this
        exact batch content, if one exists - the mechanism that makes
        retrying the same batch, or executing a different batch with
        identical semantic content, idempotent.
        """

        raise NotImplementedError

    @abstractmethod
    def list_by_batch(self, batch_id: int) -> list[GraphExecution]:
        raise NotImplementedError
