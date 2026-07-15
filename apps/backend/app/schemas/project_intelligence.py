from typing import Literal

from pydantic import BaseModel


DocumentationStatus = Literal[
    "empty",
    "incomplete",
    "available",
]

ModuleStatus = Literal[
    "not_started",
    "in_progress",
    "completed",
]

RiskLevel = Literal[
    "low",
    "medium",
    "high",
]

ReadinessStatus = Literal[
    "not_ready",
    "partially_ready",
    "ready",
]


class DocumentationIntelligence(BaseModel):
    document_count: int
    completion: int
    status: DocumentationStatus


class ProgressIntelligence(BaseModel):
    completed: int
    total: int
    completion: int
    status: ModuleStatus


class IssuesIntelligence(BaseModel):
    open: int
    critical: int


class ProjectIntelligenceResponse(BaseModel):
    project_id: int
    health_score: int
    risk_level: RiskLevel
    readiness: ReadinessStatus
    next_action: str

    documentation: DocumentationIntelligence
    commissioning: ProgressIntelligence
    relay_testing: ProgressIntelligence
    issues: IssuesIntelligence