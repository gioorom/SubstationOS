from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.canonicalization.canonicalization_exceptions import (
    CanonicalFactNotFoundError,
    CanonicalizationClaimNotFoundError,
    CanonicalizationProjectNotFoundError,
    CanonicalizationReviewCandidateNotFoundError,
    ProjectNotCanonicalizableError,
    ReviewCandidateNotApprovedError,
)
from app.domain.canonicalization.canonicalization_models import (
    CanonicalFact,
)
from app.domain.canonicalization.canonicalization_repository import (
    CanonicalFactRepository,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.project.project_factory import ProjectFactory
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import Project
from app.domain.project.project_repository import ProjectRepository
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.domain.review_workflow.review_candidate_repository import (
    ReviewCandidateRepository,
)
from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
)
from app.services import canonicalization_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
APPROVED_AT = datetime(2026, 1, 2, 9, 0, 0)


class FakeCanonicalFactRepository(CanonicalFactRepository):
    def __init__(self) -> None:
        self._facts: dict[int, CanonicalFact] = {}
        self._next_id = 1

    def save(self, fact: CanonicalFact) -> CanonicalFact:
        if fact.id is None:
            fact = replace(fact, id=self._next_id)
            self._next_id += 1

        self._facts[fact.id] = fact  # type: ignore[index]

        return fact

    def get_by_id(self, fact_id: int) -> CanonicalFact | None:
        return self._facts.get(fact_id)

    def get_by_review_candidate(
        self,
        review_candidate_id: int,
    ) -> CanonicalFact | None:
        for fact in self._facts.values():
            if fact.review_candidate_id == review_candidate_id:
                return fact

        return None

    def list_by_project(self, project_id: int) -> list[CanonicalFact]:
        return [
            fact
            for fact in self._facts.values()
            if fact.project_id == project_id
        ]

    def list_by_document(self, document_id: int) -> list[CanonicalFact]:
        return [
            fact
            for fact in self._facts.values()
            if any(
                evidence.document_id == document_id
                for evidence in fact.evidence
            )
        ]


class FakeReviewCandidateRepository(ReviewCandidateRepository):
    def __init__(self) -> None:
        self._candidates: dict[int, ReviewCandidate] = {}

    def register(self, candidate: ReviewCandidate) -> None:
        self._candidates[candidate.id] = candidate  # type: ignore[index]

    def create(self, candidate: ReviewCandidate) -> ReviewCandidate:
        raise NotImplementedError

    def update(self, candidate: ReviewCandidate) -> ReviewCandidate:
        raise NotImplementedError

    def get_by_id(self, candidate_id: int) -> ReviewCandidate | None:
        return self._candidates.get(candidate_id)

    def get_open_by_claim(
        self,
        proposed_claim_id: int,
    ) -> ReviewCandidate | None:
        raise NotImplementedError

    def list_pending(self) -> list[ReviewCandidate]:
        raise NotImplementedError

    def list_by_project(
        self,
        project_id: int,
        *,
        status: ReviewStatus | None = None,
    ) -> list[ReviewCandidate]:
        raise NotImplementedError


class FakeProposedClaimRepository(ProposedClaimRepository):
    def __init__(self) -> None:
        self._claims: dict[int, ProposedClaim] = {}

    def register(self, claim: ProposedClaim) -> None:
        self._claims[claim.id] = claim  # type: ignore[index]

    def create(self, claim: ProposedClaim) -> ProposedClaim:
        raise NotImplementedError

    def get_by_id(self, claim_id: int) -> ProposedClaim | None:
        return self._claims.get(claim_id)

    def find_duplicate(self, *args: object, **kwargs: object):
        raise NotImplementedError

    def list_by_project(self, project_id: int) -> list[ProposedClaim]:
        raise NotImplementedError

    def list_by_document(self, document_id: int) -> list[ProposedClaim]:
        raise NotImplementedError

    def replace_evidence(self, *args: object, **kwargs: object):
        raise NotImplementedError

    def delete(self, claim_id: int) -> None:
        raise NotImplementedError


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



def _evidence() -> tuple[EvidenceReference, ...]:
    return (
        EvidenceReference(
            engineering_index_entry_id=1,
            document_id=5,
            locator=IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE,
                value="3",
            ),
        ),
    )


