from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.canonicalization.canonicalization_models import (
    CanonicalEntityReference,
    CanonicalFact,
    CanonicalProvenance,
)
from app.domain.canonicalization.canonicalization_repository import (
    CanonicalFactRepository,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.graph_builder.graph_builder_exceptions import (
    GraphBuilderProjectNotFoundError,
    GraphOperationBatchNotFoundError,
    ProjectNotGraphBuildableError,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphOperationBatch,
)
from app.domain.graph_builder.graph_operation_batch_repository import (
    GraphOperationBatchRepository,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    EvidenceReference,
)
from app.services import graph_builder_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


class FakeGraphOperationBatchRepository(GraphOperationBatchRepository):
    def __init__(self) -> None:
        self._batches: dict[int, GraphOperationBatch] = {}
        self._next_id = 1

    def save(self, batch: GraphOperationBatch) -> GraphOperationBatch:
        if batch.id is None:
            batch = replace(batch, id=self._next_id)
            self._next_id += 1

        self._batches[batch.id] = batch  # type: ignore[index]

        return batch

    def get_by_id(self, batch_id: int) -> GraphOperationBatch | None:
        return self._batches.get(batch_id)


class FakeCanonicalFactRepository(CanonicalFactRepository):
    def __init__(self) -> None:
        self._facts: list[CanonicalFact] = []

    def register(self, fact: CanonicalFact) -> None:
        self._facts.append(fact)

    def save(self, fact: CanonicalFact) -> CanonicalFact:
        raise NotImplementedError

    def get_by_id(self, fact_id: int) -> CanonicalFact | None:
        raise NotImplementedError

    def get_by_review_candidate(self, review_candidate_id: int):
        raise NotImplementedError

    def list_by_project(self, project_id: int) -> list[CanonicalFact]:
        return [
            fact for fact in self._facts if fact.project_id == project_id
        ]

    def list_by_document(self, document_id: int) -> list[CanonicalFact]:
        return [
            fact
            for fact in self._facts
            if any(
                evidence.document_id == document_id
                for evidence in fact.evidence
            )
        ]


class FakeProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[int, Project] = {}

    def register(self, project: Project) -> None:
        self._projects[project.id] = project  # type: ignore[index]

    def get_by_id(self, project_id: int) -> Project | None:
        return self._projects.get(project_id)

    def get_by_code(self, code: str) -> Project | None:
        raise NotImplementedError

    def save(self, project: Project) -> Project:
        raise NotImplementedError

    def list_all(self, *, include_deleted: bool = False):
        raise NotImplementedError

    def list_page(self, query):
        """
        In-memory paging. Legitimate here precisely because it is a fake:
        the SQLAlchemy adapter must page in the database, and an
        architecture test holds it to that.
        """

        from app.domain.shared_kernel.pagination import Page

        projects = self.list_all(include_deleted=query.include_deleted)

        if query.lifecycle_state is not None:
            projects = [
                project
                for project in projects
                if project.lifecycle_state is query.lifecycle_state
            ]

        if query.status is not None:
            projects = [
                project
                for project in projects
                if project.status is query.status
            ]

        if query.search is not None:
            needle = query.search.value.lower()

            projects = [
                project
                for project in projects
                if needle in project.name.lower()
                or needle in project.code.lower()
                or needle in project.customer.lower()
                or needle in (project.location or "").lower()
            ]

        start = query.page.offset

        return Page.of(
            tuple(projects[start : start + query.page.limit]),
            total=len(projects),
            request=query.page,
        )



def _project(project_id: int = 10) -> Project:
    return replace(
        ProjectFactory.create(
            name="Alpha Substation",
            code="ALPHA-001",
            customer="Acme Utilities",
            created_at=CREATED_AT,
        ),
        id=project_id,
        lifecycle_state=ProjectLifecycleState.ACTIVE,
    )


def _fact(project_id: int = 10, document_id: int = 5) -> CanonicalFact:
    return CanonicalFact(
        id=1,
        project_id=project_id,
        claim_type=ClaimType.EXISTENCE,
        subject=CanonicalEntityReference(
            entity_type="CABLE",
            canonical_id="C-295",
        ),
        predicate=None,
        object=None,
        proposed_claim_id=1,
        review_candidate_id=1,
        evidence=(
            EvidenceReference(
                engineering_index_entry_id=1,
                document_id=document_id,
                locator=IndexEntryLocator(
                    kind=IndexEntryLocatorKind.PAGE,
                    value="3",
                ),
            ),
        ),
        provenance=CanonicalProvenance(
            reviewed_by="engineer.smith",
            reviewed_at=CREATED_AT,
        ),
        created_at=CREATED_AT,
    )


@pytest.fixture()
def repositories():
    return (
        FakeGraphOperationBatchRepository(),
        FakeCanonicalFactRepository(),
        FakeProjectRepository(),
    )


def test_build_batch_for_project_persists_a_batch(repositories) -> None:
    batch_repository, fact_repository, project_repository = repositories
    project_repository.register(_project())
    fact_repository.register(_fact())

    batch = graph_builder_service.build_batch_for_project(
        batch_repository,
        fact_repository,
        project_repository,
        project_id=10,
        now=CREATED_AT,
    )

    assert batch.id is not None
    assert len(batch.operations) == 1


def test_build_batch_for_project_raises_for_an_unknown_project(
    repositories,
) -> None:
    batch_repository, fact_repository, project_repository = repositories

    with pytest.raises(GraphBuilderProjectNotFoundError):
        graph_builder_service.build_batch_for_project(
            batch_repository,
            fact_repository,
            project_repository,
            project_id=999,
            now=CREATED_AT,
        )


def test_build_batch_for_project_raises_for_an_archived_project(
    repositories,
) -> None:
    batch_repository, fact_repository, project_repository = repositories
    project_repository.register(
        replace(_project(), lifecycle_state=ProjectLifecycleState.ARCHIVED)
    )

    with pytest.raises(ProjectNotGraphBuildableError):
        graph_builder_service.build_batch_for_project(
            batch_repository,
            fact_repository,
            project_repository,
            project_id=10,
            now=CREATED_AT,
        )


def test_build_batch_for_project_with_no_facts_persists_an_empty_batch(
    repositories,
) -> None:
    batch_repository, fact_repository, project_repository = repositories
    project_repository.register(_project())

    batch = graph_builder_service.build_batch_for_project(
        batch_repository,
        fact_repository,
        project_repository,
        project_id=10,
        now=CREATED_AT,
    )

    assert batch.id is not None
    assert batch.operations == ()


def test_build_batch_for_document_persists_a_batch(repositories) -> None:
    batch_repository, fact_repository, project_repository = repositories
    project_repository.register(_project())
    fact_repository.register(_fact(document_id=5))

    batch = graph_builder_service.build_batch_for_document(
        batch_repository,
        fact_repository,
        project_repository,
        document_id=5,
        now=CREATED_AT,
    )

    assert batch.id is not None
    assert batch.project_id == 10


def test_build_batch_for_document_with_no_facts_is_not_persisted(
    repositories,
) -> None:
    batch_repository, fact_repository, project_repository = repositories

    batch = graph_builder_service.build_batch_for_document(
        batch_repository,
        fact_repository,
        project_repository,
        document_id=999,
        now=CREATED_AT,
    )

    assert batch.id is None
    assert batch.project_id is None
    assert batch.operations == ()


def test_build_batch_for_document_raises_for_an_archived_project(
    repositories,
) -> None:
    batch_repository, fact_repository, project_repository = repositories
    project_repository.register(
        replace(_project(), lifecycle_state=ProjectLifecycleState.ARCHIVED)
    )
    fact_repository.register(_fact(document_id=5))

    with pytest.raises(ProjectNotGraphBuildableError):
        graph_builder_service.build_batch_for_document(
            batch_repository,
            fact_repository,
            project_repository,
            document_id=5,
            now=CREATED_AT,
        )


def test_get_graph_operation_batch_raises_for_an_unknown_batch(
    repositories,
) -> None:
    batch_repository = repositories[0]

    with pytest.raises(GraphOperationBatchNotFoundError):
        graph_builder_service.get_graph_operation_batch(
            batch_repository,
            999,
        )
