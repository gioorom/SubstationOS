from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.engineering_index.document_retrieval_models import (
    DocumentMentionReference,
    DocumentReference,
    DocumentRelevance,
    DocumentRelevanceCategory,
    DocumentRelevanceComponent,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringEvidenceReference,
    EngineeringResponse,
    EngineeringResponseMetadata,
    EngineeringResponseOrigin,
    EngineeringResponseSection,
    EngineeringResponseStatistics,
    EngineeringResponseStatus,
    EngineeringResponseVersion,
    EngineeringSectionType,
    EngineeringUncertainty,
    EngineeringUncertaintyLevel,
    EngineeringWarning,
    EngineeringWarningCategory,
    ComparisonAssessment,
    ComparisonOutcome,
    VerificationAssessment,
    VerificationOutcome,
)
from app.schemas.context_builder import ContextPackageRead, context_package_from_schema
from app.schemas.llm_provider import (
    LLMResponseEnvelopeRead,
    llm_response_envelope_from_schema,
)
from app.schemas.prompt_builder import PromptPackageRead, prompt_package_from_schema

# --- Request -----------------------------------------------------------


class EngineeringResponseBuildRequestBody(BaseModel):
    """
    An Engineering Response build request. ``project_id`` is
    deliberately absent - the path's own ``{project_id}`` is
    authoritative, matching every other governed router's convention.
    ``context_package``/``prompt_package`` are exactly the objects the
    prior ``/context-builder/build``/``/prompt-builder/build`` calls
    returned; ``llm_response_envelope`` is exactly the ``envelope``
    field a prior ``/llm/invoke`` call returned. This endpoint performs
    no AI invocation of its own - it never calls Context Builder,
    Prompt Builder, or the LLM Invocation Runtime itself.
    """

    context_package: ContextPackageRead
    prompt_package: PromptPackageRead
    llm_response_envelope: LLMResponseEnvelopeRead


# --- Response ------------------------------------------------------------


class EngineeringResponseSectionRead(BaseModel):
    section_type: EngineeringSectionType
    title: str
    body: list[str]
    sequence: int
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class EngineeringEvidenceReferenceRead(BaseModel):
    candidate_id: str
    graph_node_ids: list[str]
    graph_relationship_ids: list[str]

    model_config = ConfigDict(from_attributes=True)


class DocumentRelevanceComponentRead(BaseModel):
    category: DocumentRelevanceCategory
    weight: float
    detail: str

    model_config = ConfigDict(from_attributes=True)


class DocumentRelevanceRead(BaseModel):
    total: float
    components: list[DocumentRelevanceComponentRead]

    model_config = ConfigDict(from_attributes=True)


class DocumentMentionReferenceRead(BaseModel):
    entry_id: int | None
    kind: EngineeringIndexEntryKind
    identifier: str
    locator_kind: IndexEntryLocatorKind
    locator_value: str | None
    label: str | None
    page: int | None

    model_config = ConfigDict(from_attributes=True)


class DocumentReferenceRead(BaseModel):
    """
    One retrieved document, exposed with exactly the metadata a repository
    already holds. Every metadata field is nullable because an Engineering
    Index entry may outlive the document row it points at; a ``null``
    title means "unknown", never a placeholder.
    """

    document_id: int
    title: str | None
    document_format: str | None
    document_category: str | None
    revision: str | None
    metadata_available: bool
    relevance: DocumentRelevanceRead
    matched_identifiers: list[str]
    matched_terms: list[str]
    mentions: list[DocumentMentionReferenceRead]
    mention_count: int
    page_references: list[int]

    model_config = ConfigDict(from_attributes=True)


class VerificationAssessmentRead(BaseModel):
    """
    The machine-readable verdict of a verification. ``outcome`` is
    ``null`` when the model did not open its answer with one of the four
    declared verdict tokens - never a verdict inferred from its prose.

    ``evidence_bounded`` marks the one case where the builder overrides
    the model: with no retrieved evidence the outcome is
    ``insufficient_evidence`` whatever was written, because nothing
    existed to support or contradict the statement with.
    """

    outcome: VerificationOutcome | None
    stated_by_model: bool
    evidence_bounded: bool
    evidence_reference_count: int

    model_config = ConfigDict(from_attributes=True)


