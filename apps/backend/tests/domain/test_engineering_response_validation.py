from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.engineering_response.engineering_response_composition import (
    ENGINEERING_RESPONSE_SECTION_ORDER,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringEvidenceReference,
    EngineeringResponse,
    EngineeringResponseMetadata,
    EngineeringResponseOrigin,
    EngineeringResponseSection,
    EngineeringResponseStatistics,
    EngineeringResponseStatus,
    EngineeringSectionType,
    EngineeringUncertainty,
    EngineeringUncertaintyLevel,
    EngineeringResponseVersion,
    EngineeringWarning,
    EngineeringWarningCategory,
)
from app.domain.engineering_response.engineering_response_validation import (
    EngineeringResponseValidator,
    validate_response,
)

NOW = datetime(2026, 1, 1, 11, 0, 0)


def _sections() -> tuple[EngineeringResponseSection, ...]:
    titles = {
        EngineeringSectionType.SUMMARY: "Summary",
        EngineeringSectionType.DIRECT_ANSWER: "Direct Answer",
        EngineeringSectionType.TECHNICAL_EXPLANATION: "Technical Explanation",
        EngineeringSectionType.ASSUMPTIONS: "Assumptions",
        EngineeringSectionType.WARNINGS: "Warnings",
        EngineeringSectionType.LIMITATIONS: "Limitations",
        EngineeringSectionType.NEXT_ACTIONS: "Next Actions",
        EngineeringSectionType.REFERENCES: "Evidence References",
        EngineeringSectionType.UNKNOWN: "Unrecognized Content",
    }
    sections = []
    for index, section_type in enumerate(ENGINEERING_RESPONSE_SECTION_ORDER):
        body = ("Direct answer text.",) if section_type.value == "direct_answer" else ()
        sections.append(
            EngineeringResponseSection(
                section_type=section_type,
                title=titles[section_type],
                body=body,
                sequence=index,
                enabled=bool(body),
            )
        )
    return tuple(sections)


def _response(**overrides) -> EngineeringResponse:
    sections = overrides.pop("sections", _sections())
    warnings = overrides.pop("warnings", ())
    uncertainties = overrides.pop(
        "uncertainties",
        (EngineeringUncertainty(level=EngineeringUncertaintyLevel.LOW, reasons=("ok",)),),
    )
    references = overrides.pop("references", ())

    enabled = sum(1 for s in sections if s.enabled)
    character_count = sum(len(line) for s in sections for line in s.body)

    defaults = dict(
        project_id=1,
        status=EngineeringResponseStatus.COMPLETE,
        sections=sections,
        summary=sections[0],
        direct_answer=sections[1],
        references=references,
        warnings=warnings,
        uncertainties=uncertainties,
        overall_uncertainty=EngineeringUncertaintyLevel.LOW,
        metadata=EngineeringResponseMetadata(
            engineering_response_version="1.0",
            response_policy_version="1.0",
            assembled_at=NOW,
            project_id=1,
            provider_id="fake",
            configured_model_identifier="model-x",
            returned_model_identifier="model-x",
            request_correlation_id="corr-1",
            prompt_package_version="1.0",
            context_builder_version="1.0",
            prompt_builder_version="1.0",
            package_version="1.0",
        ),
        statistics=EngineeringResponseStatistics(
            section_count=len(sections),
            enabled_section_count=enabled,
            disabled_section_count=len(sections) - enabled,
            warning_count=len(warnings),
            uncertainty_count=len(uncertainties),
            reference_count=len(references),
            character_count=character_count,
        ),
        version=EngineeringResponseVersion(
            engineering_response_version="1.0",
            response_policy_version="1.0",
            prompt_builder_version="1.0",
            context_builder_version="1.0",
            request_preparation_policy_version="1.0",
            runtime_version="1.0",
            package_version="1.0",
        ),
    )
    defaults.update(overrides)
    return EngineeringResponse(**defaults)


def test_a_well_formed_response_is_valid() -> None:
    result = validate_response(_response())

    assert result.valid is True
    assert result.errors == ()


def test_the_validator_class_delegates_to_the_same_function() -> None:
    response = _response()

    assert EngineeringResponseValidator.validate(response) == validate_response(
        response
    )


def test_sections_out_of_order_are_rejected() -> None:
    sections = _sections()
    reordered = (sections[1], sections[0]) + sections[2:]

    result = validate_response(_response(sections=reordered))

    assert result.valid is False
    assert any("canonical order" in error for error in result.errors)


def test_duplicate_section_types_are_rejected() -> None:
    sections = _sections()
    duplicated = sections[:-1] + (sections[0],)

    result = validate_response(_response(sections=duplicated))

    assert result.valid is False
    assert any("Duplicate section types" in error for error in result.errors)


def test_incomplete_metadata_is_rejected() -> None:
    response = _response()
    broken_metadata = replace(response.metadata, provider_id="")
    broken = replace(response, metadata=broken_metadata)

    result = validate_response(broken)

    assert result.valid is False
    assert any("Metadata is incomplete" in error for error in result.errors)


