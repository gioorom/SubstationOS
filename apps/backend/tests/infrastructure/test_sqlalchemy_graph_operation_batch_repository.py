from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.canonicalization.canonicalization_factory import (
    CanonicalizationFactory,
)
from app.domain.canonicalization.canonicalization_models import CanonicalFact
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.graph_builder.graph_builder_factory import (
    GraphOperationBatchFactory,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphNodeOperation,
    GraphOperationBatchScope,
    GraphOperationBatchSource,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_factory import (
    EvidenceReferenceFactory,
    ProposedClaimFactory,
)
from app.domain.proposed_claims.proposed_claim_models import ClaimSubject
from app.infrastructure.canonicalization.sqlalchemy_canonical_fact_repository import (
    SqlAlchemyCanonicalFactRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.infrastructure.graph_builder.sqlalchemy_graph_operation_batch_repository import (
    SqlAlchemyGraphOperationBatchRepository,
)
from app.infrastructure.project.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from app.infrastructure.proposed_claims.sqlalchemy_proposed_claim_repository import (
    SqlAlchemyProposedClaimRepository,
)
from app.infrastructure.review_workflow.sqlalchemy_review_candidate_repository import (
    SqlAlchemyReviewCandidateRepository,
)
from app.infrastructure.review_workflow.sqlalchemy_review_history_repository import (
    SqlAlchemyReviewHistoryRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord
from app.services import review_workflow_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
APPROVED_AT = datetime(2026, 1, 2, 9, 0, 0)


def _persist_canonical_fact(
    db_session: Session,
    *,
    identifier: str = "C-295",
) -> CanonicalFact:
    project = ProjectRecord(
        name="Alpha Substation",
        code=f"ALPHA-{identifier}",
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    document = DocumentRecord(
        filename="functional-schematic.pdf",
        file_path="/tmp/functional-schematic.pdf",
        project_id=project.id,
        project_name=project.name,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    index_repository = SqlAlchemyEngineeringIndexRepository(db_session)
    entry = index_repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=project.id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier=identifier,
            created_at=CREATED_AT,
        )
    )

    claim_repository = SqlAlchemyProposedClaimRepository(db_session)
    claim = claim_repository.create(
        ProposedClaimFactory.create(
            project_id=project.id,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value=f"Cable {identifier[2:]}"),
            predicate=None,
            object_=None,
            evidence=(EvidenceReferenceFactory.from_index_entry(entry),),
            now=CREATED_AT,
        )
    )

    candidate_repository = SqlAlchemyReviewCandidateRepository(db_session)
    history_repository = SqlAlchemyReviewHistoryRepository(db_session)
    project_repository = SqlAlchemyProjectRepository(db_session)

    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=claim.id,  # type: ignore[arg-type]
        now=CREATED_AT,
    )
    approved = review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer.smith",
        now=APPROVED_AT,
    )

    fact_repository = SqlAlchemyCanonicalFactRepository(db_session)

    return fact_repository.save(
        CanonicalizationFactory.canonicalize_claim(
            claim=claim,
            candidate=approved,
            now=APPROVED_AT,
        )
    )


def test_save_persists_a_batch_with_its_operations(
    db_session: Session,
) -> None:
    fact = _persist_canonical_fact(db_session)
    batch, _results = GraphOperationBatchFactory.build(
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.PROJECT,
            scope_id=fact.project_id,
        ),
        facts=[fact],
        now=CREATED_AT,
    )

    repository = SqlAlchemyGraphOperationBatchRepository(db_session)
    saved = repository.save(batch)

    assert saved.id is not None
    assert len(saved.operations) == 1
    assert isinstance(saved.operations[0], GraphNodeOperation)
    assert saved.operations[0].entity_id.value == "%d:CABLE:C-295" % (
        fact.project_id
    )


def test_get_by_id_returns_none_for_a_missing_batch(
    db_session: Session,
) -> None:
    repository = SqlAlchemyGraphOperationBatchRepository(db_session)

    assert repository.get_by_id(999) is None


def test_get_by_id_preserves_deterministic_operation_order(
    db_session: Session,
) -> None:
    fact = _persist_canonical_fact(db_session, identifier="C-295")
    batch, _results = GraphOperationBatchFactory.build(
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.PROJECT,
            scope_id=fact.project_id,
        ),
        facts=[fact],
        now=CREATED_AT,
    )
    repository = SqlAlchemyGraphOperationBatchRepository(db_session)
    saved = repository.save(batch)

    reloaded = repository.get_by_id(saved.id)  # type: ignore[arg-type]

    assert reloaded is not None
    assert reloaded.operations == saved.operations
    assert reloaded.source.scope is GraphOperationBatchScope.PROJECT
    assert reloaded.source.scope_id == fact.project_id
