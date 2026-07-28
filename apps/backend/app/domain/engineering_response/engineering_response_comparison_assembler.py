"""
Assembles a comparison ``EngineeringResponse`` (Milestone 24.2) - the
same four stages as ``engineering_response_assembler.py``, differing only
in the composition input.

Statistics, metadata, versioning and validation are the **same shared
functions**, so a comparison response is held to exactly the same
structural invariants as every other response, plus the comparison
consistency rules ``engineering_response_validation.py`` adds.

Pure and deterministic; ``now`` is caller-supplied.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
)
from app.domain.engineering_response.engineering_response_comparison_composition import (  # noqa: E501
    compose_comparison_response,
)
from app.domain.engineering_response.engineering_response_metadata import (
    build_metadata,
    build_version,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
    EngineeringResponseBuildRequest,
    EngineeringResponseBuilderResult,
    EngineeringResponseConfiguration,
    EngineeringResponsePolicy,
    EngineeringResponseSourceEnvelope,
)
from app.domain.engineering_response.engineering_response_policy import (
    ENGINEERING_RESPONSE_VERSION,
    RESPONSE_POLICY_VERSION,
)
from app.domain.engineering_response.engineering_response_statistics import (
    build_statistics,
)
from app.domain.engineering_response.engineering_response_validation import (
    validate_response,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


def assemble_comparison_response(
    *,
    comparison: ComparisonContextPackage,
    prompt_package: PromptPackage,
    source: EngineeringResponseSourceEnvelope,
    now: datetime,
) -> EngineeringResponseBuilderResult:
    configuration = EngineeringResponseConfiguration(
        response_policy=EngineeringResponsePolicy(
            version=RESPONSE_POLICY_VERSION
        ),
        engineering_response_version=ENGINEERING_RESPONSE_VERSION,
    )
    # Metadata and versioning read the LEFT side's package: both sides were
    # assembled in the same call, by the same builder, under the same
    # policy versions, so either reports the same provenance.
    metadata_request = EngineeringResponseBuildRequest(
        project_id=comparison.project_id,
        context_package=comparison.left.package,
        prompt_package=prompt_package,
        source=source,
        configuration=configuration,
    )

    composition = compose_comparison_response(
        comparison, prompt_package, source
    )

    response = EngineeringResponse(
        project_id=comparison.project_id,
        status=composition.status,
        sections=composition.sections,
        summary=composition.summary,
        direct_answer=composition.direct_answer,
        references=composition.references,
        warnings=composition.warnings,
        uncertainties=composition.uncertainties,
        overall_uncertainty=composition.overall_uncertainty,
        metadata=build_metadata(metadata_request, now=now),
        statistics=build_statistics(composition),
        version=build_version(metadata_request),
        comparison=composition.comparison,
    )

    return EngineeringResponseBuilderResult(
        project_id=comparison.project_id,
        response=response,
        validation=validate_response(response),
    )
