"""
Document-lookup composition (Milestone 23B.1) - the ``Composition`` stage
for the first ``DETERMINISTIC_RETRIEVAL`` response. Builds every
``EngineeringResponseSection``, ``EngineeringWarning`` and
``EngineeringUncertainty`` declaration from an already-executed
``DocumentRetrievalResult``.

**No AI usage of any kind, and nothing invented.** Every line of every
section restates a field a repository already holds: a document's stored
title, format, category and revision, the identifiers its Engineering
Index entries recorded, the pages or locators those entries point at, and
the relevance this system itself computed from a fixed documented weight
table. Nothing summarizes a document, judges its quality, or claims
anything about its contents.

The section *shape* is exactly the shape Milestone 18 fixed: the same
nine section types, in the same canonical order, with sections that have
nothing to contribute constructed disabled and empty. A consumer built
for a knowledge-query response therefore renders a document-lookup
response without special-casing it.

``SUMMARY``/``TECHNICAL_EXPLANATION``/``ASSUMPTIONS``/``NEXT_ACTIONS``
stay disabled and empty here for the same reason they do for an LLM
response: this builder has no honest basis to write them. Suggesting
"open drawing 3 next" would be advice, not retrieved data.

O(n) in the number of retrieved documents and their recorded mentions.
"""

from __future__ import annotations

from app.domain.engineering_index.document_retrieval_models import (
    DocumentReference,
    DocumentRetrievalResult,
)
from app.domain.engineering_response.engineering_response_composition import (
    build_section,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseCompositionResult,
    EngineeringResponseSection,
    EngineeringResponseStatus,
    EngineeringSectionType,
    EngineeringUncertainty,
    EngineeringUncertaintyLevel,
    EngineeringWarning,
    EngineeringWarningCategory,
)
from app.domain.engineering_response.engineering_response_policy import (
    overall_uncertainty_from,
)


def _determine_status(
    result: DocumentRetrievalResult,
) -> EngineeringResponseStatus:
    """``EMPTY`` when nothing matched, ``PARTIAL`` when the answer is
    knowably incomplete (results truncated by the limit, or a matched
    document whose metadata could not be read), ``COMPLETE`` otherwise.
    ``UNSUPPORTED`` never occurs: there is no provider here that could
    return content this system does not interpret."""

    if not result.references:
        return EngineeringResponseStatus.EMPTY

    if (
        result.metadata.truncated_by_limit
        or result.metadata.documents_missing_metadata
    ):
        return EngineeringResponseStatus.PARTIAL

    return EngineeringResponseStatus.COMPLETE


def _describe(reference: DocumentReference) -> str:
    """One document, described only by fields that exist. An unavailable
    field is reported as unavailable rather than omitted silently or
    filled in."""

    parts = [f"document_id={reference.document_id}"]

    if reference.metadata_available:
        parts.append(f"title={reference.title}")
        parts.append(f"type={reference.document_format}")
        parts.append(f"category={reference.document_category}")
        parts.append(f"revision={reference.revision}")
    else:
        parts.append("metadata unavailable")

    parts.append(f"relevance={reference.relevance.total:.2f}")
    parts.append(f"mentions={reference.mention_count}")

    if reference.matched_identifiers:
        parts.append(
            f"matched={', '.join(reference.matched_identifiers)}"
        )

    pages = reference.page_references
    if pages:
        parts.append(f"pages={', '.join(str(page) for page in pages)}")

    return "; ".join(parts)


def _build_direct_answer_section(
    result: DocumentRetrievalResult,
) -> EngineeringResponseSection:
    body = tuple(_describe(reference) for reference in result.references)

    return build_section(
        EngineeringSectionType.DIRECT_ANSWER, "Matching Documents", body
    )


def _build_references_section(
    result: DocumentRetrievalResult,
) -> EngineeringResponseSection:
    """The recorded mentions themselves - the navigable evidence behind
    each document, one line per mention."""

    body = tuple(
        f"document_id={reference.document_id}: "
        f"{mention.identifier} ({mention.kind.value}) at "
        f"{mention.locator_kind.value}"
        + (f" {mention.locator_value}" if mention.locator_value else "")
        for reference in result.references
        for mention in reference.mentions
    )

    return build_section(
        EngineeringSectionType.REFERENCES, "Document Evidence", body
    )


