"""
The deterministic identity of one canonical representation (EPIC 32.E2.4).

Its upstream is the immutable source content, which is not derived
by this platform: the chain hangs on the bytes themselves. The local
derivation identity is the representation contract - the parser and
the normalisation it applies, which are versioned separately from
the document and can read the same bytes differently.

Pure and total: no I/O, no clock, no ambient state. See
``app/domain/artifact_identity`` for the composition contract.
"""

from __future__ import annotations

from app.domain.artifact_identity.artifact_identity_builder import (
    derive_identity,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)

from app.domain.artifact_identity.artifact_identity_builder import (
    source_identity,
)


def representation_identity(
    *,
    document_id: int,
    content_checksum: str,
    checksum_algorithm: str,
    representation_version: str,
    parser_name: str,
    parser_version: str,
) -> ArtifactIdentity:
    """
    The identity of the representation these bytes produce under this
    representation contract.

    The parser is named because it is a derivation input, not a label:
    the same bytes under the same contract read differently when the
    library that reads them changes, and an upgrade that silently reused
    the old representation would carry a stale reading through every
    stage below.
    """

    return derive_identity(
        ArtifactKind.CANONICAL_PDF,
        upstream=source_identity(
            document_id=document_id,
            content_checksum=content_checksum,
            checksum_algorithm=checksum_algorithm,
        ),
        local=(
            ("representation_version", representation_version),
            ("parser_name", parser_name),
            ("parser_version", parser_version),
        ),
    )
