from __future__ import annotations

from abc import ABC, abstractmethod


class GraphUnitOfWork(ABC):
    """
    Port for the transaction boundary one batch execution runs inside.
    ``GraphStore`` and ``GraphExecutionRepository`` write within one
    shared transaction (flushing, never committing on their own); this
    port is the only thing that commits or rolls that transaction back.

    Introduced beyond this milestone's literal type list because the
    atomicity requirement ("execute the complete batch atomically... A
    failed operation must roll back the complete graph mutation
    transaction") cannot be honored across several repository calls
    without *some* explicit transaction-boundary seam - and a raw
    ``Session`` must not leak into the service layer (every other
    bounded context in this codebase depends only on ports). This is
    that seam, kept as small as the requirement demands.
    """

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
