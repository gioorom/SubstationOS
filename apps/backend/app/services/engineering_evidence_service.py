"""
Application service for Engineering Evidence Extraction (EPIC 2,
Milestone 28.1).

    Canonical Text            (27.1, through its own repository port)
        -> Check the version   this extractor understands the segmentation
        -> Check identity      the text describes the document it claims to
        -> Execute the rules   a pure domain function
        -> Validate the set    provenance is exact, values are typed
        -> Persist or reuse    through EngineeringEvidenceRepository

**Its only input is canonical text.** It has no content port, no
storage-location port, no parser and no PDF library: it could not reopen
the original document if it wanted to, which is the point. It calls no
LLM, writes no Engineering Index record and writes no graph node - a
future milestone will decide what these observations *mean*, with review,
and this one deliberately stops short of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.canonical_text.canonical_text_repository import (
    CanonicalTextRepository,
)
from app.domain.engineering_evidence.engineering_evidence_repository import (
    EngineeringEvidenceRepository,
)
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_failures import (
    EvidenceFailure,
    EvidenceFailureCode,
)
from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidenceSet,
    EvidenceStatus,
)
from app.domain.engineering_evidence.evidence_policy import (
    EXTRACTION_POLICY_VERSION,
    SUPPORTED_SEGMENTATION_VERSIONS,
    is_supported_segmentation_version,
)
from app.domain.engineering_evidence.evidence_validation import (
    validate_evidence_set,
)


@dataclass(frozen=True, slots=True)
class EvidenceExtractionResult:
    """
    What one extraction concluded.

    ``reused`` distinguishes "this source was already extracted under
    this policy" from "it was extracted now"; ``rejected_count`` reports
    the candidates the rules decided against, which are returned as
    diagnostics and never stored.
    """

    succeeded: bool
    evidence_set: EngineeringEvidenceSet | None = None
    reused: bool = False
    rejected_count: int = 0
    failure: EvidenceFailure | None = None

    @property
    def found_evidence(self) -> bool:
        """Whether anything persistable was observed. ``False`` is a
        successful outcome, not a failure: a document may simply contain
        nothing these rules recognise."""

        return (
            self.evidence_set is not None
            and not self.evidence_set.is_empty
        )


def extract_document_evidence(
    canonical_text_repository: CanonicalTextRepository,
    evidence_repository: EngineeringEvidenceRepository,
    *,
    document_id: int,
    project_id: int | None = None,
    extraction_policy_version: str = EXTRACTION_POLICY_VERSION,
) -> EvidenceExtractionResult:
    """
    Extract - or re-use - the engineering evidence of one document.

    Checks run in order and the first failure is returned: there is no
    point complaining about a segmentation's version when there is no
    segmentation.
    """

    canonical_text = canonical_text_repository.find_latest_for_document(
        document_id
    )

    if canonical_text is None:
        return _failed(
            EvidenceFailureCode.CANONICAL_TEXT_MISSING,
            f"Document '{document_id}' has no canonical text; there is "
            "nothing to extract evidence from.",
            detail="Evidence extraction is the step after segmentation. "
            "Canonical text is its only input - it never reads the "
            "original document.",
        )

    if canonical_text.document_id != document_id:
        return _failed(
            EvidenceFailureCode.INCONSISTENT_SOURCE_IDENTITY,
            f"The canonical text returned for document '{document_id}' "
            f"describes document '{canonical_text.document_id}'.",
            detail="Continuing would attach observations to the wrong "
            "document.",
        )

    if not is_supported_segmentation_version(
        canonical_text.segmentation_version
    ):
        return _failed(
            EvidenceFailureCode.UNSUPPORTED_CANONICAL_TEXT_VERSION,
            f"The canonical text of document '{document_id}' is "
            f"segmentation version "
            f"'{canonical_text.segmentation_version}', which this "
            "extractor does not understand.",
            detail=(
                "Supported: "
                + ", ".join(sorted(SUPPORTED_SEGMENTATION_VERSIONS))
                + ". A newer segmentation may group tokens differently, "
                "and provenance recorded against the wrong grouping "
                "would point at the wrong characters."
            ),
        )

    existing = evidence_repository.find_for_source(
        document_id,
        canonical_text.content_checksum,
        extraction_policy_version,
    )

    if existing is not None:
        return EvidenceExtractionResult(
            succeeded=True, evidence_set=existing, reused=True
        )

    try:
        extracted = extract_evidence(
            canonical_text,
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
            EvidenceFailureCode.RULE_EXECUTION_FAILURE,
            f"A rule failed while extracting evidence from document "
            f"'{document_id}'.",
            detail=f"{type(error).__name__}: {error}",
        )

    violation = validate_evidence_set(extracted, canonical_text)

    if violation is not None:
        return _failed(
            violation.code, violation.message, detail=violation.detail
        )

    rejected = len(extracted.with_status(EvidenceStatus.REJECTED))
    persistable = EngineeringEvidenceSet(
        document_id=extracted.document_id,
        project_id=extracted.project_id,
        content_checksum=extracted.content_checksum,
        segmentation_version=extracted.segmentation_version,
        extraction_policy_version=extracted.extraction_policy_version,
        evidence=tuple(
            item for item in extracted.evidence if item.is_persistable
        ),
    )

    try:
        evidence_repository.save(persistable)
    except Exception as error:  # noqa: BLE001 - see above
        return _failed(
            EvidenceFailureCode.EVIDENCE_PERSISTENCE_FAILURE,
            f"The evidence set for document '{document_id}' was built "
            "and could not be stored.",
            detail=f"{type(error).__name__}: {error}",
        )

    return EvidenceExtractionResult(
        succeeded=True,
        evidence_set=persistable,
        reused=False,
        rejected_count=rejected,
    )


def get_evidence_set(
    evidence_repository: EngineeringEvidenceRepository, document_id: int
) -> EngineeringEvidenceSet | None:
    """
    The current evidence set of one document - the **only** thing a
    future knowledge-construction milestone should consume.

    ``None`` means no extraction has run. Not an error: most documents
    have not been extracted from, and an empty set would be
    indistinguishable from a document in which nothing was observed.
    """

    return evidence_repository.find_latest_for_document(document_id)


def _failed(
    code: EvidenceFailureCode, message: str, *, detail: str | None = None
) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        succeeded=False,
        failure=EvidenceFailure(code=code, message=message, detail=detail),
    )