def _build_warnings(
    result: DocumentRetrievalResult,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringWarning, ...]:
    warnings: list[EngineeringWarning] = []

    if status is EngineeringResponseStatus.EMPTY:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.INSUFFICIENT_EVIDENCE,
                message="No document in this project's Engineering Index "
                "mentions any of the requested identifiers.",
            )
        )

    if result.metadata.truncated_by_limit:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.LIMITED_RESPONSE,
                message=(
                    f"{result.statistics.matched_document_count} documents "
                    f"matched; the "
                    f"{result.statistics.returned_document_count} most "
                    "relevant were returned."
                ),
            )
        )

    if result.metadata.documents_missing_metadata:
        warnings.append(
            EngineeringWarning(
                category=EngineeringWarningCategory.PARTIAL_CONTEXT,
                message=(
                    "Document metadata was unavailable for "
                    f"{len(result.metadata.documents_missing_metadata)} "
                    "matched document(s); only their recorded mentions are "
                    "reported."
                ),
            )
        )

    return tuple(warnings)


def _build_warnings_section(
    warnings: tuple[EngineeringWarning, ...],
) -> EngineeringResponseSection:
    body = tuple(
        f"[{warning.category.value}] {warning.message}"
        for warning in warnings
    )

    return build_section(EngineeringSectionType.WARNINGS, "Warnings", body)


def _build_limitations_section(
    result: DocumentRetrievalResult,
) -> EngineeringResponseSection:
    lines: list[str] = [
        "This answer reports which documents mention the requested "
        "identifiers. It does not read, interpret or summarize their "
        "contents.",
    ]

    if result.metadata.truncated_by_limit:
        lines.append(
            "More documents matched than the requested limit allowed; the "
            "list is not exhaustive."
        )

    if result.metadata.documents_missing_metadata:
        lines.append(
            "Some matched documents could no longer be read from the "
            "document repository; their title, type and revision are "
            "unknown."
        )

    return build_section(
        EngineeringSectionType.LIMITATIONS, "Limitations", tuple(lines)
    )


def _build_uncertainties(
    result: DocumentRetrievalResult,
    status: EngineeringResponseStatus,
) -> tuple[EngineeringUncertainty, ...]:
    uncertainties: list[EngineeringUncertainty] = []

    if status is EngineeringResponseStatus.EMPTY:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.HIGH,
                reasons=(
                    "No document mentions any of the requested "
                    "identifiers. The equipment may be undocumented, or "
                    "the documents that cover it may not be indexed yet.",
                ),
            )
        )

    if result.metadata.truncated_by_limit:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.MEDIUM,
                reasons=(
                    "The document list was truncated by the requested "
                    "limit, so a relevant document may be missing from it.",
                ),
            )
        )

    if result.metadata.documents_missing_metadata:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.MEDIUM,
                reasons=(
                    "Metadata for one or more matched documents was "
                    "unavailable, so they cannot be identified by title or "
                    "revision.",
                ),
            )
        )

    if not uncertainties:
        uncertainties.append(
            EngineeringUncertainty(
                level=EngineeringUncertaintyLevel.LOW,
                reasons=(
                    "Every matched document was resolved from governed "
                    "repository state, with no interpretation applied.",
                ),
            )
        )

    return tuple(uncertainties)


def compose_document_lookup_response(
    result: DocumentRetrievalResult,
) -> EngineeringResponseCompositionResult:
    status = _determine_status(result)
    warnings = _build_warnings(result, status)
    uncertainties = _build_uncertainties(result, status)

    summary_section = build_section(EngineeringSectionType.SUMMARY, "Summary", ())
    direct_answer_section = _build_direct_answer_section(result)
    technical_explanation_section = build_section(
        EngineeringSectionType.TECHNICAL_EXPLANATION,
        "Technical Explanation",
        (),
    )
    assumptions_section = build_section(
        EngineeringSectionType.ASSUMPTIONS, "Assumptions", ()
    )
    warnings_section = _build_warnings_section(warnings)
    limitations_section = _build_limitations_section(result)
    next_actions_section = build_section(
        EngineeringSectionType.NEXT_ACTIONS, "Next Actions", ()
    )
    references_section = _build_references_section(result)
    unknown_section = build_section(
        EngineeringSectionType.UNKNOWN, "Unrecognized Content", ()
    )

    return EngineeringResponseCompositionResult(
        sections=(
            summary_section,
            direct_answer_section,
            technical_explanation_section,
            assumptions_section,
            warnings_section,
            limitations_section,
            next_actions_section,
            references_section,
            unknown_section,
        ),
        summary=summary_section,
        direct_answer=direct_answer_section,
        # Graph evidence, deliberately empty: this workflow retrieves
        # documents, not graph facts. The documents live in
        # ``document_references``.
        references=(),
        warnings=warnings,
        uncertainties=uncertainties,
        overall_uncertainty=overall_uncertainty_from(uncertainties),
        status=status,
        document_references=result.references,
    )
