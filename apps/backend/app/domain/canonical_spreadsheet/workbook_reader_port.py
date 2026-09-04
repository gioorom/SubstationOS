"""
The workbook reading port (ADR-0034).

The domain declares *what a read produces*; an infrastructure adapter
decides *which library produces it*. That boundary is the point: opening
a workbook is the most library-coupled step in this lineage and the one
place untrusted bytes are decoded, so confining it to one adapter behind
one contract means replacing the library later is a re-canonicalisation,
not a rewrite.

**The port takes bytes, not a path.** The adapter therefore cannot open a
file, walk a directory or reach storage at all - the bytes arrive through
``DocumentContentPort``, which stays the one governed way into stored
content. It also makes the reader trivially testable against literal
bytes.

An implementation **must not**:

- **raise** - every failure is returned as a typed
  :class:`WorkbookReadResult` so the caller records a cause rather than
  catching whatever a library chose to throw this release;
- **interpret** - no header row, no column name, no record, no reading of
  what a register denotes;
- **sort or merge** - the grid is recorded in the file's own coordinates,
  and rows and columns are never renumbered to close a gap;
- **evaluate a formula** - the expression and any value another
  application cached into the file are recorded separately, and nothing
  is computed;
- **identify a header** - which row names the columns is a judgement, and
  this context reads nothing that could check one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.canonical_spreadsheet.canonical_spreadsheet_exceptions import (
    InvalidCanonicalWorkbookError,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
    WorkbookCanonicalizationFailureCode,
)
from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalWorkbook,
)


@dataclass(frozen=True, slots=True)
class WorkbookReadResult:
    """
    Either a ``workbook`` or a ``failure_code`` - never both, never
    neither.

    ``detail`` is a safe, already-composed explanation - never a raw
    exception object and never a stack trace.
    """

    workbook: CanonicalWorkbook | None = None
    failure_code: WorkbookCanonicalizationFailureCode | None = None
    detail: str | None = None

    def __post_init__(self) -> None:
        if (self.workbook is None) == (self.failure_code is None):
            raise InvalidCanonicalWorkbookError(
                "A workbook read result is a workbook or a failure "
                "code, and exactly one of them."
            )

    @property
    def was_read(self) -> bool:
        return self.workbook is not None


class WorkbookReaderPort(ABC):
    """Turns the bytes of a workbook into a canonical representation."""

    @property
    @abstractmethod
    def reader_name(self) -> str:
        """The library's name, recorded on every representation it
        produces so "which reader produced this grid?" is answerable
        years later without guessing."""

        raise NotImplementedError

    @property
    @abstractmethod
    def reader_version(self) -> str:
        """The library's version, recorded for the same reason and
        carried into this artifact's identity. Two library versions can
        legitimately disagree about a difficult workbook; a
        representation that did not name its reader would make that
        disagreement invisible."""

        raise NotImplementedError

    @abstractmethod
    def read(
        self,
        content: bytes,
        *,
        document_id: int,
        content_checksum: str,
        checksum_algorithm: str,
    ) -> WorkbookReadResult:
        """
        Read ``content`` into a :class:`CanonicalWorkbook`.

        Deterministic: the same bytes must always produce an equal
        representation, on any machine, under any load. Implementations
        therefore bound their work by properties of the file rather than
        by elapsed time, and preserve the workbook's own coordinates
        rather than re-deriving an ordering of their own.

        Returns a typed failure - encrypted, malformed, over a safety
        bound, empty, or a reader fault - rather than raising. The
        checksum is carried through rather than recomputed here: this
        port receives bytes and has no way to know they are the bytes
        anybody identified.
        """

        raise NotImplementedError
