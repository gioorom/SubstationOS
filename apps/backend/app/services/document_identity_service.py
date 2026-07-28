"""
Application service for Document Identity (EPIC 2, Milestone 25.2).

The one place that turns *a storage reference* into the two deterministic
facts this milestone establishes about a document:

    storage reference
          |
      content identity      (found, readable, non-empty, SHA-256, size)
          |
      leading bytes         (at most SIGNATURE_PREFIX_LENGTH of them)
          |
      format classification (signature > declared MIME > extension)

Both callers - the upload endpoint and the ingestion pipeline - come
through here, so the format rules exist once. An upload that classified
one way and an ingestion that classified another would make a document's
own format a matter of which code path last looked at it.

It reads bytes only through ``DocumentContentPort``, and only the
leading signature plus a streamed digest. **No parsing, no OCR, no text
extraction, no embeddings, no LLM.** Nothing here learns what a document
says; it establishes which bytes they are and what kind of file they
form.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.document_identity.content_identity import (
    ContentIdentityResult,
    resolve_content_identity,
)
from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_format import FormatClassification
from app.domain.document_identity.format_classifier import (
    classify_document_format,
)
from app.domain.document_identity.format_signatures import (
    SIGNATURE_PREFIX_LENGTH,
)


@dataclass(frozen=True, slots=True)
class ResolvedDocumentIdentity:
    """
    What one look at a document's stored bytes established.

    ``format`` is always present, even when ``content`` failed: a file
    that could not be read can still carry a declared MIME type and an
    extension, and the classification records exactly that - a format
    settled by weak evidence, with the signature evidence reading "no
    content was readable". Withholding it would lose the only thing still
    known about an unreadable document.
    """

    content: ContentIdentityResult
    format: FormatClassification


def resolve_document_identity(
    content_port: DocumentContentPort,
    *,
    storage_reference: str | None,
    filename: str | None = None,
    declared_mime_type: str | None = None,
) -> ResolvedDocumentIdentity:
    """
    Establishes content identity and format for the bytes at
    ``storage_reference``.

    The leading bytes are read **only** when content identity resolved.
    Reading a prefix from something already reported as missing, empty or
    unreadable would either fail again or - worse - succeed against a
    file that had changed underneath, and the classification would then
    describe bytes the checksum does not cover.
    """

    content = resolve_content_identity(content_port, storage_reference or "")

    content_prefix: bytes | None = None

    if content.resolved:
        try:
            content_prefix = content_port.read_prefix(
                content.identity.storage_reference, SIGNATURE_PREFIX_LENGTH
            )
        except OSError:
            # The bytes were readable a moment ago and are not now. The
            # classification simply proceeds without a signature, which
            # its evidence records honestly; the content failure is not
            # rewritten after the fact.
            content_prefix = None

    return ResolvedDocumentIdentity(
        content=content,
        format=classify_document_format(
            content_prefix=content_prefix,
            declared_mime_type=declared_mime_type,
            filename=filename,
        ),
    )
