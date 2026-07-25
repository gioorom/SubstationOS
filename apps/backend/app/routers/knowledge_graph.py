"""
LEGACY - see app/models/knowledge_graph.py's module docstring and
ADR-0009 (Legacy Knowledge Graph Isolation). Serves unreviewed
``ProjectEntity``/``EntityRelation`` reads. The governed equivalent is
``app.routers.project_knowledge_graph`` (execution) and
``app.routers.graph_query`` (deterministic reads at
``/projects/{id}/graph/**``) - a different URL namespace by design, not
an oversight. Retained (not deleted) because
``app.routers.documents.upload_document`` still writes to the tables
this router reads. Marked ``deprecated`` in the OpenAPI schema so new
API consumers are steered toward the governed path.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.knowledge_graph import (
    EntityRelation,
    EntityType,
    ProjectEntity,
)
from app.models.project import Project
from app.schemas.knowledge_graph import (
    EntityDetailResponse,
    KnowledgeGraphEdge,
    KnowledgeGraphResponse,
)
from app.services.knowledge_graph import (
    get_project_entities,
    get_related_entities,
)


router = APIRouter(
    prefix="/projects",
    tags=["Knowledge Graph (Legacy)"],
    deprecated=True,
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_project_or_404(
    db: Session,
    project_id: int,
) -> Project:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.get(
    "/{project_id}/knowledge-graph",
    response_model=KnowledgeGraphResponse,
)
def get_knowledge_graph(
    project_id: int,
    search: str | None = Query(
        default=None,
        min_length=1,
        description="Search entities by name or description",
    ),
    entity_type: EntityType | None = Query(
        default=None,
        description="Filter entities by type",
    ),
    db: Session = Depends(get_db),
):
    get_project_or_404(
        db=db,
        project_id=project_id,
    )

    entity_statement = select(ProjectEntity).where(
        ProjectEntity.project_id == project_id,
    )

    if entity_type is not None:
        entity_statement = entity_statement.where(
            ProjectEntity.entity_type == entity_type,
        )

    if search is not None:
        normalized_search = search.strip()

        entity_statement = entity_statement.where(
            or_(
                ProjectEntity.name.ilike(
                    f"%{normalized_search}%"
                ),
                ProjectEntity.description.ilike(
                    f"%{normalized_search}%"
                ),
                ProjectEntity.source_document.ilike(
                    f"%{normalized_search}%"
                ),
            )
        )

    entity_statement = entity_statement.order_by(
        ProjectEntity.entity_type,
        ProjectEntity.name,
    )

    entities = list(
        db.scalars(entity_statement).all()
    )

    entity_ids = {
        entity.id
        for entity in entities
    }

    relations: list[EntityRelation] = []

    if entity_ids:
        relation_statement = (
            select(EntityRelation)
            .where(
                EntityRelation.source_entity_id.in_(entity_ids),
                EntityRelation.target_entity_id.in_(entity_ids),
            )
            .order_by(EntityRelation.id)
        )

        relations = list(
            db.scalars(relation_statement).all()
        )

    edges = [
        KnowledgeGraphEdge(
            id=relation.id,
            source=relation.source_entity_id,
            target=relation.target_entity_id,
            relation_type=relation.relation_type,
        )
        for relation in relations
    ]

    return KnowledgeGraphResponse(
        project_id=project_id,
        nodes=entities,
        edges=edges,
    )


@router.get(
    "/{project_id}/entities",
    response_model=list[EntityDetailResponse],
)
def get_entities(
    project_id: int,
    entity_type: EntityType | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
):
    get_project_or_404(
        db=db,
        project_id=project_id,
    )

    entities = get_project_entities(
        db=db,
        project_id=project_id,
        entity_type=entity_type,
    )

    return [
        EntityDetailResponse(
            id=entity.id,
            project_id=entity.project_id,
            entity_type=entity.entity_type,
            name=entity.name,
            description=entity.description,
            source_document=entity.source_document,
            created_at=entity.created_at,
            related_entities=get_related_entities(
                db=db,
                entity_id=entity.id,
            ),
        )
        for entity in entities
    ]


@router.get(
    "/{project_id}/entities/{entity_id}",
    response_model=EntityDetailResponse,
)
def get_entity(
    project_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
):
    get_project_or_404(
        db=db,
        project_id=project_id,
    )

    entity = db.get(
        ProjectEntity,
        entity_id,
    )

    if (
        entity is None
        or entity.project_id != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    related_entities = get_related_entities(
        db=db,
        entity_id=entity.id,
    )

    return EntityDetailResponse(
        id=entity.id,
        project_id=entity.project_id,
        entity_type=entity.entity_type,
        name=entity.name,
        description=entity.description,
        source_document=entity.source_document,
        created_at=entity.created_at,
        related_entities=related_entities,
    )