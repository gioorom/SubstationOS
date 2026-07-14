from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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
    pass


class ProjectRead(ProjectBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )