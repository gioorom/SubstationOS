"""
The document format classifier (Milestone 25.2) - the **one** place a
document's format is decided, used by both upload and ingestion.

Pure and deterministic: given the same leading bytes, MIME type and
filename, it always returns the same classification. No I/O, no wall
clock, no heuristics, no scoring, and no AI of any kind. It reads at most
``SIGNATURE_PREFIX_LENGTH`` bytes - never a meaningful amount of a
document, and never its contents in any semantic sense.

## The rule

Evidence is gathered from all three sources, then resolved in descending
order of trust:

1. **Content signature** - the file's own leading bytes. The only
   evidence the file itself supplies, and the only one a rename cannot
   change.
2. **Declared MIME type** - what the uploading client claimed.
3. **Filename extension** - a naming convention, not a fact.

**A readable signature decides, full stop.** If the bytes say PDF and the
filename says ``.dwg``, the format is PDF: the bytes are the document and
the name is a label somebody typed. The disagreement is not discarded -
it is recorded in ``evidence`` and surfaced by
``disagreeing_evidence``, because a file whose name contradicts its
contents is worth an engineer's attention even when the classification
itself is certain.

**Without a signature, two weak sources that disagree deadlock.** MIME
and extension are both claims *about* the file rather than facts *from*
it, so neither can arbitrate the other. That yields ``CONFLICTING``, and
the caller decides what to do - choosing one would be exactly the
arbitrary classification this milestone forbids.

**A signature that identifies only a container abstains.** ``xlsx`` and
``docx`` are both ZIP archives, so the ZIP header says "this is a ZIP",
not "this is a spreadsheet". The classifier records that it looked and
had no opinion, and lets the weaker sources decide - which is honest, and
different from having found nothing at all.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import (
    ClassifiedFormat,
    FormatClassification,
    FormatClassificationOutcome,
    FormatEvidence,
    FormatEvidenceKind,
)
from app.domain.document_identity.format_signatures import (
    AMBIGUOUS_SIGNATURES,
    CONTENT_SIGNATURES,
    FILENAME_EXTENSIONS,
    MIME_TYPES,
)


def _signature_evidence(content_prefix: bytes | None) -> FormatEvidence:
    """Longest-first, so a longer and more specific prefix always wins
    over a shorter one that happens to also match."""

    if not content_prefix:
        return FormatEvidence(
            kind=FormatEvidenceKind.CONTENT_SIGNATURE,
            detail="no content was readable",
        )

    for prefix, detected in sorted(
        CONTENT_SIGNATURES, key=lambda entry: len(entry[0]), reverse=True
    ):
        if content_prefix.startswith(prefix):
            return FormatEvidence(
                kind=FormatEvidenceKind.CONTENT_SIGNATURE,
                detail=f"leading bytes matched {prefix!r}",
                detected_format=detected,
            )

    for prefix, explanation in AMBIGUOUS_SIGNATURES:
        if content_prefix.startswith(prefix):
            return FormatEvidence(
                kind=FormatEvidenceKind.CONTENT_SIGNATURE,
                detail=explanation,
            )

    return FormatEvidence(
        kind=FormatEvidenceKind.CONTENT_SIGNATURE,
        detail="leading bytes matched no known signature",
    )


def _mime_evidence(declared_mime_type: str | None) -> FormatEvidence:
    if not declared_mime_type or not declared_mime_type.strip():
        return FormatEvidence(
            kind=FormatEvidenceKind.DECLARED_MIME_TYPE,
            detail="no MIME type was declared",
        )

    # A declared type may carry parameters ("text/plain; charset=utf-8").
    normalized = declared_mime_type.split(";")[0].strip().lower()
    detected = MIME_TYPES.get(normalized)

    return FormatEvidence(
        kind=FormatEvidenceKind.DECLARED_MIME_TYPE,
        detail=(
            f"declared '{normalized}'"
            if detected is not None
            else f"declared '{normalized}', which maps to no known format"
        ),
        detected_format=detected,
    )


def _extension_evidence(filename: str | None) -> FormatEvidence:
    if not filename or "." not in filename:
        return FormatEvidence(
            kind=FormatEvidenceKind.FILENAME_EXTENSION,
            detail="the filename carries no extension",
        )

    extension = filename[filename.rfind(".") :].lower()
    detected = FILENAME_EXTENSIONS.get(extension)

    return FormatEvidence(
        kind=FormatEvidenceKind.FILENAME_EXTENSION,
        detail=(
            f"extension '{extension}'"
            if detected is not None
            else f"extension '{extension}', which maps to no known format"
        ),
        detected_format=detected,
    )


def classify_document_format(
    *,
    content_prefix: bytes | None = None,
    declared_mime_type: str | None = None,
    filename: str | None = None,
) -> FormatClassification:
    """
    The one entry point. ``content_prefix`` is the document's leading
    bytes, read through ``DocumentContentPort`` by whichever caller has
    one - this function performs no I/O of its own, so its determinism is
    verifiable.
    """

    signature = _signature_evidence(content_prefix)
    mime = _mime_evidence(declared_mime_type)
    extension = _extension_evidence(filename)
    evidence = (signature, mime, extension)

    if signature.has_opinion:
        return FormatClassification(
            outcome=FormatClassificationOutcome.CLASSIFIED,
            detected_format=signature.detected_format,
            decided_by=FormatEvidenceKind.CONTENT_SIGNATURE,
            evidence=evidence,
        )

    weaker = tuple(
        candidate for candidate in (mime, extension) if candidate.has_opinion
    )

    if not weaker:
        return FormatClassification(
            outcome=FormatClassificationOutcome.UNKNOWN,
            detected_format=None,
            decided_by=None,
            evidence=evidence,
        )

    opinions = {candidate.detected_format for candidate in weaker}

    if len(opinions) > 1:
        # No signature to arbitrate, and two claims *about* the file that
        # disagree. Neither outranks the other, so nothing here can decide.
        return FormatClassification(
            outcome=FormatClassificationOutcome.CONFLICTING,
            detected_format=None,
            decided_by=None,
            evidence=evidence,
        )

    decided = weaker[0]

    return FormatClassification(
        outcome=FormatClassificationOutcome.CLASSIFIED,
        detected_format=decided.detected_format,
        decided_by=decided.kind,
        evidence=evidence,
    )
