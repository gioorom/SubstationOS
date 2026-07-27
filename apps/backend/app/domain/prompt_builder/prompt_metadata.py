"""
Builds ``PromptMetadata`` and ``PromptVersion``. ``now`` is always
supplied by the caller (the service layer) rather than read from the
wall clock here, keeping assembly deterministic and reproducible
(CLAUDE.md SS16) given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.composition_policy import PROMPT_PACKAGE_VERSION
from app.domain.prompt_builder.prompt_builder_models import (
    PromptBuilderConfiguration,
    PromptMetadata,
    PromptVersion,
)


def build_metadata(
    *,
    configuration: PromptBuilderConfiguration,
    context_package: ContextPackage,
    now: datetime,
) -> PromptMetadata:
    return PromptMetadata(
        prompt_builder_version=configuration.prompt_builder_version,
        composition_policy_version=configuration.composition_policy.version,
        context_builder_version=context_package.metadata.context_builder_version,
        assembled_at=now,
        package_version=PROMPT_PACKAGE_VERSION,
    )


def build_version(
    *,
    configuration: PromptBuilderConfiguration,
    context_package: ContextPackage,
) -> PromptVersion:
    return PromptVersion(
        prompt_builder_version=configuration.prompt_builder_version,
        composition_policy_version=configuration.composition_policy.version,
        context_builder_version=context_package.metadata.context_builder_version,
        package_version=PROMPT_PACKAGE_VERSION,
    )
