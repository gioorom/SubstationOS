"""
The narrow, **read-only** port onto stored document bytes (Milestone
25.2).

This is the only way any bounded context reaches document content, and it
is deliberately the smallest surface that supports what this milestone
needs: look at a file's leading bytes, stream it to checksum it, and say
whether it is there at all.

**Read-only by construction, not by convention.** There is no write, no
delete, no move and no open-for-append. A future capability that needs to
*store* content must add its own port and justify it - it cannot quietly
acquire the ability through this one. An architecture test asserts the
abstract-method set, so the guarantee is a matter of contract.

The domain defines the contract; an infrastructure adapter implements it
against the filesystem today and could implement it against object
storage tomorrow without this module changing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentContentDescriptor:
    """
    What is known about stored content without reading it.

    ``size_bytes`` is the stored length. ``readable`` is ``False`` when
    the reference resolves to something that exists but cannot be read -
    a permission problem, a directory, a broken link. That is a different
    fact from "not found", and conflating the two would tell an engineer
    to look in the wrong place.
    """

    storage_reference: str
    size_bytes: int
    readable: bool


class DocumentContentPort(ABC):
    """Port for reading stored document bytes. Implemented by an
    infrastructure adapter; never by the domain."""

    @abstractmethod
    def describe(
        self, storage_reference: str
    ) -> DocumentContentDescriptor | None:
        """
        Return what is known about the stored content, or ``None`` if
        nothing exists at this reference.

        ``None`` means *not found*. A descriptor with ``readable=False``
        means *found but unreadable*. Callers must keep the two apart.
        """

        raise NotImplementedError

    @abstractmethod
    def read_prefix(self, storage_reference: str, length: int) -> bytes:
        """
        Read at most ``length`` leading bytes - the bounded read format
        classification needs.

        Bounded rather than whole-file on purpose: identifying a format
        requires a few dozen bytes, and a port that returned everything
        would invite a caller to read a whole drawing into memory for it.
        """

        raise NotImplementedError

    @abstractmethod
    def iter_chunks(
        self, storage_reference: str, chunk_size: int
    ) -> Iterator[bytes]:
        """
        Stream the content in chunks, for checksumming.

        Streamed rather than returned whole so a 200 MB drawing is
        hashed without ever being held in memory.
        """

        raise NotImplementedError
