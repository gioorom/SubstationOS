"""
The port through which reference corpora are read (Milestone 28.2).

**Read-only, deliberately.** A corpus is the definition of "correct" for
every extraction rule in this system. Nothing writes one at runtime:
changing what correct means is an edit to a version-controlled file,
reviewed like any other change to the domain, and accompanied by a bump
of the corpus version.

There is no ``save`` on this contract, and an architecture test asserts
the abstract method set stays that way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.evidence_evaluation.corpus_models import (
    ReferenceCorpus,
    ReferenceDocument,
)


class ReferenceCorpusRepository(ABC):
    """Loads versioned reference corpora."""

    @abstractmethod
    def list_corpora(self) -> tuple[str, ...]:
        """Every corpus id available, in a stable order."""

        raise NotImplementedError

    @abstractmethod
    def load(self, corpus_id: str) -> ReferenceCorpus | None:
        """
        The corpus with this id, or ``None`` if there is none.

        Implementations validate on load: a corpus that does not satisfy
        the model must be refused rather than partially returned, because
        a partially-read definition of correct is worse than none.
        """

        raise NotImplementedError

    @abstractmethod
    def materialize(
        self,
        document: ReferenceDocument,
        *,
        document_id: int,
        content_checksum: str,
    ) -> CanonicalTextDocument:
        """
        Turn a reference document's declared text into canonical text.

        On the repository because the repository is what knows how a
        corpus stores its documents. Implementations must build it
        through the **real** segmenter: a corpus that hand-built its own
        tokens would measure the extractor against a world that does not
        exist, and would keep passing on the day segmentation changed.
        """

        raise NotImplementedError
