"""
The deterministic identity of one canonical workbook (ADR-0034).

Its upstream is the immutable source content, which is not derived by
this platform: this lineage, like the PDF one, hangs on the bytes
themselves. That is the whole shape of the fork ADR-0034 describes - two
families sharing a root and meeting nowhere above it. The local
derivation identity is the representation contract: the reader and the
version of the shape it produces, both versioned separately from the
document and both able to read the same bytes differently.

Pure and total: no I/O, no clock, no ambient state. See
``app/domain/artifact_identity`` for the composition contract.
"""

from __future__ import annotations

from app.domain.artifact_identity.artifact_identity_builder import (
    derive_identity,
    source_identity,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)


def workbook_identity(
    *,
    document_id: int,
    content_checksum: str,
    checksum_algorithm: str,
    representation_version: str,
    reader_name: str,
    reader_version: str,
) -> ArtifactIdentity:
    """
    The identity of the representation these bytes produce under this
    representation contract.

    The reader is named because it is a derivation input, not a label:
    the same bytes under the same contract read differently when the
    library that reads them changes, and an upgrade that silently reused
    the old representation would carry a stale reading through every
    stage below.
    """

    return derive_identity(
        ArtifactKind.CANONICAL_SPREADSHEET,
        upstream=source_identity(
            document_id=document_id,
            content_checksum=content_checksum,
            checksum_algorithm=checksum_algorithm,
        ),
        local=(
            ("representation_version", representation_version),
            ("reader_name", reader_name),
            ("reader_version", reader_version),
        ),
    )
