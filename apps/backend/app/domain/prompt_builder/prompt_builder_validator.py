from __future__ import annotations

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.prompt_builder_exceptions import (
    InvalidProjectIdError,
    ProjectIdMismatchError,
)


class PromptBuilderValidator:
    """Stateless validation rules for Prompt Builder, shared by
    ``PromptBuildRequestFactory``. Validates only structurally invalid
    input (a non-positive project id, a project id that disagrees with
    the supplied ``ContextPackage``) - Prompt Builder always assembles
    a structurally complete ``PromptPackage`` from any well-formed
    ``ContextPackage``, including an empty one; that is not a
    validation error (see ``prompt_composition.py``'s handling of empty
    sections)."""

    @staticmethod
    def validate_project_id(project_id: int) -> None:
        if project_id <= 0:
            raise InvalidProjectIdError(project_id)

    @staticmethod
    def validate_project_id_matches_context_package(
        project_id: int, context_package: ContextPackage
    ) -> None:
        if project_id != context_package.project_id:
            raise ProjectIdMismatchError(project_id, context_package.project_id)
