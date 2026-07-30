"""
The public project contract.

``ProjectStatus`` is imported from the **domain** here, not from
``app.models.project``. Until Milestone 30.1.3 it came from the ORM
module, which made a persistence enum part of the public API by
accident; it is a domain vocabulary that happens to be persisted, and a
test asserts the two sets agree.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import (
    UNVERSIONED_CANONICAL_DOMAIN,
    Project,
)
from app.domain.project.project_status import ProjectStatus
from app.schemas.pagination import PageMetadata


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

    status: ProjectStatus = Field(
        default=ProjectStatus.PLANNING,
        description=(
            "Delivery phase of the installation. Orthogonal to "
            "lifecycle_state: a project can be 'energized' and "
            "'archived' at the same time."
        ),
    )

    description: str | None = None


class ProjectCreate(ProjectBase):
    """
    A new project.

    ``created_by`` is deliberately **absent** since EPIC 30.3. It used to
    be accepted from the request body, which meant the record of who
    created a project was whatever the caller typed. It is now taken from
    the authenticated identity, and there is no field here through which
    a caller could claim to be somebody else.
    """

    canonical_domain_version: str = UNVERSIONED_CANONICAL_DOMAIN


class ProjectUpdateMetadata(BaseModel):
    """
    Partial update of Project metadata. ``code`` is intentionally absent:
    once published, a project's code is a contract (CLAUDE.md §16) and is
    never renamed through a metadata update. Fields left unset are
    unchanged.

    ``lifecycle_state`` is absent for a different reason: it moves only
    through the explicit transitions (``/activate``, ``/archive``,
    ``/restore``, ``DELETE``), each of which validates the move. Allowing
    it here would let a caller jump from Draft to Deleted in one PATCH,
    skipping every rule.
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

    status: ProjectStatus | None = Field(
        default=None,
        description=(
            "Moves the installation's delivery phase. Unconstrained by "
            "design - works can be re-planned - unlike lifecycle_state."
        ),
    )

    voltage_level: str | None = Field(
        default=None,
        max_length=50,
    )


class ProjectRead(ProjectBase):
    """
    One project.

    Built from the **domain** aggregate, never from an ORM row. Before
    Milestone 30.1.3 the router re-read the ORM record to fill in
    ``status`` and ``voltage_level``, which the domain model did not
    carry; it does now, and that read is gone.
    """

    id: int
    lifecycle_state: ProjectLifecycleState
    canonical_domain_version: str
    created_by: str | None

    #: The user who owns the project. ``None`` for projects created
    #: before authentication existed.
    owner_user_id: int | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    deleted_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )

    @classmethod
    def of(cls, project: Project) -> "ProjectRead":
        return cls(
            id=project.id,
            name=project.name,
            code=project.code,
            customer=project.customer,
            epc=project.epc,
            country=project.country,
            location=project.location,
            voltage_level=project.voltage_level,
            status=project.status,
            description=project.description,
            lifecycle_state=project.lifecycle_state,
            canonical_domain_version=project.canonical_domain_version,
            created_by=project.created_by,
            owner_user_id=project.owner_user_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
            archived_at=project.archived_at,
            deleted_at=project.deleted_at,
        )


class ProjectListResponse(BaseModel):
    """One page of the project registry."""

    items: tuple[ProjectRead, ...]
    pagination: PageMetadata
