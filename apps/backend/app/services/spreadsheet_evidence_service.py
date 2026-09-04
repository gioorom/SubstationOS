"""
Application service for spreadsheet evidence extraction (ADR-0034).

    Canonical Workbook        (through its own repository port)
        -> Check the version   this extractor understands the recording
        -> Check identity      the workbook describes the document it claims
        -> Execute the rules   a pure domain function
        -> Persist or reuse    through SpreadsheetEvidenceRepository

**Its only input is a canonical workbook.** It has no content port, no
storage-location port, no reader and no spreadsheet library: it could not
reopen the original file if it wanted to, which is the point. It calls no
LLM, writes no Engineering Index record, no graph node, no graph edge and
no entity - a future milestone will decide what these observations
*mean*, with review, and this one deliberately stops short of it.

**The chain stops here.** Nothing in this lineage imports
``engineering_entities``, ``engineering_facts``,
``engineering_semantics``, ``governed_knowledge_graph``, ``human_review``
or the promotion service, and no ``Cable``, ``Circuit``, ``Terminal``,
``From``, ``To`` or ``CONNECTS`` concept is introduced anywhere. A cable
register read by this milestone yields cells containing
designation-shaped text at stated coordinates, and nothing more.

It is the **mirror** of ``engineering_evidence_service``, not a widening
of it: the PDF family's evidence set, provenance and key formula are
untouched, and the two stores never meet.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.domain.artifact_identity.artifact_identity_exceptions import (  # noqa: E501
    InvalidArtifactIdentityError,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
)
from app.domain.canonical_spreadsheet.canonical_workbook_repository import (
    CanonicalWorkbookRepository,
)
from app.domain.engineering_evidence.evidence_models import EvidenceStatus
from app.domain.spreadsheet_evidence.spreadsheet_evidence_exceptions import (
    SpreadsheetEvidenceFailure,
    SpreadsheetEvidenceFailureCode,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_extractor import (
    extract_cell_evidence,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_identity import (
    spreadsheet_evidence_set_identity,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    SpreadsheetEvidenceSet,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_policy import (
    SPREADSHEET_EXTRACTION_POLICY_VERSION,
    SUPPORTED_WORKBOOK_VERSIONS,
    is_supported_workbook_version,
)
from app.domain.spreadsheet_evidence.spreadsheet_evidence_repository import (
    SpreadsheetEvidenceRepository,
)


@dataclass(frozen=True, slots=True)
class SpreadsheetEvidenceExtractionResult:
    """
    What one extraction concluded.

    ``reused`` distinguishes "this workbook was already extracted under
    this policy" from "it was extracted now"; ``rejected_count`` reports
    the candidates the rules decided against, which are returned as
    diagnostics and never stored.
    """

    succeeded: bool
    evidence_set: SpreadsheetEvidenceSet | None = None
    reused: bool = False
    rejected_count: int = 0
    failure: SpreadsheetEvidenceFailure | None = None

    @property
    def found_evidence(self) -> bool:
        """Whether anything persistable was observed. ``False`` is a
        successful outcome, not a failure: a register may simply contain
        nothing these rules recognise."""

        return (
            self.evidence_set is not None
            and not self.evidence_set.is_empty
        )


def extract_workbook_evidence(
    workbook_repository: CanonicalWorkbookRepository,
    evidence_repository: SpreadsheetEvidenceRepository,
    *,
    document_id: int,
    project_id: int | None = None,
    extraction_policy_version: str = SPREADSHEET_EXTRACTION_POLICY_VERSION,
) -> SpreadsheetEvidenceExtractionResult:
    """
    Extract - or re-use - the spreadsheet evidence of one document.

    Checks run in order and the first failure is returned: there is no
    point complaining about a recording's version when there is no
    recording.
    """

    workbook = workbook_repository.find_latest_for_document(document_id)

    if workbook is None:
        return _failed(
            SpreadsheetEvidenceFailureCode.CANONICAL_WORKBOOK_MISSING,
            f"Document '{document_id}' has no canonical workbook; there "
            "is nothing to extract evidence from.",
            detail="Evidence extraction is the step after the workbook "
            "was read. The canonical workbook is its only input - it "
            "never reads the original file.",
        )

    if workbook.document_id != document_id:
        return _failed(
            SpreadsheetEvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The canonical workbook returned for document "
            f"'{document_id}' describes document "
            f"'{workbook.document_id}'.",
            detail="Continuing would attach observations to the wrong "
            "document.",
        )

    if not is_supported_workbook_version(workbook.representation_version):
        return _failed(
            SpreadsheetEvidenceFailureCode.UNSUPPORTED_WORKBOOK_VERSION,
            f"The canonical workbook of document '{document_id}' is "
            f"representation version "
            f"'{workbook.representation_version}', which this extractor "
            "does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_WORKBOOK_VERSIONS))
                + ". A newer recording may record a cell's text "
                "differently, and character offsets taken against the "
                "wrong recording would point at the wrong characters."
            ),
        )

    if workbook.artifact_identity is None:
        return _failed(
            SpreadsheetEvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The canonical workbook of document '{document_id}' was "
            "stored before the derivation identity chain existed.",
            detail="Its provenance cannot be reconstructed, so evidence "
            "read from it could never prove its own reuse is valid. "
            "Re-read the workbook to give it a current identity.",
        )

    # What this stage produces from that workbook under its own
    # extraction policy. Everything further upstream - the reader, its
    # version, the bytes - reaches this digest through the workbook's
    # identity, so this layer names none of them.
    try:
        expected_identity = spreadsheet_evidence_set_identity(
            workbook=ArtifactIdentity(
                value=workbook.artifact_identity,
                kind=ArtifactKind.CANONICAL_SPREADSHEET,
                contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
            ),
            extraction_policy_version=extraction_policy_version,
        )
    except InvalidArtifactIdentityError as error:
        return _failed(
            SpreadsheetEvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The canonical workbook of document '{document_id}' "
            "carries a malformed derivation identity.",
            detail=f"{type(error).__name__}: {error}",
        )

    existing = evidence_repository.find_by_identity(
        document_id, expected_identity.value
    )

    if existing is not None:
        return SpreadsheetEvidenceExtractionResult(
            succeeded=True, evidence_set=existing, reused=True
        )

    try:
        extracted = extract_cell_evidence(
            workbook,
            project_id=project_id,
            extraction_policy_version=extraction_policy_version,
        )
    except Exception as error:  # noqa: BLE001 - see below
        # The extractor is pure and total by design, so reaching here
        # means a rule defect rather than a data condition. Caught
        # anyway: a caller needs one honest answer instead of an
        # exception crossing the boundary, and the cause is carried in
        # ``detail`` rather than swallowed.
        return _failed(
            SpreadsheetEvidenceFailureCode.RULE_EXECUTION_FAILURE,
            f"A rule failed while extracting evidence from document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    rejected = len(extracted.with_status(EvidenceStatus.REJECTED))
    persistable = replace(
        extracted,
        evidence=tuple(
            item for item in extracted.evidence if item.is_persistable
        ),
        artifact_identity=expected_identity.value,
        upstream_identity=workbook.artifact_identity,
    )

    try:
        evidence_repository.save(persistable)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            SpreadsheetEvidenceFailureCode.EVIDENCE_PERSISTENCE_FAILURE,
            f"The spreadsheet evidence set for document "
            f"'{document_id}' was built and could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return SpreadsheetEvidenceExtractionResult(
        succeeded=True,
        evidence_set=persistable,
        reused=False,
        rejected_count=rejected,
    )


def get_spreadsheet_evidence_set(
    evidence_repository: SpreadsheetEvidenceRepository, document_id: int
) -> SpreadsheetEvidenceSet | None:
    """
    The current spreadsheet evidence set of one document.

    ``None`` means no extraction has run. Not an error: most documents
    have not been extracted from, and an empty set would be
    indistinguishable from a register in which nothing was observed.
    """

    return evidence_repository.find_latest_for_document(document_id)


def _failed(
    code: SpreadsheetEvidenceFailureCode,
    message: str,
    *,
    detail: str | None = None,
) -> SpreadsheetEvidenceExtractionResult:
    return SpreadsheetEvidenceExtractionResult(
        succeeded=False,
        failure=SpreadsheetEvidenceFailure(
            code=code, message=message, detail=detail
        ),
    )
