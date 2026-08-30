"""
Orchestrates the full Prompt Builder pipeline (Milestone 15):

    ContextPackage
            |
       Composition          (prompt_composition.py)
            |
       Statistics           (prompt_statistics.py)
            |
       Metadata/Versioning  (prompt_metadata.py)
            |
       Validation           (prompt_validation.py)
       PromptBuildResult

Pure and deterministic: given the same ``PromptBuildRequest`` and the
same ``now``, always produces the same ``PromptBuildResult``, including
every section, statistic, and version. ``now`` is accepted as an
explicit parameter rather than read from the wall clock, so this
function performs no I/O and no non-deterministic side effect
(CLAUDE.md SS15, "Pure domain").

Overall complexity is O(n) in the size of the input ``ContextPackage``
(its selected candidates and warnings) - Composition is a small,
constant number of linear passes over already-materialized results
(never a second retrieval, never a database query); Statistics,
Metadata, and Validation are each O(1) or O(n) over the fixed, small
set of nine sections.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.prompt_builder.prompt_builder_models import (
    PromptBuildRequest,
    PromptBuildResult,
    PromptPackage,
)
from app.domain.prompt_builder.prompt_composition import compose_sections
from app.domain.prompt_builder.prompt_metadata import build_metadata, build_version
from app.domain.prompt_builder.prompt_statistics import build_statistics
from app.domain.prompt_builder.prompt_validation import validate_package


def assemble_prompt_package(
    request: PromptBuildRequest,
    *,
    now: datetime,
    reasoning: "ReasoningResult | None" = None,
) -> PromptBuildResult:
    """
    ``reasoning`` is a **derived** conclusion (EPIC 32.1), optional
    because most workflows run no rule. It is passed alongside the
    request rather than folded into it: a `PromptBuildRequest` is what a
    caller asks for, and a conclusion is something the engine produced.
    """

    context_package = request.context_package

    assembly = compose_sections(
        context_package, objective=request.objective, reasoning=reasoning
    )
    statistics = build_statistics(assembly, context_package)
    metadata = build_metadata(
        configuration=request.configuration,
        context_package=context_package,
        now=now,
    )
    version = build_version(
        configuration=request.configuration, context_package=context_package
    )

    package = PromptPackage(
        project_id=request.project_id,
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
        objective=request.objective,
    )

    validation = validate_package(package)

    return PromptBuildResult(
        project_id=request.project_id,
        configuration=request.configuration,
        package=package,
        validation=validation,
    )
