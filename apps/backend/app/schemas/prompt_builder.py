from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.prompt_builder.prompt_builder_models import (
    PromptConstraint,
    PromptEvidenceReference,
    PromptInstruction,
    PromptMetadata,
    PromptObjective,
    PromptPackage,
    PromptSection,
    PromptSectionType,
    PromptStatistics,
    PromptVersion,
)
from app.schemas.context_builder import ContextPackageRead, context_package_from_schema

# --- Request ---------------------------------------------------------------


class PromptBuildRequestBody(BaseModel):
    """
    A Prompt Builder build request. ``project_id`` is deliberately
    absent - the path's own ``{project_id}`` is authoritative, matching
    every other governed router's convention. ``context_package`` is
    the ``ContextPackage`` a prior call to
    ``/context-builder/build`` returned (its ``package`` field) -
    Prompt Builder never calls Context Builder itself, so the caller
    supplies the package directly.

    ``objective`` selects between Prompt Builder's own fixed, versioned
    instruction and expected-output sets - it is never a caller-supplied
    prompt, template or instruction string. Omitting it produces exactly
    the package this endpoint produced before Milestone 23B.2.
    """

    context_package: ContextPackageRead
    objective: PromptObjective = PromptObjective.DIRECT_ANSWER


# --- Response ----------------------------------------------------------------


class PromptSectionRead(BaseModel):
    section_type: PromptSectionType
    priority: int
    content: list[str]
    estimated_token_count: int
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class PromptConstraintRead(BaseModel):
    identifier: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class PromptInstructionRead(BaseModel):
    identifier: str
    description: str

    model_config = ConfigDict(from_attributes=True)


class PromptEvidenceReferenceRead(BaseModel):
    item_id: str
    node_ids: list[str]
    edge_ids: list[str]
    statement_key: str
    review_id: int
    document_id: int

    model_config = ConfigDict(from_attributes=True)


class PromptMetadataRead(BaseModel):
    prompt_builder_version: str
    composition_policy_version: str
    context_assembly_version: str | None
    assembled_at: datetime
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class PromptStatisticsRead(BaseModel):
    section_count: int
    estimated_total_tokens: int
    enabled_section_count: int
    disabled_section_count: int
    knowledge_item_count: int
    reference_count: int
    warnings: list[str]

    model_config = ConfigDict(from_attributes=True)


class PromptVersionRead(BaseModel):
    prompt_builder_version: str
    composition_policy_version: str
    context_assembly_version: str | None
    package_version: str

    model_config = ConfigDict(from_attributes=True)


class PromptPackageRead(BaseModel):
    """
    Deliberately exposes only strongly typed sections and supporting
    objects - no raw provider payload, no serialized message list, no
    free-form concatenated prompt string of any kind (Milestone 15's
    "no raw provider payloads" requirement).
    """

    project_id: int
    objective: PromptObjective = PromptObjective.DIRECT_ANSWER
    system_context: PromptSectionRead
    engineering_context: PromptSectionRead
    retrieved_knowledge: PromptSectionRead
    constraints: list[PromptConstraintRead]
    instructions: list[PromptInstructionRead]
    expected_output: PromptSectionRead
    references: list[PromptEvidenceReferenceRead]
    sections: list[PromptSectionRead]
    metadata: PromptMetadataRead
    statistics: PromptStatisticsRead
    version: PromptVersionRead

    model_config = ConfigDict(from_attributes=True)


class PromptCompositionPolicyRead(BaseModel):
    version: str

    model_config = ConfigDict(from_attributes=True)


class PromptBuilderConfigurationRead(BaseModel):
    composition_policy: PromptCompositionPolicyRead
    prompt_builder_version: str

    model_config = ConfigDict(from_attributes=True)


class PromptValidationResultRead(BaseModel):
    valid: bool
    errors: list[str]

    model_config = ConfigDict(from_attributes=True)


class PromptBuildResultRead(BaseModel):
    project_id: int
    configuration: PromptBuilderConfigurationRead
    package: PromptPackageRead
    validation: PromptValidationResultRead

    model_config = ConfigDict(from_attributes=True)


# --- Reconstruction (LLM Provider Abstraction Layer's own input shape) ----
#
# The LLM Provider Abstraction Layer's own request body reuses
# PromptPackageRead as its own prompt_package field and calls
# prompt_package_from_schema to reconstruct the domain object - the
# same "reuse the upstream response shape" pattern this module's own
# context_package_from_schema already established for Context Builder.


def _section_from_read(model: PromptSectionRead) -> PromptSection:
    return PromptSection(
        section_type=model.section_type,
        priority=model.priority,
        content=tuple(model.content),
        estimated_token_count=model.estimated_token_count,
        enabled=model.enabled,
    )


def prompt_package_from_schema(model: PromptPackageRead) -> PromptPackage:
    return PromptPackage(
        project_id=model.project_id,
        objective=model.objective,
        system_context=_section_from_read(model.system_context),
        engineering_context=_section_from_read(model.engineering_context),
        retrieved_knowledge=_section_from_read(model.retrieved_knowledge),
        constraints=tuple(
            PromptConstraint(identifier=c.identifier, description=c.description)
            for c in model.constraints
        ),
        instructions=tuple(
            PromptInstruction(identifier=i.identifier, description=i.description)
            for i in model.instructions
        ),
        expected_output=_section_from_read(model.expected_output),
        references=tuple(
            PromptEvidenceReference(
                item_id=r.item_id,
                node_ids=tuple(r.node_ids),
                edge_ids=tuple(r.edge_ids),
                statement_key=r.statement_key,
                review_id=r.review_id,
                document_id=r.document_id,
            )
            for r in model.references
        ),
        sections=tuple(_section_from_read(s) for s in model.sections),
        metadata=PromptMetadata(
            prompt_builder_version=model.metadata.prompt_builder_version,
            composition_policy_version=model.metadata.composition_policy_version,
            context_assembly_version=model.metadata.context_assembly_version,
            assembled_at=model.metadata.assembled_at,
            package_version=model.metadata.package_version,
        ),
        statistics=PromptStatistics(
            section_count=model.statistics.section_count,
            estimated_total_tokens=model.statistics.estimated_total_tokens,
            enabled_section_count=model.statistics.enabled_section_count,
            disabled_section_count=model.statistics.disabled_section_count,
            knowledge_item_count=model.statistics.knowledge_item_count,
            reference_count=model.statistics.reference_count,
            warnings=tuple(model.statistics.warnings),
        ),
        version=PromptVersion(
            prompt_builder_version=model.version.prompt_builder_version,
            composition_policy_version=model.version.composition_policy_version,
            context_assembly_version=model.version.context_assembly_version,
            package_version=model.version.package_version,
        ),
    )


# Re-exported so app/routers/prompt_builder.py and
# app/routers/llm_provider.py have one import site for both the
# request schema and the ContextPackage/PromptPackage reconstruction
# helpers.
__all__ = [
    "PromptBuildRequestBody",
    "PromptBuildResultRead",
    "PromptPackageRead",
    "context_package_from_schema",
    "prompt_package_from_schema",
]
