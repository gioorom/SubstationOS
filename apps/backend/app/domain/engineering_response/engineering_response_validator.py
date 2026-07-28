from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalResult,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    BlankRequestCorrelationIdError,
    InvalidProjectIdError,
    ProjectIdMismatchError,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


class EngineeringResponseInputValidator:
    """Stateless validation rules for Engineering Response, shared by
    ``EngineeringResponseBuildRequestFactory`` and
    ``EngineeringResponseDocumentLookupBuildRequestFactory``. Validates only
    structurally invalid input (a non-positive project id, a project id
    that disagrees with a supplied upstream package) - Engineering
    Response always builds a structurally complete
    ``EngineeringResponse`` from any well-formed
    ``EngineeringResponseSourceEnvelope``, including one with no
    content blocks at all (that yields ``EngineeringResponseStatus.EMPTY``,
    which is not a validation error)."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_project_id_matches_context_package(
        project_id: int, context_package: ContextPackage
    ) -> None:
        if project_id != context_package.project_id:
            raise ProjectIdMismatchError(
                project_id, context_package.project_id, "ContextPackage"
            )

    @staticmethod
    def validate_project_id_matches_prompt_package(
        project_id: int, prompt_package: PromptPackage
    ) -> None:
        if project_id != prompt_package.project_id:
            raise ProjectIdMismatchError(
                project_id, prompt_package.project_id, "PromptPackage"
            )

    @staticmethod
    def validate_project_id_matches_document_retrieval(
        project_id: int, retrieval_result: DocumentRetrievalResult
    ) -> None:
        if project_id != retrieval_result.request.project_id:
            raise ProjectIdMismatchError(
                project_id,
                retrieval_result.request.project_id,
                "DocumentRetrievalResult",
            )

    @staticmethod
    def validate_request_correlation_id(request_correlation_id: str) -> None:
        if not request_correlation_id or not request_correlation_id.strip():
            raise BlankRequestCorrelationIdError()
