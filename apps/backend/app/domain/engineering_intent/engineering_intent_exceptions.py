from __future__ import annotations


class EngineeringIntentError(Exception):
    """Base class for every exception raised by the Engineering Request
    Classification bounded context."""


class InvalidProjectIdError(EngineeringIntentError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class InvalidRequestTextError(EngineeringIntentError):
    """The request text is blank, or normalizes to nothing at all (e.g.
    punctuation only) - there is no request to classify."""

    def __init__(self, request_text: str) -> None:
        self.request_text = request_text

        super().__init__("Request text is blank or contains no classifiable content.")


class InvalidClassificationProvenanceError(EngineeringIntentError):
    """A required provenance identifier (session, conversation, or turn)
    is blank - without them the deterministic
    ``EngineeringIntentId`` cannot be derived."""

    def __init__(self, field_name: str, value: str) -> None:
        self.field_name = field_name
        self.value = value

        super().__init__(
            f"Invalid classification provenance: '{field_name}' is blank."
        )
