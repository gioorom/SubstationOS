"""
Deterministic content identity (Milestone 25.2): the checksum and size
that answer "are these the same bytes?" without anybody reading them.

**The same bytes always produce the same identity**, whatever the file is
called, wherever it is stored and however many times it is computed. That
is the whole point: a checksum that depended on the filename would answer
a question nobody asked.

SHA-256, streamed in chunks so a large drawing is never held in memory.
The algorithm is recorded alongside the value rather than assumed, so a
future change of algorithm makes old identities recognisably old instead
of silently incomparable.

**Identity is not deduplication.** Two documents with identical bytes get
identical checksums, and this milestone draws no conclusion from that.
Whether a repeated upload is a duplicate, a legitimate re-issue under a
new revision, or the same drawing filed against two projects is a
question about the *documents*, not their bytes - and answering it here
would be inventing a policy nobody has stated.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)

CHECKSUM_ALGORITHM = "sha256"

# 1 MiB: large enough that hashing a big drawing is not dominated by call
# overhead, small enough that memory use stays flat regardless of file
# size.
CHECKSUM_CHUNK_SIZE = 1024 * 1024


class ContentIdentityFailureReason(str, Enum):
    """
    Why content identity could not be established.

    Four distinct reasons, kept apart because they send an engineer to
    four different places: the document row points nowhere, the file is
    there but unreadable, the file is empty, or reading it broke partway
    through.
    """

    CONTENT_NOT_FOUND = "content_not_found"
    CONTENT_INACCESSIBLE = "content_inaccessible"
    EMPTY_CONTENT = "empty_content"
    CHECKSUM_FAILURE = "checksum_failure"


@dataclass(frozen=True, slots=True)
class ContentIdentity:
    """The bytes' own identity. ``storage_reference`` is recorded so a
    reader can see *which* stored object was hashed, without it being part
    of what the checksum covers."""

    storage_reference: str
    checksum_algorithm: str
    checksum: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ContentIdentityResult:
    """Either an ``identity`` or a ``failure_reason`` - never both, never
    neither."""

    resolved: bool
    identity: ContentIdentity | None = None
    failure_reason: ContentIdentityFailureReason | None = None
    detail: str | None = None


def _failed(
    reason: ContentIdentityFailureReason, detail: str
) -> ContentIdentityResult:
    return ContentIdentityResult(
        resolved=False, failure_reason=reason, detail=detail
    )


def resolve_content_identity(
    content_port: DocumentContentPort, storage_reference: str
) -> ContentIdentityResult:
    """
    Establishes one document's content identity through the read-only
    port.

    A domain service rather than a pure function, because it genuinely
    needs the bytes - but it reaches them only through the port, so the
    domain still imports no filesystem, no storage client and no ORM.

    An empty file fails rather than hashing to SHA-256's empty digest.
    That digest is a real, well-defined value, which is exactly the
    problem: recorded as an identity it would make every empty document in
    the system look like the same document, and would let a zero-byte
    upload pass as ready for extraction.
    """

    if not storage_reference or not storage_reference.strip():
        return _failed(
            ContentIdentityFailureReason.CONTENT_NOT_FOUND,
            "The document record carries no storage reference.",
        )

    try:
        descriptor = content_port.describe(storage_reference)
    except OSError as error:
        return _failed(
            ContentIdentityFailureReason.CONTENT_INACCESSIBLE,
            f"Stored content could not be examined: {error}",
        )

    if descriptor is None:
        return _failed(
            ContentIdentityFailureReason.CONTENT_NOT_FOUND,
            f"No stored content exists at '{storage_reference}'.",
        )

    if not descriptor.readable:
        return _failed(
            ContentIdentityFailureReason.CONTENT_INACCESSIBLE,
            f"Stored content at '{storage_reference}' exists but cannot "
            "be read.",
        )

    if descriptor.size_bytes <= 0:
        return _failed(
            ContentIdentityFailureReason.EMPTY_CONTENT,
            f"Stored content at '{storage_reference}' is empty; there is "
            "nothing to identify.",
        )

    digest = hashlib.sha256()
    hashed_bytes = 0

    try:
        for chunk in content_port.iter_chunks(
            storage_reference, CHECKSUM_CHUNK_SIZE
        ):
            digest.update(chunk)
            hashed_bytes += len(chunk)
    except OSError as error:
        return _failed(
            ContentIdentityFailureReason.CHECKSUM_FAILURE,
            f"Reading stored content failed partway through: {error}",
        )

    if hashed_bytes != descriptor.size_bytes:
        # The file changed under us, or the descriptor and the stream
        # disagree. Either way the checksum describes bytes that are not
        # the ones reported, so recording it would be a lie.
        return _failed(
            ContentIdentityFailureReason.CHECKSUM_FAILURE,
            f"Read {hashed_bytes} bytes but the stored content reports "
            f"{descriptor.size_bytes}; the content changed while it was "
            "being read.",
        )

    return ContentIdentityResult(
        resolved=True,
        identity=ContentIdentity(
            storage_reference=storage_reference,
            checksum_algorithm=CHECKSUM_ALGORITHM,
            checksum=digest.hexdigest(),
            size_bytes=hashed_bytes,
        ),
    )
