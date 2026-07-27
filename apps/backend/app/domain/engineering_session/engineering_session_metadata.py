"""
Builds ``EngineeringSessionMetadata`` and ``EngineeringSessionVersion``.
``now``/``created_at`` are always supplied by the caller rather than
read from the wall clock here, keeping every builder operation
deterministic and reproducible (CLAUDE.md SS16) given the same inputs.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_session.engineering_session_models import (
    EngineeringSessionConfiguration,
    EngineeringSessionMetadata,
    EngineeringSessionVersion,
)
from app.domain.engineering_session.engineering_session_policy import (
    SESSION_PACKAGE_VERSION,
)


def build_metadata(
    *,
    configuration: EngineeringSessionConfiguration,
    project_id: int,
    created_by: str | None,
    created_at: datetime,
    updated_at: datetime,
) -> EngineeringSessionMetadata:
    return EngineeringSessionMetadata(
        engineering_session_version=(
            configuration.engineering_session_version
        ),
        session_policy_version=configuration.session_policy.version,
        project_id=project_id,
        created_by=created_by,
        created_at=created_at,
        updated_at=updated_at,
        package_version=SESSION_PACKAGE_VERSION,
    )


def build_version(
    configuration: EngineeringSessionConfiguration,
) -> EngineeringSessionVersion:
    return EngineeringSessionVersion(
        engineering_session_version=(
            configuration.engineering_session_version
        ),
        session_policy_version=configuration.session_policy.version,
        package_version=SESSION_PACKAGE_VERSION,
    )
