"""
The deterministic identity of one engineering semantic set (EPIC 32.E2.4).

Its upstream is the fact set it interpreted. The end of the
deterministic chain: everything a statement rests on is reachable
from this identity, one link at a time.

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

def semantic_set_identity(
    *,
    fact_set: ArtifactIdentity,
    semantic_policy_version: str,
    semantic_contract_version: str,
) -> ArtifactIdentity:
    """The identity of the statements these facts yield under these
    semantic rules and this semantic contract."""

    return derive_identity(
        ArtifactKind.SEMANTIC_SET,
        upstream=fact_set,
        local=(
            ("semantic_policy_version", semantic_policy_version),
            ("semantic_contract_version", semantic_contract_version),
        ),
    )
