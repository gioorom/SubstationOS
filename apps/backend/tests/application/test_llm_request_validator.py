from __future__ import annotations

from datetime import datetime

import pytest

from app.application.models.llm_exceptions import (
    InvalidGenerationParametersError,
    InvalidModelIdentifierError,
    InvalidProjectIdError,
    InvalidPromptPackageError,
    MissingModelSelectionError,
    MissingProviderSelectionError,
    ProjectIdMismatchError,
)
from app.application.models.llm_request import (
    LLMGenerationParameters,
    LLMModelSelection,
    LLMProviderSelection,
)
from app.application.services.llm_request_validator import (
    MAX_MODEL_IDENTIFIER_LENGTH,
    LLMRequestValidator,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)
from app.services import context_builder_service, prompt_builder_service

PROJECT_ID = 6
NOW = datetime(2026, 1, 1, 7, 0, 0)


def _prompt_package(project_id: int = PROJECT_ID):
    collection = KnowledgeCandidateCollection(
        candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
    )
    context_result = context_builder_service.build_context_package(
        project_id=project_id, candidates=collection, now=NOW
    )
    prompt_result = prompt_builder_service.build_prompt_package(
        project_id=project_id, context_package=context_result.package, now=NOW
    )
    return prompt_result.package


def test_project_id_must_be_positive():
    with pytest.raises(InvalidProjectIdError):
        LLMRequestValidator.validate_project_id(0)


def test_project_id_must_match_the_prompt_package():
    package = _prompt_package(project_id=1)
    with pytest.raises(ProjectIdMismatchError):
        LLMRequestValidator.validate_project_id_matches_prompt_package(2, package)


def test_a_structurally_valid_prompt_package_passes():
    package = _prompt_package()
    LLMRequestValidator.validate_prompt_package(package)  # does not raise


def test_provider_selection_must_be_present():
    with pytest.raises(MissingProviderSelectionError):
        LLMRequestValidator.validate_provider_selection(
            LLMProviderSelection(provider_id="")
        )
    with pytest.raises(MissingProviderSelectionError):
        LLMRequestValidator.validate_provider_selection(
            LLMProviderSelection(provider_id="   ")
        )


def test_model_selection_must_be_present():
    with pytest.raises(MissingModelSelectionError):
        LLMRequestValidator.validate_model_selection(
            LLMModelSelection(model_identifier="")
        )


def test_model_identifier_must_not_exceed_the_maximum_length():
    with pytest.raises(InvalidModelIdentifierError):
        LLMRequestValidator.validate_model_selection(
            LLMModelSelection(model_identifier="x" * (MAX_MODEL_IDENTIFIER_LENGTH + 1))
        )


def test_any_non_blank_model_identifier_is_accepted_no_static_list():
    # Deliberately weird, made-up model strings must be accepted -
    # model identifiers are never validated against a hardcoded list
    # of "known" model names (Milestone 16's own requirement).
    LLMRequestValidator.validate_model_selection(
        LLMModelSelection(model_identifier="totally-made-up-future-model-9000")
    )


def test_negative_or_zero_max_output_tokens_is_rejected():
    with pytest.raises(InvalidGenerationParametersError):
        LLMRequestValidator.validate_generation_parameters(
            LLMGenerationParameters(max_output_tokens=0)
        )


def test_temperature_out_of_range_is_rejected():
    with pytest.raises(InvalidGenerationParametersError):
        LLMRequestValidator.validate_generation_parameters(
            LLMGenerationParameters(temperature=3.5)
        )


def test_blank_stop_sequence_is_rejected():
    with pytest.raises(InvalidGenerationParametersError):
        LLMRequestValidator.validate_generation_parameters(
            LLMGenerationParameters(stop_sequences=("valid", ""))
        )


def test_valid_generation_parameters_pass():
    LLMRequestValidator.validate_generation_parameters(
        LLMGenerationParameters(
            max_output_tokens=512, temperature=0.5, stop_sequences=("STOP",)
        )
    )