def test_version_inconsistent_with_metadata_is_rejected() -> None:
    response = _response()
    broken_version = replace(response.version, engineering_response_version="9.9")
    broken = replace(response, version=broken_version)

    result = validate_response(broken)

    assert result.valid is False
    assert any("inconsistent with metadata" in error for error in result.errors)


def test_reference_count_inconsistency_is_rejected() -> None:
    response = _response(
        references=(
            EngineeringEvidenceReference(
                candidate_id="c1", graph_node_ids=(), graph_relationship_ids=()
            ),
        )
    )
    broken_statistics = replace(response.statistics, reference_count=0)
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any("reference_count" in error for error in result.errors)


def test_warning_count_inconsistency_is_rejected() -> None:
    response = _response(
        warnings=(
            EngineeringWarning(
                category=EngineeringWarningCategory.PARTIAL_CONTEXT,
                message="m",
            ),
        )
    )
    broken_statistics = replace(response.statistics, warning_count=0)
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any("warning_count" in error for error in result.errors)


def test_missing_uncertainty_declarations_are_rejected() -> None:
    response = _response()
    broken = replace(
        response,
        uncertainties=(),
        statistics=replace(response.statistics, uncertainty_count=0),
    )

    result = validate_response(broken)

    assert result.valid is False
    assert any("uncertainty declaration is required" in error for error in result.errors)


def test_overall_uncertainty_inconsistency_is_rejected() -> None:
    response = _response()
    broken = replace(response, overall_uncertainty=EngineeringUncertaintyLevel.HIGH)

    result = validate_response(broken)

    assert result.valid is False
    assert any("overall_uncertainty is inconsistent" in error for error in result.errors)


def test_section_count_inconsistency_is_rejected() -> None:
    response = _response()
    broken_statistics = replace(response.statistics, section_count=99)
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any("section_count" in error for error in result.errors)


def test_enabled_disabled_section_count_inconsistency_is_rejected() -> None:
    response = _response()
    broken_statistics = replace(response.statistics, enabled_section_count=99)
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any("enabled/disabled section counts" in error for error in result.errors)


def test_character_count_inconsistency_is_rejected() -> None:
    response = _response()
    broken_statistics = replace(response.statistics, character_count=0)
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any("character_count" in error for error in result.errors)


# --- Origin / provider correspondence (Milestone 23B.1) -------------------


def _deterministic_response(**overrides) -> EngineeringResponse:
    """A DETERMINISTIC_RETRIEVAL response: no provider, no model, no
    runtime version."""

    response = _response()
    metadata = replace(
        response.metadata,
        provider_id=None,
        configured_model_identifier=None,
        returned_model_identifier=None,
        prompt_package_version=None,
        context_builder_version=None,
        prompt_builder_version=None,
    )
    version = replace(
        response.version,
        prompt_builder_version=None,
        context_builder_version=None,
        request_preparation_policy_version=None,
        runtime_version=None,
    )

    return replace(
        response,
        origin=EngineeringResponseOrigin.DETERMINISTIC_RETRIEVAL,
        metadata=metadata,
        version=version,
        **overrides,
    )


def test_a_response_defaults_to_an_llm_invocation_origin() -> None:
    """Every response built before Milestone 23B.1 keeps exactly the
    meaning it already had."""

    assert _response().origin is EngineeringResponseOrigin.LLM_INVOCATION


def test_a_well_formed_deterministic_response_is_valid() -> None:
    result = validate_response(_deterministic_response())

    assert result.valid is True
    assert result.errors == ()


def test_an_llm_response_missing_its_provider_is_rejected() -> None:
    broken_metadata = replace(_response().metadata, provider_id=None)
    broken = replace(_response(), metadata=broken_metadata)

    result = validate_response(broken)

    assert result.valid is False
    assert any("LLM_INVOCATION" in error for error in result.errors)


def test_an_llm_response_missing_its_model_is_rejected() -> None:
    broken_metadata = replace(
        _response().metadata, configured_model_identifier=""
    )
    broken = replace(_response(), metadata=broken_metadata)

    result = validate_response(broken)

    assert result.valid is False


def test_a_deterministic_response_claiming_a_provider_is_rejected() -> None:
    """The fabrication this project refuses: a response nothing generated
    must not be able to claim a model generated it."""

    response = _deterministic_response()
    broken_metadata = replace(response.metadata, provider_id="anthropic")
    broken = replace(response, metadata=broken_metadata)

    result = validate_response(broken)

    assert result.valid is False
    assert any(
        "must name no provider" in error for error in result.errors
    )


def test_a_deterministic_response_claiming_a_runtime_version_is_rejected() -> (
    None
):
    response = _deterministic_response()
    broken_version = replace(response.version, runtime_version="1.0")
    broken = replace(response, version=broken_version)

    result = validate_response(broken)

    assert result.valid is False
    assert any(
        "runtime was never invoked" in error for error in result.errors
    )


def test_document_reference_count_inconsistency_is_rejected() -> None:
    response = _deterministic_response()
    broken_statistics = replace(
        response.statistics, document_reference_count=3
    )
    broken = replace(response, statistics=broken_statistics)

    result = validate_response(broken)

    assert result.valid is False
    assert any(
        "document_reference_count" in error for error in result.errors
    )
