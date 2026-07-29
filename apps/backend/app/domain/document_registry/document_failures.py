"""
Typed failures for the document registry.

Each carries the identifiers a caller needs and **nothing about the
infrastructure that failed**: no path, no exception text, no adapter
name. A message that says "PermissionError: /var/substationos/storage/…"
tells an attacker the storage layout and tells an engineer nothing they
can act on.
"""

from __future__ import annotations


class DocumentRegistryError(Exception):
    """Base class for every document registry failure."""


class DocumentNotFoundError(DocumentRegistryError):
    """No document with this id exists in the registry."""

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id

        super().__init__(f"Document '{document_id}' does not exist.")


class DocumentContentNotFoundError(DocumentRegistryError):
    """
    The document exists, but its bytes do not.

    Deliberately distinct from :class:`DocumentNotFoundError`: a missing
    registry row and a missing file are different problems with
    different remedies, and reporting both as "not found" would send an
    engineer looking in the wrong place.
    """

    def __init__(self, document_id: int, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason

        super().__init__(
            f"The content of document '{document_id}' is not available: "
            f"{reason}."
        )


class DocumentContentAccessError(DocumentRegistryError):
    """
    The content exists and could not be read - a permission problem, an
    unreadable reference, a storage fault.

    Distinct from "not found" for the same reason: "it is not there" and
    "it is there and I cannot read it" are different facts.
    """

    def __init__(self, document_id: int, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason

        super().__init__(
            f"The content of document '{document_id}' could not be "
            f"read: {reason}."
        )


class DocumentPersistenceError(DocumentRegistryError):
    """
    The registry itself could not be read.

    Raised in place of the underlying database exception so no driver
    message, table name or connection string reaches a response.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail

        super().__init__(f"The document registry could not be read: {detail}")
