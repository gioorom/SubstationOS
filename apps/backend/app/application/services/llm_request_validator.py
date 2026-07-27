"""
Stateless validation rules for the LLM Provider Abstraction Layer,
shared by ``LLMRequestPreparationService``. Validates only structurally
invalid input - a genuinely unsupported *optional* capability or
generation parameter is reported as a warning on
``LLMRequestPreparationResult`` instead (see ``llm_request_service.py``).
"""

from __future__ import annotations

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
from app.domain.prompt_builder.prompt_builder_models import PromptPackage
from app.domain.prompt_builder.prompt_validation import validate_package

MAX_MODEL_IDENTIFIER_LENGTH = 200
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0


class LLMRequestValidator:
    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_project_id_matches_prompt_package(
        project_id: int, prompt_package: PromptPackage
    ) -> None:
        if project_id != prompt_package.project_id:
            raise ProjectIdMismatchError(project_id, prompt_package.project_id)

    @staticmethod
    def validate_prompt_package(prompt_package: PromptPackage) -> None:
        validation = validate_package(prompt_package)
        if not validation.valid:
            raise InvalidPromptPackageError("; ".join(validation.errors))

        if not any(section.enabled for section in prompt_package.sections):
            raise InvalidPromptPackageError(
                "No enabled prompt sections are available to send to a "
                "provider."
            )

    @staticmethod
    def validate_provider_selection(selection: LLMProviderSelection) -> None:
        if not selection.provider_id or not selection.provider_id.strip():
            raise MissingProviderSelectionError()

    @staticmethod
    def validate_model_selection(selection: LLMModelSelection) -> None:
        identifier = selection.model_identifier

        if not identifier or not identifier.strip():
            raise MissingModelSelectionError()

        if len(identifier) > MAX_MODEL_IDENTIFIER_LENGTH:
            raise InvalidModelIdentifierError(
                identifier, MAX_MODEL_IDENTIFIER_LENGTH
            )

    @staticmethod
    def validate_generation_parameters(
        parameters: LLMGenerationParameters,
    ) -> None:
        if (
            parameters.max_output_tokens is not None
            and parameters.max_output_tokens <= 0
        ):
            raise InvalidGenerationParametersError(
                "max_output_tokens must be positive when supplied."
            )

        if parameters.temperature is not None and not (
            MIN_TEMPERATURE <= parameters.temperature <= MAX_TEMPERATURE
        ):
            raise InvalidGenerationParametersError(
                "temperature must be within "
                f"[{MIN_TEMPERATURE}, {MAX_TEMPERATURE}] when supplied."
            )

        for stop_sequence in parameters.stop_sequences:
            if not stop_sequence:
                raise InvalidGenerationParametersError(
                    "A stop sequence must not be blank."
                )
