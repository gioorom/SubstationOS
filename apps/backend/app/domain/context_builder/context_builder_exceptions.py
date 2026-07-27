from __future__ import annotations


class ContextBuilderError(Exception):
    """Base class for every exception raised by the Context Builder
    bounded context."""


class InvalidProjectIdError(ContextBuilderError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(f"Invalid project id: '{project_id}'.")


class InvalidBudgetPolicyValueError(ContextBuilderError):
    def __init__(
        self, field_name: str, value: int, minimum: int, maximum: int
    ) -> None:
        self.field_name = field_name
        self.value = value

        super().__init__(
            f"Budget policy field '{field_name}' has value {value}, "
            f"outside the supported range [{minimum}, {maximum}]."
        )


class BlankMetadataEntryKeyError(ContextBuilderError):
    def __init__(self) -> None:
        super().__init__("A metadata entry key must not be blank.")
