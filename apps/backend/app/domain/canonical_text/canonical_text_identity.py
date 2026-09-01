"""
The deterministic identity of one canonical text segmentation (EPIC 32.E2.4).

Its upstream is the canonical representation it segmented - not the
source bytes. The same bytes read under a raised representation
contract are a different representation, and a segmentation over one
must never answer for the other.

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

def segmentation_identity(
    *, representation: ArtifactIdentity, segmentation_version: str
) -> ArtifactIdentity:
    """The identity of the segmentation this representation produces
    under this segmentation contract."""

    return derive_identity(
        ArtifactKind.CANONICAL_TEXT,
        upstream=representation,
        local=(("segmentation_version", segmentation_version),),
    )
