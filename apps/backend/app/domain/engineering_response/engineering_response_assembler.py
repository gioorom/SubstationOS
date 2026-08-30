"""
Orchestrates the full Engineering Response Builder pipeline (Milestone
18):

    ContextPackage + PromptPackage + EngineeringResponseSourceEnvelope
            |
       Composition           (engineering_response_composition.py)
            |
       Statistics            (engineering_response_statistics.py)
            |
       Metadata/Versioning   (engineering_response_metadata.py)
            |
       Validation            (engineering_response_validation.py)
       EngineeringResponseBuilderResult

Pure and deterministic: given the same ``EngineeringResponseBuildRequest``
and the same ``now``, always produces the same
``EngineeringResponseBuilderResult``, including every section,
statistic, and version. ``now`` is accepted as an explicit parameter
rather than read from the wall clock, so this function performs no I/O
and no non-deterministic side effect (CLAUDE.md SS15, "Pure domain").
No AI usage of any kind.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_response.engineering_response_composition import (
    compose_engineering_response,
)
from app.domain.engineering_response.engineering_response_metadata import (
    build_metadata,
    build_version,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
    EngineeringResponseBuildRequest,
    EngineeringResponseBuilderResult,
)
from app.domain.engineering_response.engineering_response_statistics import (
    build_statistics,
)
from app.domain.engineering_response.engineering_response_validation import (
    validate_response,
)


def assemble_engineering_response(
    request: EngineeringResponseBuildRequest, *, now: datetime
) -> EngineeringResponseBuilderResult:
    composition = compose_engineering_response(
        request.context_package,
        request.prompt_package,
        request.source,
        request.reasoning,
    )
    statistics = build_statistics(composition)
    metadata = build_metadata(request, now=now)
    version = build_version(request)

    response = EngineeringResponse(
        project_id=request.project_id,
        status=composition.status,
        sections=composition.sections,
        summary=composition.summary,
        direct_answer=composition.direct_answer,
        references=composition.references,
        warnings=composition.warnings,
        uncertainties=composition.uncertainties,
        overall_uncertainty=composition.overall_uncertainty,
        metadata=metadata,
        statistics=statistics,
        version=version,
        verification=composition.verification,
        derived_reasoning=composition.derived_reasoning,
    )

    validation = validate_response(response)

    return EngineeringResponseBuilderResult(
        project_id=request.project_id,
        response=response,
        validation=validation,
    )
