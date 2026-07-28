"""
Where a document's bytes are recorded to be (Milestone 25.2).

Deliberately a **second, separate port** from ``DocumentContentPort``, and
deliberately tiny. The two answer different questions against different
systems:

- this one asks the *document registry* "where were document N's bytes
  put?" and is answered from the document row;
- ``DocumentContentPort`` asks the *byte store* "what is at this
  reference?" and is answered from storage.

Merging them would give one adapter both a database session and a
filesystem handle, which is exactly the breadth this milestone is trying
not to grant. Keeping them apart also keeps ``DocumentMetadata`` free of
a storage path: the Engineering Index answers questions about documents
and has no business knowing where their bytes live.

A ``storage_reference`` is an **opaque string** to the domain. Today it
is a filesystem path; under a future object store it would be a key. No
domain code parses it, joins it to a root, or assumes it addresses a
file - it is handed back to the content port and nowhere else.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DocumentStorageLocationPort(ABC):
    """Read-only lookup of one document's storage reference."""

    @abstractmethod
    def find_storage_reference(self, document_id: int) -> str | None:
        """
        Return the storage reference recorded for this document, or
        ``None`` if there is no such document or no reference was ever
        recorded for it.

        ``None`` is not an error here. It means the registry cannot say
        where the bytes are, which the caller reports as a content
        failure with that reason named - never as an empty path handed
        to the byte store.
        """

        raise NotImplementedError
