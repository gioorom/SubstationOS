from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_response.engineering_response_assembler import (
    assemble_engineering_response,
)
from app.domain.engineering_response.engineering_response_composition import (
    ENGINEERING_RESPONSE_SECTION_ORDER,
)
from app.domain.engineering_response.engineering_response_factory import (
    EngineeringResponseBuildRequestFactory,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    EngineeringResponseStatus,
    EngineeringSectionType,
    EngineeringSourceFinishReason,
    EngineeringUncertaintyLevel,
    EngineeringWarningCategory,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage
from app.services import context_builder_service, prompt_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    quantity_item,
    relationship_item,
    results_for,
)

PROJECT_ID = 21
NOW = datetime(2026, 1, 1, 10, 0, 0)


def _asset(designation: str):
    """One approved governed asset, designated as an engineer wrote it."""

    return asset_item(
        f"node-{designation.lower()}",
        designation,
        statement_key=f"statement-{designation}",
        project_id=PROJECT_ID,
    )


def _quantity(designation: str, *, value: str = "630 kVA"):
    """One approved governed quantity, reached from its asset by the
    governed relationship that asserted it."""

    return quantity_item(
        subject_node_id=f"node-{designation.lower()}",
        subject_label=designation,
        quantity_node_id=f"node-{value.replace(' ', '').lower()}",
        quantity_label=value,
        edge_id=f"edge-{designation.lower()}",
        statement_key=f"statement-q-{designation}",
        project_id=PROJECT_ID,
    )


def _relationship(subject: str, object_designation: str):
    """One approved governed relationship, both endpoints resolved."""

    return relationship_item(
        subject_node_id=f"node-{subject.lower()}",
        subject_label=subject,
        object_node_id=f"node-{object_designation.lower()}",
        object_label=object_designation,
        edge_id=f"edge-{subject.lower()}-{object_designation.lower()}",
        statement_key=f"statement-r-{subject}",
        project_id=PROJECT_ID,
    )


def _packages(
    items: tuple, **context_overrides
) -> tuple[ContextPackage, PromptPackage]:
    context_result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=results_for(tuple(items), project_id=PROJECT_ID),
        now=NOW,
        **context_overrides,
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=context_result.package, now=NOW
    )
    return context_result.package, prompt_result.package


def _text_source(
    text: str = "The cable feeds the transformer.",
    finish_reason: EngineeringSourceFinishReason = EngineeringSourceFinishReason.COMPLETED,
    extra_content: tuple[EngineeringResponseSourceContent, ...] = (),
    provider_warnings: tuple[str, ...] = (),
) -> EngineeringResponseSourceEnvelope:
    content = (
        EngineeringResponseSourceContent(
            sequence_index=0,
            is_supported_text=True,
            text=text,
            provider_block_type=None,
        ),
    ) + extra_content

    return EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=content,
        finish_reason=finish_reason,
        request_correlation_id="corr-1",
        attempt_count=1,
        warnings=provider_warnings,
        input_tokens=10,
        output_tokens=5,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )


def _build(context_package, prompt_package, source):
    request = EngineeringResponseBuildRequestFactory.create(
        project_id=PROJECT_ID,
        context_package=context_package,
        prompt_package=prompt_package,
        source=source,
    )
    return assemble_engineering_response(request, now=NOW)


def test_sections_follow_the_canonical_deterministic_order() -> None:
    context_package, prompt_package = _packages((_asset("C-1"),))
    result = _build(context_package, prompt_package, _text_source())

    section_types = tuple(s.section_type for s in result.response.sections)
    assert section_types == ENGINEERING_RESPONSE_SECTION_ORDER


def test_summary_technical_explanation_assumptions_and_next_actions_are_always_empty() -> (
    None
):
    context_package, prompt_package = _packages((_asset("C-1"),))
    result = _build(context_package, prompt_package, _text_source())

    always_empty = {
        EngineeringSectionType.SUMMARY,
        EngineeringSectionType.TECHNICAL_EXPLANATION,
        EngineeringSectionType.ASSUMPTIONS,
        EngineeringSectionType.NEXT_ACTIONS,
    }
    for section in result.response.sections:
        if section.section_type in always_empty:
            assert section.enabled is False
            assert section.body == ()


def test_full_coverage_and_completed_finish_reason_yields_complete_status_and_low_uncertainty() -> (
    None
):
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    assert context_package.coverage.overall_completeness == 1.0

    result = _build(context_package, prompt_package, _text_source())

    assert result.response.status is EngineeringResponseStatus.COMPLETE
    assert result.response.overall_uncertainty is EngineeringUncertaintyLevel.LOW
    assert result.response.warnings == ()
    assert result.validation.valid is True


def test_zero_retrieved_candidates_yields_insufficient_evidence_and_high_uncertainty() -> (
    None
):
    context_package, prompt_package = _packages(())

    result = _build(context_package, prompt_package, _text_source())

    categories = {w.category for w in result.response.warnings}
    assert EngineeringWarningCategory.INSUFFICIENT_EVIDENCE in categories
    assert result.response.overall_uncertainty is EngineeringUncertaintyLevel.HIGH


def test_partial_coverage_yields_partial_context_warning_and_medium_uncertainty() -> (
    None
):
    context_package, prompt_package = _packages(
        (_asset("C-1"), _asset("C-2")),
        max_items=1,
    )
    assert 0.5 <= context_package.coverage.overall_completeness < 1.0

    result = _build(context_package, prompt_package, _text_source())

    categories = {w.category for w in result.response.warnings}
    assert EngineeringWarningCategory.PARTIAL_CONTEXT in categories
    assert result.response.overall_uncertainty is EngineeringUncertaintyLevel.MEDIUM


