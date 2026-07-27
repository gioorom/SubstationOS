from __future__ import annotations


class EngineeringEngineError(Exception):
    """Base class for every exception raised by the Engineering Engine
    bounded context."""


class InvalidExecutionRequestError(EngineeringEngineError):
    def __init__(self, reason: str) -> None:
        self.reason = reason

        super().__init__(f"Invalid engine execution request: {reason}")


class DuplicateWorkflowRegistrationError(EngineeringEngineError):
    """Two workflows registered for the same intent type - the registry
    refuses, since workflow selection must be unambiguous."""

    def __init__(self, intent_type_value: str) -> None:
        self.intent_type_value = intent_type_value

        super().__init__(
            f"A workflow is already registered for intent type "
            f"'{intent_type_value}'."
        )


class WorkflowNotRegisteredError(EngineeringEngineError):
    def __init__(self, intent_type_value: str) -> None:
        self.intent_type_value = intent_type_value

        super().__init__(
            f"No workflow is registered for intent type "
            f"'{intent_type_value}'."
        )


class StepHandlerNotRegisteredError(EngineeringEngineError):
    def __init__(self, step_type_value: str) -> None:
        self.step_type_value = step_type_value

        super().__init__(
            f"No step handler is registered for step type "
            f"'{step_type_value}'."
        )


class MissingRequiredArtifactError(EngineeringEngineError):
    """A step declared it requires an artifact the execution context
    does not carry - a deterministic failure, never a silent skip."""

    def __init__(self, step_type_value: str, artifact_key_value: str) -> None:
        self.step_type_value = step_type_value
        self.artifact_key_value = artifact_key_value

        super().__init__(
            f"Step '{step_type_value}' requires artifact "
            f"'{artifact_key_value}', which has not been produced."
        )
