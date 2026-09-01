"""
The deterministic identity of one engineering evidence set (EPIC 32.E2.4).

Its upstream is the canonical text it read. That is what closes the
segmentation question structurally: a re-segmentation changes the
text's identity, so evidence over the old grouping cannot answer for
the new one - and this layer never has to know what a segmentation
version is.

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

def evidence_set_identity(
    *, canonical_text: ArtifactIdentity, extraction_policy_version: str
) -> ArtifactIdentity:
    """The identity of the evidence this text yields under this
    extraction policy."""

    return derive_identity(
        ArtifactKind.EVIDENCE_SET,
        upstream=canonical_text,
        local=(("extraction_policy_version", extraction_policy_version),),
    )