class ComparisonAssessmentRead(BaseModel):
    """
    The machine-readable outcome of a comparison. ``outcome`` is ``null``
    when the model did not open its answer with one of the three declared
    outcome tokens - never one inferred from its prose.

    ``evidence_bounded`` marks the structural override: when either side
    retrieved no evidence the outcome is ``insufficient_evidence``
    whatever was written, because a missing side is a gap in the project's
    reviewed knowledge and can never honestly become a difference.

    There are deliberately no structured ADDED/REMOVED/MODIFIED/UNCHANGED
    findings here - see ``ComparisonAssessment``'s own docstring.
    """

    outcome: ComparisonOutcome | None
    stated_by_model: bool
    evidence_bounded: bool
    left_evidence_count: int
    right_evidence_count: int

    model_config = ConfigDict(from_attributes=True)


class EngineeringWarningRead(BaseModel):
    category: EngineeringWarningCategory
    message: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringUncertaintyRead(BaseModel):
    level: EngineeringUncertaintyLevel
    reasons: list[str]

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseMetadataRead(BaseModel):
    engineering_response_version: str
    response_policy_version: str
    assembled_at: datetime
    project_id: int
    # Null for a DETERMINISTIC_RETRIEVAL response: no provider and no
    # model were involved (see EngineeringResponseOrigin).
    provider_id: str | None
    configured_model_identifier: str | None
    returned_model_identifier: str | None
    request_correlation_id: str
    prompt_package_version: str | None
    context_builder_version: str | None
    prompt_builder_version: str | None
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseStatisticsRead(BaseModel):
    section_count: int
    enabled_section_count: int
    disabled_section_count: int
    warning_count: int
    uncertainty_count: int
    reference_count: int
    character_count: int
    document_reference_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseVersionRead(BaseModel):
    engineering_response_version: str
    response_policy_version: str
    prompt_builder_version: str | None
    context_builder_version: str | None
    request_preparation_policy_version: str | None
    runtime_version: str | None
    package_version: str
    document_retrieval_version: str | None = None
    document_relevance_policy_version: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseRead(BaseModel):
    """
    Deliberately exposes only strongly typed sections and supporting
    objects - no provider SDK response, no ``LLMResponseEnvelope``, no
    raw prompt or response string of any kind. The canonical output
    contract of the engineering answer layer.

    ``origin`` tells a client whether a model was involved at all:
    ``references`` carries graph evidence for an LLM-produced answer,
    ``document_references`` carries document evidence for a deterministic
    document lookup, and the two are never conflated.
    """

    project_id: int
    status: EngineeringResponseStatus
    origin: EngineeringResponseOrigin = (
        EngineeringResponseOrigin.LLM_INVOCATION
    )
    sections: list[EngineeringResponseSectionRead]
    summary: EngineeringResponseSectionRead
    direct_answer: EngineeringResponseSectionRead
    references: list[EngineeringEvidenceReferenceRead]
    document_references: list[DocumentReferenceRead] = []
    verification: VerificationAssessmentRead | None = None
    comparison: ComparisonAssessmentRead | None = None
    warnings: list[EngineeringWarningRead]
    uncertainties: list[EngineeringUncertaintyRead]
    overall_uncertainty: EngineeringUncertaintyLevel
    metadata: EngineeringResponseMetadataRead
    statistics: EngineeringResponseStatisticsRead
    version: EngineeringResponseVersionRead

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class EngineeringResponseBuilderResultRead(BaseModel):
    project_id: int
    response: EngineeringResponseRead
    validation: EngineeringResponseValidationResultRead

    model_config = ConfigDict(from_attributes=True)


# --- Reconstruction (Engineering Session's own input shape) ---------------
#
# Engineering Session (Milestone 19) owns EngineeringResponse objects
# directly and needs to reconstruct one from its own API response shape
# when appending it to a session - the same "reuse the upstream
# response shape as the next stage's request shape" pattern
# ``prompt_package_from_schema``/``context_package_from_schema`` already
# established.


def _section_from_read(model: EngineeringResponseSectionRead) -> EngineeringResponseSection:
    return EngineeringResponseSection(
        section_type=model.section_type,
        title=model.title,
        body=tuple(model.body),
        sequence=model.sequence,
        enabled=model.enabled,
    )