def test_unsupported_content_alongside_text_yields_partial_status_and_warnings() -> (
    None
):
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    source = _text_source(
        extra_content=(
            EngineeringResponseSourceContent(
                sequence_index=1,
                is_supported_text=False,
                text="",
                provider_block_type="tool_use",
            ),
        )
    )

    result = _build(context_package, prompt_package, source)

    assert result.response.status is EngineeringResponseStatus.PARTIAL
    categories = {w.category for w in result.response.warnings}
    assert EngineeringWarningCategory.UNKNOWN_CONTENT in categories

    unknown_section = next(
        s
        for s in result.response.sections
        if s.section_type is EngineeringSectionType.UNKNOWN
    )
    assert unknown_section.enabled is True
    assert "tool_use" in unknown_section.body[0]


def test_only_unsupported_content_yields_unsupported_status_and_high_uncertainty() -> (
    None
):
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    source = EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(
            EngineeringResponseSourceContent(
                sequence_index=0,
                is_supported_text=False,
                text="",
                provider_block_type="tool_use",
            ),
        ),
        finish_reason=EngineeringSourceFinishReason.TOOL_REQUEST,
        request_correlation_id="corr-1",
        attempt_count=1,
        warnings=(),
        input_tokens=None,
        output_tokens=None,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )

    result = _build(context_package, prompt_package, source)

    assert result.response.status is EngineeringResponseStatus.UNSUPPORTED
    direct_answer = result.response.direct_answer
    assert direct_answer.enabled is False
    categories = {w.category for w in result.response.warnings}
    assert EngineeringWarningCategory.UNSUPPORTED_RESPONSE in categories
    assert result.response.overall_uncertainty is EngineeringUncertaintyLevel.HIGH


def test_no_content_at_all_yields_empty_status_and_unknown_uncertainty() -> None:
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    source = EngineeringResponseSourceEnvelope(
        provider_id="fake",
        configured_model_identifier="model-x",
        returned_model_identifier="model-x",
        content=(),
        finish_reason=EngineeringSourceFinishReason.PROVIDER_ERROR,
        request_correlation_id="corr-1",
        attempt_count=1,
        warnings=(),
        input_tokens=None,
        output_tokens=None,
        runtime_version="1.0",
        adapter_version="1.0",
        request_preparation_policy_version="1.0",
    )

    result = _build(context_package, prompt_package, source)

    assert result.response.status is EngineeringResponseStatus.EMPTY
    assert result.response.overall_uncertainty is EngineeringUncertaintyLevel.UNKNOWN


def test_truncated_finish_reason_yields_partial_status_and_limitations() -> None:
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    source = _text_source(finish_reason=EngineeringSourceFinishReason.MAXIMUM_OUTPUT_REACHED)

    result = _build(context_package, prompt_package, source)

    assert result.response.status is EngineeringResponseStatus.PARTIAL
    limitations_section = next(
        s
        for s in result.response.sections
        if s.section_type is EngineeringSectionType.LIMITATIONS
    )
    assert limitations_section.enabled is True
    assert "truncated" in limitations_section.body[0]


def test_provider_warnings_are_echoed_as_structured_provider_warning_entries() -> (
    None
):
    context_package, prompt_package = _packages(
        (_asset("C-1"),), max_items=10
    )
    source = _text_source(provider_warnings=("A raw provider-level warning.",))

    result = _build(context_package, prompt_package, source)

    matching = [
        w
        for w in result.response.warnings
        if w.category is EngineeringWarningCategory.PROVIDER_WARNING
    ]
    assert len(matching) == 1
    assert matching[0].message == "A raw provider-level warning."


def test_references_are_preserved_verbatim_from_the_prompt_package() -> None:
    context_package, prompt_package = _packages((_asset("C-1"),))

    result = _build(context_package, prompt_package, _text_source())

    assert len(result.response.references) == len(prompt_package.references)
    for engineering_reference, prompt_reference in zip(
        result.response.references, prompt_package.references
    ):
        assert engineering_reference.item_id == prompt_reference.item_id
        assert engineering_reference.node_ids == prompt_reference.node_ids
        assert (
            engineering_reference.edge_ids
            == prompt_reference.edge_ids
        )


def test_statistics_are_internally_consistent() -> None:
    context_package, prompt_package = _packages((_asset("C-1"),))
    result = _build(context_package, prompt_package, _text_source())
    response = result.response

    assert response.statistics.section_count == len(response.sections)
    enabled = sum(1 for s in response.sections if s.enabled)
    assert response.statistics.enabled_section_count == enabled
    assert response.statistics.disabled_section_count == len(response.sections) - enabled
    assert response.statistics.warning_count == len(response.warnings)
    assert response.statistics.uncertainty_count == len(response.uncertainties)
    assert response.statistics.reference_count == len(response.references)
    expected_characters = sum(len(line) for s in response.sections for line in s.body)
    assert response.statistics.character_count == expected_characters


def test_identical_inputs_produce_an_identical_response() -> None:
    context_package, prompt_package = _packages((_asset("C-1"),))
    source = _text_source()

    first = _build(context_package, prompt_package, source)
    second = _build(context_package, prompt_package, source)

    assert first.response == second.response
    assert first.validation == second.validation


def test_a_well_formed_response_is_valid() -> None:
    context_package, prompt_package = _packages((_asset("C-1"),))
    result = _build(context_package, prompt_package, _text_source())

    assert result.validation.valid is True
    assert result.validation.errors == ()
