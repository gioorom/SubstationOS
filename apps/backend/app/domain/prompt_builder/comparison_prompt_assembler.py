"""
Assembles a comparison ``PromptPackage`` (Milestone 24.2) - the same four
stages as ``prompt_package_assembler.py``, differing only in the
composition input.

Statistics, metadata, versioning and validation are the **same shared
functions**, so a comparison prompt is held to exactly the same
structural invariants as every other prompt, including the fixed
eleven-section shape and the objective/instruction correspondence.

Pure and deterministic; ``now`` is caller-supplied, so no wall clock is
read and no I/O occurs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
)
from app.domain.prompt_builder.comparison_prompt_composition import (
    compose_comparison_sections,
)
from app.domain.prompt_builder.composition_policy import (
    COMPOSITION_POLICY_VERSION,
    PROMPT_BUILDER_VERSION,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptBuilderConfiguration,
    PromptBuildResult,
    PromptCompositionPolicy,
    PromptObjective,
    PromptPackage,
)
from app.domain.prompt_builder.prompt_metadata import (
    build_metadata,
    build_version,
)
from app.domain.prompt_builder.prompt_statistics import build_statistics
from app.domain.prompt_builder.prompt_validation import validate_package


def assemble_comparison_prompt_package(
    comparison: ComparisonContextPackage, *, now: datetime
) -> PromptBuildResult:
    configuration = PromptBuilderConfiguration(
        composition_policy=PromptCompositionPolicy(
            version=COMPOSITION_POLICY_VERSION
        ),
        prompt_builder_version=PROMPT_BUILDER_VERSION,
    )

    assembly = compose_comparison_sections(comparison)

    # Statistics and metadata are derived from the LEFT package's own
    # context metadata: both sides were assembled by the same builder, in
    # the same call, under the same policy versions, so either reports the
    # same provenance. Statistics' knowledge-item count is corrected below
    # to span both sides, which is the one figure that genuinely differs.
    statistics = build_statistics(assembly, comparison.left.package)
    metadata = build_metadata(
        configuration=configuration,
        context_package=comparison.left.package,
        now=now,
    )
    version = build_version(
        configuration=configuration, context_package=comparison.left.package
    )

    from dataclasses import replace

    statistics = replace(
        statistics,
        knowledge_item_count=(
            comparison.statistics.left_evidence_count
            + comparison.statistics.right_evidence_count
        ),
    )

    package = PromptPackage(
        project_id=comparison.project_id,
        system_context=assembly.system_context,
        engineering_context=assembly.engineering_context,
        retrieved_knowledge=assembly.retrieved_knowledge,
        constraints=assembly.constraints,
        instructions=assembly.instructions,
        expected_output=assembly.expected_output,
        references=assembly.references,
        sections=assembly.sections,
        metadata=metadata,
        statistics=statistics,
        version=version,
        objective=PromptObjective.ENGINEERING_COMPARISON,
    )

    return PromptBuildResult(
        project_id=comparison.project_id,
        configuration=configuration,
        package=package,
        validation=validate_package(package),
    )
