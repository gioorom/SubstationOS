from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.graph_builder.graph_builder_models import (
    GraphOperationBatch,
)


class GraphOperationBatchRepository(ABC):
    """
    Port for persisting and retrieving Graph Operation Batches - Graph
    Builder's own output artifact. This is not graph persistence: no
    graph node, edge, or database is stored or referenced by this port;
    it only records the deterministic operation list this bounded
    context produced, so ``GET /graph-builder/batch/{batch_id}`` has
    something to return.

    Deliberately has no ``update``/``delete`` method: a batch is a
    point-in-time snapshot, produced once and never edited in place -
    rebuilding produces a new batch, not a mutation of an old one.
    """

    @abstractmethod
    def save(self, batch: GraphOperationBatch) -> GraphOperationBatch:
        """Insert a new batch (``id`` must be ``None``) and return it
        with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, batch_id: int) -> GraphOperationBatch | None:
        """Return the batch with this id, or ``None`` if none
        exists."""

        raise NotImplementedError
