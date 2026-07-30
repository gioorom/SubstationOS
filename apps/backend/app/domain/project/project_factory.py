from __future__ import annotations

from datetime import datetime

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import (
    UNVERSIONED_CANONICAL_DOMAIN,
    Project,
)
from app.domain.project.project_status import ProjectStatus
from app.domain.project.project_validator import ProjectValidator


class ProjectFactory:
    """
    Builds a new ``Project`` aggregate, enforcing invariants at
    construction time (CLAUDE.md §4.2). Every project starts in
    ``DRAFT`` - it becomes ``ACTIVE`` only through an explicit
    ``ActivateProject`` use case, never on creation.
    """

    @staticmethod
    def create(
        *,
        name: str,
        code: str,
        customer: str,
        created_at: datetime,
        epc: str | None = None,
        country: str | None = None,
        location: str | None = None,
        description: str | None = None,
        canonical_domain_version: str = UNVERSIONED_CANONICAL_DOMAIN,
        created_by: str | None = None,
        owner_user_id: int | None = None,
        status: ProjectStatus = ProjectStatus.PLANNING,
        voltage_level: str | None = None,
    ) -> Project:
        ProjectValidator.validate_name(name)
        ProjectValidator.validate_code(code)

        return Project(
            id=None,
            name=name,
            code=code,
            customer=customer,
            epc=epc,
            country=country,
            location=location,
            description=description,
            lifecycle_state=ProjectLifecycleState.DRAFT,
            canonical_domain_version=canonical_domain_version,
            created_by=created_by,
            owner_user_id=owner_user_id,
            created_at=created_at,
            updated_at=created_at,
            status=status,
            voltage_level=voltage_level,
        )
