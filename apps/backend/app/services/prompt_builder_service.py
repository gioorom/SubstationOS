"""
Application service for Prompt Builder (EPIC 4, Milestone 15).
Validates a build request through ``PromptBuildRequestFactory``,
delegates assembly to the pure domain pipeline
(``prompt_package_assembler.assemble_prompt_package``), and returns a
``PromptBuildResult``. Performs no persistence and no I/O of any kind -
Prompt Builder's entire input is the ``ContextPackage`` the caller
supplies; it never calls Graph Query, Structured Retrieval, Context
Builder, or an AI provider itself.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.prompt_builder_factory import (
    PromptBuildRequestFactory,
)
from app.domain.prompt_builder.prompt_builder_models import PromptBuildResult
from app.domain.prompt_builder.prompt_package_assembler import (
    assemble_prompt_package,
)


def build_prompt_package(
    *,
    project_id: int,
    context_package: ContextPackage,
    now: datetime,
) -> PromptBuildResult:
    request = PromptBuildRequestFactory.create(
        project_id=project_id, context_package=context_package
    )

    return assemble_prompt_package(request, now=now)
