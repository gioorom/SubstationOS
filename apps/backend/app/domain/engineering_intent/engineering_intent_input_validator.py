from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_exceptions import (
    InvalidClassificationProvenanceError,
    InvalidProjectIdError,
    InvalidRequestTextError,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
)
from app.domain.engineering_intent.engineering_intent_normalization import (
    normalize_text,
)


class EngineeringIntentInputValidator:
    """Stateless validation of classification input. Validates only
    structurally invalid input (a non-positive project id, blank
    provenance identifiers, request text with no classifiable content).
    Every other input is valid, not an error - an unclassifiable but
    non-empty request is a legitimate ``UNSUPPORTED_REQUEST`` result,
    never an exception."""

    @staticmethod
    def validate(input_: EngineeringIntentClassificationInput) -> None:
        if input_.project_id <= 0:
            raise InvalidProjectIdError(input_.project_id)

        for field_name, value in (
            ("engineering_session_id", input_.engineering_session_id),
            ("conversation_id", input_.conversation_id),
            ("turn_id", input_.turn_id),
        ):
            if not value or not value.strip():
                raise InvalidClassificationProvenanceError(field_name, value)

        if not normalize_text(input_.request_text):
            raise InvalidRequestTextError(input_.request_text)
