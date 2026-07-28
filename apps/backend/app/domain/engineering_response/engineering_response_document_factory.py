"""
Builds an immutable ``EngineeringResponseDocumentLookupBuildRequest`` from
an already-executed document lookup (CLAUDE.md §4.2 - a factory enforces
invariants at construction time). The ``DETERMINISTIC_RETRIEVAL``
counterpart to ``engineering_response_factory.py``, sharing the same
``EngineeringResponseInputValidator`` rather than restating them.
"""

from __future__ import annotations

from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalResult,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseConfiguration,
    EngineeringResponseDocumentLookupBuildRequest,
    EngineeringResponsePolicy,
)
from app.domain.engineering_response.engineering_response_policy import (
    ENGINEERING_RESPONSE_VERSION,
    RESPONSE_POLICY_VERSION,
)
from app.domain.engineering_response.engineering_response_validator import (
    EngineeringResponseInputValidator,
)


class EngineeringResponseDocumentLookupBuildRequestFactory:
    @staticmethod
    def create(
        *,
        project_id: int,
        retrieval_result: DocumentRetrievalResult,
        request_correlation_id: str,
    ) -> EngineeringResponseDocumentLookupBuildRequest:
        EngineeringResponseInputValidator.validate_project_id(project_id)
        EngineeringResponseInputValidator.validate_project_id_matches_document_retrieval(
            project_id, retrieval_result
        )
        EngineeringResponseInputValidator.validate_request_correlation_id(
            request_correlation_id
        )

        configuration = EngineeringResponseConfiguration(
            response_policy=EngineeringResponsePolicy(
                version=RESPONSE_POLICY_VERSION
            ),
            engineering_response_version=ENGINEERING_RESPONSE_VERSION,
        )

        return EngineeringResponseDocumentLookupBuildRequest(
            project_id=project_id,
            retrieval_result=retrieval_result,
            request_correlation_id=request_correlation_id.strip(),
            configuration=configuration,
        )
