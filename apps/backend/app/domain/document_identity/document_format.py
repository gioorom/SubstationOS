"""
The document format vocabulary and the evidence a classification rests on
(EPIC 2, Milestone 25.2).

``ClassifiedFormat`` is this domain's own restatement of the persistence
layer's ``DocumentFormat``, value-for-value - never an import of it
(CLAUDE.md's Dependency Rule: the domain depends on nothing). A test
asserts the two value sets agree, so a format added to one cannot
silently go missing from the other. This is the same "domain owns its own
restatement, agreement asserted by test" pattern Engineering Response
already established for ``EngineeringSourceFinishReason``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClassifiedFormat(str, Enum):
    """
    Every document format this system recognises.

    ``OTHER`` means **unclassified**, not "examined and found unusable" -
    it is what a document carries when nothing has determined its format.
    Milestone 25.1 established that distinction and it holds here: a
    classifier that could not decide reports ``UNKNOWN``, which is a
    different and honest state from asserting ``OTHER``.
    """

    PDF = "pdf"
    DWG = "dwg"
    DXF = "dxf"
    MODEL_3D = "model_3d"
    XLSX = "xlsx"
    DOCX = "docx"
    IMAGE = "image"
    OTHER = "other"


class FormatEvidenceKind(str, Enum):
    """
    Where one piece of format evidence came from, in descending order of
    trust.

    ``CONTENT_SIGNATURE`` reads the file's own leading bytes - the only
    evidence the file itself supplies, and the only one a rename cannot
    change. ``DECLARED_MIME_TYPE`` is what the uploading client claimed.
    ``FILENAME_EXTENSION`` is the weakest: it is a naming convention, not
    a fact about the bytes.
    """

    CONTENT_SIGNATURE = "content_signature"
    DECLARED_MIME_TYPE = "declared_mime_type"
    FILENAME_EXTENSION = "filename_extension"


# Descending trust. The classifier walks this order and the first kind
# with an opinion decides - see ``format_classifier.py`` for the full rule
# and why a disagreement below the signature is recorded rather than
# fatal.
EVIDENCE_TRUST_ORDER: tuple[FormatEvidenceKind, ...] = (
    FormatEvidenceKind.CONTENT_SIGNATURE,
    FormatEvidenceKind.DECLARED_MIME_TYPE,
    FormatEvidenceKind.FILENAME_EXTENSION,
)


class FormatClassificationOutcome(str, Enum):
    """
    Whether the format could be determined at all.

    ``CONFLICTING`` is reserved for a genuine deadlock: no content
    signature was readable, and the two weaker sources disagree with
    nothing authoritative to arbitrate between them. Picking one would be
    exactly the arbitrary classification this milestone forbids.
    """

    CLASSIFIED = "classified"
    UNKNOWN = "unknown"
    CONFLICTING = "conflicting"


@dataclass(frozen=True, slots=True)
class FormatEvidence:
    """
    One source's opinion about a document's format.

    ``detected_format`` is ``None`` when the source had **no opinion** -
    an absent MIME type, an unrecognised extension, or a signature that
    identifies a container shared by several formats. That is deliberately
    different from an opinion that happens to disagree: silence is not
    disagreement.

    ``detail`` records what was actually observed ("%PDF-", ".dwg",
    "application/pdf"), so a classification explains itself without the
    file being re-read.
    """

    kind: FormatEvidenceKind
    detail: str
    detected_format: ClassifiedFormat | None = None

    @property
    def has_opinion(self) -> bool:
        return self.detected_format is not None


@dataclass(frozen=True, slots=True)
class FormatClassification:
    """
    The full, auditable result of classifying one document.

    ``evidence`` is carried in **every** outcome, including failures: when
    the classifier declines, an engineer needs to see what each source
    said in order to understand why. A refusal that reported nothing would
    be indistinguishable from a bug.
    """

    outcome: FormatClassificationOutcome
    detected_format: ClassifiedFormat | None
    decided_by: FormatEvidenceKind | None
    evidence: tuple[FormatEvidence, ...]

    @property
    def is_classified(self) -> bool:
        return self.outcome is FormatClassificationOutcome.CLASSIFIED

    @property
    def disagreeing_evidence(self) -> tuple[FormatEvidence, ...]:
        """Evidence that had an opinion and was overruled by a stronger
        source. Not a failure - the bytes outrank a filename - but a real
        signal that a file may have been renamed, and worth surfacing."""

        if self.detected_format is None:
            return ()

        return tuple(
            evidence
            for evidence in self.evidence
            if evidence.has_opinion
            and evidence.detected_format is not self.detected_format
        )