def _document_reference_from_read(
    model: DocumentReferenceRead,
) -> DocumentReference:
    """``page_references`` is deliberately not read back: it is a derived
    view over ``mentions``, so reconstructing the mentions reconstructs
    it, and accepting a caller-supplied value would let the two
    disagree."""

    return DocumentReference(
        document_id=model.document_id,
        title=model.title,
        document_format=model.document_format,
        document_category=model.document_category,
        revision=model.revision,
        metadata_available=model.metadata_available,
        relevance=DocumentRelevance(
            total=model.relevance.total,
            components=tuple(
                DocumentRelevanceComponent(
                    category=component.category,
                    weight=component.weight,
                    detail=component.detail,
                )
                for component in model.relevance.components
            ),
        ),
        matched_identifiers=tuple(model.matched_identifiers),
        matched_terms=tuple(model.matched_terms),
        mentions=tuple(
            DocumentMentionReference(
                entry_id=mention.entry_id,
                kind=mention.kind,
                identifier=mention.identifier,
                locator_kind=mention.locator_kind,
                locator_value=mention.locator_value,
                label=mention.label,
            )
            for mention in model.mentions
        ),
        mention_count=model.mention_count,
        sort_key=(
            -model.relevance.total,
            -model.mention_count,
            model.document_id,
        ),
    )


def engineering_response_from_schema(
    model: EngineeringResponseRead,
) -> EngineeringResponse:
    return EngineeringResponse(
        project_id=model.project_id,
        status=model.status,
        sections=tuple(_section_from_read(s) for s in model.sections),
        summary=_section_from_read(model.summary),
        direct_answer=_section_from_read(model.direct_answer),
        references=tuple(
            EngineeringEvidenceReference(
                candidate_id=r.candidate_id,
                graph_node_ids=tuple(r.graph_node_ids),
                graph_relationship_ids=tuple(r.graph_relationship_ids),
            )
            for r in model.references
        ),
        warnings=tuple(
            EngineeringWarning(category=w.category, message=w.message)
            for w in model.warnings
        ),
        uncertainties=tuple(
            EngineeringUncertainty(level=u.level, reasons=tuple(u.reasons))
            for u in model.uncertainties
        ),
        overall_uncertainty=model.overall_uncertainty,
        metadata=EngineeringResponseMetadata(
            engineering_response_version=model.metadata.engineering_response_version,
            response_policy_version=model.metadata.response_policy_version,
            assembled_at=model.metadata.assembled_at,
            project_id=model.metadata.project_id,
            provider_id=model.metadata.provider_id,
            configured_model_identifier=model.metadata.configured_model_identifier,
            returned_model_identifier=model.metadata.returned_model_identifier,
            request_correlation_id=model.metadata.request_correlation_id,
            prompt_package_version=model.metadata.prompt_package_version,
            context_builder_version=model.metadata.context_builder_version,
            prompt_builder_version=model.metadata.prompt_builder_version,
            package_version=model.metadata.package_version,
        ),
        statistics=EngineeringResponseStatistics(
            section_count=model.statistics.section_count,
            enabled_section_count=model.statistics.enabled_section_count,
            disabled_section_count=model.statistics.disabled_section_count,
            warning_count=model.statistics.warning_count,
            uncertainty_count=model.statistics.uncertainty_count,
            reference_count=model.statistics.reference_count,
            character_count=model.statistics.character_count,
            document_reference_count=(
                model.statistics.document_reference_count
            ),
        ),
        version=EngineeringResponseVersion(
            engineering_response_version=model.version.engineering_response_version,
            response_policy_version=model.version.response_policy_version,
            prompt_builder_version=model.version.prompt_builder_version,
            context_builder_version=model.version.context_builder_version,
            request_preparation_policy_version=(
                model.version.request_preparation_policy_version
            ),
            runtime_version=model.version.runtime_version,
            package_version=model.version.package_version,
            document_retrieval_version=(
                model.version.document_retrieval_version
            ),
            document_relevance_policy_version=(
                model.version.document_relevance_policy_version
            ),
        ),
        origin=model.origin,
        document_references=tuple(
            _document_reference_from_read(reference)
            for reference in model.document_references
        ),
        comparison=(
            None
            if model.comparison is None
            else ComparisonAssessment(
                outcome=model.comparison.outcome,
                stated_by_model=model.comparison.stated_by_model,
                evidence_bounded=model.comparison.evidence_bounded,
                left_evidence_count=model.comparison.left_evidence_count,
                right_evidence_count=model.comparison.right_evidence_count,
            )
        ),
        verification=(
            None
            if model.verification is None
            else VerificationAssessment(
                outcome=model.verification.outcome,
                stated_by_model=model.verification.stated_by_model,
                evidence_bounded=model.verification.evidence_bounded,
                evidence_reference_count=(
                    model.verification.evidence_reference_count
                ),
            )
        ),
    )


__all__ = [
    "EngineeringResponseBuildRequestBody",
    "EngineeringResponseBuilderResultRead",
    "EngineeringResponseRead",
    "context_package_from_schema",
    "prompt_package_from_schema",
    "llm_response_envelope_from_schema",
    "engineering_response_from_schema",
]
