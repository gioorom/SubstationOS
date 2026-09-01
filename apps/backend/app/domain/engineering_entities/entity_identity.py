"""
The deterministic identity of one engineering entity set (EPIC 32.E2.4).

Its upstream is the evidence set it resolved. Its local derivation
identity is both versions this stage owns: the rules that group
observations, and the contract describing the shape they are grouped
into. They change for different reasons and neither implies the
other, so both are named.

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

def entity_set_identity(
    *,
    evidence_set: ArtifactIdentity,
    resolution_policy_version: str,
    entity_model_version: str,
) -> ArtifactIdentity:
    """The identity of the entities this evidence yields under these
    resolution rules and this entity contract."""

    return derive_identity(
        ArtifactKind.ENTITY_SET,
        upstream=evidence_set,
        local=(
            ("resolution_policy_version", resolution_policy_version),
            ("entity_model_version", entity_model_version),
        ),
    )
