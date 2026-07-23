from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import UNVERSIONED_CANONICAL_DOMAIN
from app.models.project import ProjectStatus


class ProjectBase(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=150,
    )

    code: str = Field(
        min_length=2,
        max_length=80,
    )

    customer: str = Field(
        min_length=2,
        max_length=150,
    )

    epc: str | None = Field(
        default=None,
        max_length=150,
    )

    country: str | None = Field(
        default=None,
        max_length=150,
    )

    location: str | None = Field(
        default=None,
        max_length=150,
    )

    voltage_level: str | None = Field(
        default=None,
        max_length=50,
    )

    status: ProjectStatus = ProjectStatus.PLANNING

    description: str | None = None


class ProjectCreate(ProjectBase):
    canonical_domain_version: str = UNVERSIONED_CANONICAL_DOMAIN
    created_by: str | None = None


class ProjectUpdateMetadata(BaseModel):
    """
    Partial update of Project metadata. ``code`` is intentionally absent:
    once published, a project's code is a contract (CLAUDE.md §16) and is
    never renamed through a metadata update. Fields left unset are
    unchanged.
    """

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    customer: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    epc: str | None = Field(
        default=None,
        max_length=150,
    )

    country: str | None = Field(
        default=None,
        max_length=150,
    )

    location: str | None = Field(
        default=None,
        max_length=150,
    )

    description: str | None = None


class ProjectRead(ProjectBase):
    id: int
    lifecycle_state: ProjectLifecycleState
    canonical_domain_version: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )
