"""
Deterministic backfill of document formats (EPIC 2, Milestone 25.2).

Every document uploaded before this milestone was stored as ``other``,
because the upload endpoint never set a format at all. Those rows stay
perfectly readable - ``other`` means *unclassified*, which is exactly
what they are - but a document whose bytes plainly say PDF is better
recorded as a PDF, and this is how that correction is made.

**Planning and applying are separate calls.** ``plan_format_backfill``
reads bytes and decides; ``apply_format_backfill`` writes. Nothing is
written by looking, so an operator can run the plan against production,
read the report, and only then decide - and a read of a document never
rewrites it (the brief's rule, and the reason ``record_format`` exists on
its own narrow port).

**Deterministic.** The same documents over the same bytes produce the
same decisions in the same order, every run. It uses the same classifier
as upload and ingestion - there is one format rule in this system - and
so it can conclude nothing they could not.

It never guesses. A document the classifier cannot name is left as
``other`` and reported as such; a format is never chosen to make a row
look finished.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_format import (
    FormatClassificationOutcome,
)
from app.domain.document_identity.document_format_registry import (
    DocumentFormatRegistryPort,
    RegisteredDocumentFormat,
)
from app.services.document_identity_service import resolve_document_identity

# The stored value that means "nobody has classified this yet". The
# backfill considers only these rows: a document already recorded as a
# PDF is not re-examined, because overwriting a format somebody may have
# set deliberately is not this command's job.
UNCLASSIFIED_FORMAT = "other"


class BackfillAction(str, Enum):
    """What the backfill decided for one document.

    Four outcomes rather than "changed / unchanged", because the three
    ways of staying unchanged send an operator somewhere different: the
    bytes are missing, the bytes are unreadable-or-unrecognisable, or the
    evidence contradicts itself."""

    RECLASSIFIED = "reclassified"
    LEFT_UNCLASSIFIED = "left_unclassified"
    CONTENT_UNAVAILABLE = "content_unavailable"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


@dataclass(frozen=True, slots=True)
class BackfillDecision:
    """One document's decision. ``detected_format`` is populated only for
    ``RECLASSIFIED`` - the other three actions have no format to offer,
    and reporting one would suggest a conclusion nobody reached."""

    document_id: int
    filename: str
    stored_format: str
    action: BackfillAction
    detected_format: str | None = None
    decided_by: str | None = None
    detail: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.action is BackfillAction.RECLASSIFIED


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    """What a run would do, before it does any of it."""

    decisions: tuple[BackfillDecision, ...]

    @property
    def actionable(self) -> tuple[BackfillDecision, ...]:
        return tuple(
            decision for decision in self.decisions if decision.is_actionable
        )

    def count_by_action(self) -> dict[str, int]:
        counts: dict[str, int] = {action.value: 0 for action in BackfillAction}

        for decision in self.decisions:
            counts[decision.action.value] += 1

        return counts


def plan_format_backfill(
    registry: DocumentFormatRegistryPort,
    content_port: DocumentContentPort,
    *,
    stored_format: str = UNCLASSIFIED_FORMAT,
) -> BackfillPlan:
    """Examines every document recorded under ``stored_format`` and
    decides what each one's format should be. **Writes nothing.**"""

    return BackfillPlan(
        decisions=tuple(
            _decide(content_port, document)
            for document in registry.list_by_stored_format(stored_format)
        )
    )


def apply_format_backfill(
    registry: DocumentFormatRegistryPort, plan: BackfillPlan
) -> tuple[BackfillDecision, ...]:
    """
    Records the format of every document the plan reclassified, and
    returns exactly those decisions.

    Documents the plan left alone are not touched - not rewritten with
    the value they already hold, not stamped with a "checked" marker.
    An untouched row keeps its own history.
    """

    applied = plan.actionable

    for decision in applied:
        registry.record_format(decision.document_id, decision.detected_format)

    return applied


def _decide(
    content_port: DocumentContentPort, document: RegisteredDocumentFormat
) -> BackfillDecision:
    identity = resolve_document_identity(
        content_port,
        storage_reference=document.storage_reference,
        filename=document.filename,
    )

    if not identity.content.resolved:
        # The bytes could not be read at all. The classifier may still
        # have an opinion from the filename, but acting on a filename
        # alone for a document nobody can open would record a format for
        # a file that may no longer be there.
        return _decision(
            document,
            BackfillAction.CONTENT_UNAVAILABLE,
            detail=identity.content.detail or "",
        )

    classification = identity.format

    if classification.outcome is FormatClassificationOutcome.CONFLICTING:
        return _decision(
            document,
            BackfillAction.CONFLICTING_EVIDENCE,
            detail=_evidence_detail(classification),
        )

    if classification.outcome is FormatClassificationOutcome.UNKNOWN:
        return _decision(
            document,
            BackfillAction.LEFT_UNCLASSIFIED,
            detail=_evidence_detail(classification),
        )

    return _decision(
        document,
        BackfillAction.RECLASSIFIED,
        detected_format=classification.detected_format.value,
        decided_by=classification.decided_by.value,
        detail=_evidence_detail(classification),
    )


def _decision(
    document: RegisteredDocumentFormat,
    action: BackfillAction,
    *,
    detected_format: str | None = None,
    decided_by: str | None = None,
    detail: str = "",
) -> BackfillDecision:
    return BackfillDecision(
        document_id=document.document_id,
        filename=document.filename,
        stored_format=document.stored_format,
        action=action,
        detected_format=detected_format,
        decided_by=decided_by,
        detail=detail,
    )


def _evidence_detail(classification) -> str:
    return "; ".join(
        f"{evidence.kind.value}: {evidence.detail}"
        for evidence in classification.evidence
    )
