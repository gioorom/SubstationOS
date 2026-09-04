"""
The deterministic identity of one spreadsheet evidence set (ADR-0034).

Its upstream is the canonical workbook it read. That is what closes the
reading question structurally: a different reader, or a different
recording of the same bytes, changes the workbook's identity, so
evidence over the old recording cannot answer for the new one - and this
layer never has to know what a reader or a recording contract is.

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


def spreadsheet_evidence_set_identity(
    *, workbook: ArtifactIdentity, extraction_policy_version: str
) -> ArtifactIdentity:
    """The identity of the evidence this workbook yields under this
    extraction policy."""

    return derive_identity(
        ArtifactKind.SPREADSHEET_EVIDENCE_SET,
        upstream=workbook,
        local=(("extraction_policy_version", extraction_policy_version),),
    )
