"""
The deterministic identity of one engineering fact set (EPIC 32.E2.4).

Its upstream is the entity set it associated. Facts never name the
extraction policy, the segmentation or the representation: those
reach them through the entity set's identity, which is the whole
point of chaining rather than copying.

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

def fact_set_identity(
    *,
    entity_set: ArtifactIdentity,
    fact_policy_version: str,
    fact_contract_version: str,
) -> ArtifactIdentity:
    """The identity of the facts these entities yield under these
    construction rules and this fact contract."""

    return derive_identity(
        ArtifactKind.FACT_SET,
        upstream=entity_set,
        local=(
            ("fact_policy_version", fact_policy_version),
            ("fact_contract_version", fact_contract_version),
        ),
    )
