from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.project_intelligence import (
    DocumentationIntelligence,
    IssuesIntelligence,
    ProgressIntelligence,
    ProjectIntelligenceResponse,
)


def calculate_documentation_intelligence(
    document_count: int,
) -> DocumentationIntelligence:
    if document_count == 0:
        return DocumentationIntelligence(
            document_count=0,
            completion=0,
            status="empty",
        )

    if document_count < 5:
        completion = min(document_count * 20, 80)

        return DocumentationIntelligence(
            document_count=document_count,
            completion=completion,
            status="incomplete",
        )

    return DocumentationIntelligence(
        document_count=document_count,
        completion=100,
        status="available",
    )


def calculate_health_score(
    documentation_completion: int,
) -> int:
    base_score = 40
    documentation_weight = 60

    documentation_score = round(
        documentation_completion
        * documentation_weight
        / 100
    )

    return min(
        base_score + documentation_score,
        100,
    )


def calculate_risk_level(
    health_score: int,
) -> str:
    if health_score >= 80:
        return "low"

    if health_score >= 55:
        return "medium"

    return "high"


def calculate_readiness(
    documentation_completion: int,
) -> str:
    if documentation_completion >= 100:
        return "ready"

    if documentation_completion > 0:
        return "partially_ready"

    return "not_ready"


def calculate_next_action(
    document_count: int,
) -> str:
    if document_count == 0:
        return (
            "Carica i primi documenti tecnici "
            "della commessa."
        )

    if document_count < 5:
        return (
            "Completa il set documentale minimo "
            "del progetto."
        )

    return (
        "Verifica le revisioni e prepara "
        "le attività di commissioning."
    )


def build_project_intelligence(
    db: Session,
    project_id: int,
) -> ProjectIntelligenceResponse:
    """
    Takes a project **id**, not an ORM record: the caller has already
    confirmed the project exists through the repository, and handing an
    ORM object across this boundary was the last reason the projects
    router imported one.
    """

    document_count = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .count()
    )

    documentation = (
        calculate_documentation_intelligence(
            document_count
        )
    )

    health_score = calculate_health_score(
        documentation.completion
    )

    commissioning = ProgressIntelligence(
        completed=0,
        total=0,
        completion=0,
        status="not_started",
    )

    relay_testing = ProgressIntelligence(
        completed=0,
        total=0,
        completion=0,
        status="not_started",
    )

    issues = IssuesIntelligence(
        open=0,
        critical=0,
    )

    return ProjectIntelligenceResponse(
        project_id=project_id,
        health_score=health_score,
        risk_level=calculate_risk_level(
            health_score
        ),
        readiness=calculate_readiness(
            documentation.completion
        ),
        next_action=calculate_next_action(
            document_count
        ),
        documentation=documentation,
        commissioning=commissioning,
        relay_testing=relay_testing,
        issues=issues,
    )