def _claim(project_id: int = 10) -> ProposedClaim:
    return ProposedClaim(
        id=1,
        project_id=project_id,
        claim_type=ClaimType.EXISTENCE,
        subject=ClaimSubject(value="Cable 295"),
        predicate=None,
        object=None,
        evidence=_evidence(),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _candidate(
    project_id: int = 10,
    status: ReviewStatus = ReviewStatus.APPROVED,
) -> ReviewCandidate:
    return ReviewCandidate(
        id=1,
        project_id=project_id,
        proposed_claim_id=1,
        status=status,
        review_comment=None,
        reviewed_by="engineer.smith" if status is not ReviewStatus.PENDING else None,
        reviewed_at=APPROVED_AT if status is not ReviewStatus.PENDING else None,
        created_at=CREATED_AT,
        updated_at=APPROVED_AT,
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


@pytest.fixture()
def repositories():
    return (
        FakeCanonicalFactRepository(),
        FakeReviewCandidateRepository(),
        FakeProposedClaimRepository(),
        FakeProjectRepository(),
    )


def test_canonicalize_review_candidate_creates_a_fact(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())
    claim_repository.register(_claim())
    project_repository.register(_project())

    result = canonicalization_service.canonicalize_review_candidate(
        fact_repository,
        candidate_repository,
        claim_repository,
        project_repository,
        review_candidate_id=1,
        now=APPROVED_AT,
    )

    assert result.created is True
    assert result.fact.subject.value == "CABLE:C-295"


def test_canonicalize_review_candidate_is_idempotent(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())
    claim_repository.register(_claim())
    project_repository.register(_project())

    first = canonicalization_service.canonicalize_review_candidate(
        fact_repository,
        candidate_repository,
        claim_repository,
        project_repository,
        review_candidate_id=1,
        now=APPROVED_AT,
    )
    second = canonicalization_service.canonicalize_review_candidate(
        fact_repository,
        candidate_repository,
        claim_repository,
        project_repository,
        review_candidate_id=1,
        now=APPROVED_AT,
    )

    assert first.created is True
    assert second.created is False
    assert first.fact.id == second.fact.id


def test_canonicalize_raises_for_an_unknown_candidate(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )

    with pytest.raises(CanonicalizationReviewCandidateNotFoundError):
        canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=999,
            now=APPROVED_AT,
        )


def test_canonicalize_raises_for_a_non_approved_candidate(
    repositories,
) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate(status=ReviewStatus.PENDING))
    claim_repository.register(_claim())
    project_repository.register(_project())

    with pytest.raises(ReviewCandidateNotApprovedError):
        canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=1,
            now=APPROVED_AT,
        )


def test_canonicalize_raises_for_a_missing_claim(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())

    with pytest.raises(CanonicalizationClaimNotFoundError):
        canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=1,
            now=APPROVED_AT,
        )


def test_canonicalize_raises_for_a_missing_project(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())
    claim_repository.register(_claim())

    with pytest.raises(CanonicalizationProjectNotFoundError):
        canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=1,
            now=APPROVED_AT,
        )


def test_canonicalize_raises_for_an_archived_project(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())
    claim_repository.register(_claim())
    project_repository.register(
        replace(
            _project(),
            lifecycle_state=ProjectLifecycleState.ARCHIVED,
        )
    )

    with pytest.raises(ProjectNotCanonicalizableError):
        canonicalization_service.canonicalize_review_candidate(
            fact_repository,
            candidate_repository,
            claim_repository,
            project_repository,
            review_candidate_id=1,
            now=APPROVED_AT,
        )


def test_get_canonical_fact_raises_for_an_unknown_fact(repositories) -> None:
    fact_repository = repositories[0]

    with pytest.raises(CanonicalFactNotFoundError):
        canonicalization_service.get_canonical_fact(fact_repository, 999)


def test_list_canonical_facts_for_project(repositories) -> None:
    fact_repository, candidate_repository, claim_repository, project_repository = (
        repositories
    )
    candidate_repository.register(_candidate())
    claim_repository.register(_claim())
    project_repository.register(_project())

    canonicalization_service.canonicalize_review_candidate(
        fact_repository,
        candidate_repository,
        claim_repository,
        project_repository,
        review_candidate_id=1,
        now=APPROVED_AT,
    )

    facts = canonicalization_service.list_canonical_facts_for_project(
        fact_repository,
        10,
    )

    assert len(facts) == 1
