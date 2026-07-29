from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.project.project_models import (
    UNVERSIONED_CANONICAL_DOMAIN,
    Project,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    ProposedClaim,
)
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.domain.review_workflow.review_candidate_repository import (
    ReviewCandidateRepository,
)
from app.domain.review_workflow.review_history_repository import (
    ReviewHistoryRepository,
)
from app.domain.review_workflow.review_status import (
    OPEN_STATUSES,
    ReviewStatus,
)
from app.domain.review_workflow.review_workflow_exceptions import (
    DuplicateOpenReviewCandidateError,
    InvalidReviewStatusTransitionError,
    ProjectNotReviewableError,
    ReviewCandidateNotFoundError,
    ReviewCommentRequiredError,
    ReviewedProposedClaimNotFoundError,
)
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
    ReviewHistoryEvent,
)
from app.services import review_workflow_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
DECIDED_AT = datetime(2026, 1, 2, 9, 0, 0)


class FakeProposedClaimRepository(ProposedClaimRepository):
    def __init__(self) -> None:
        self._claims: dict[int, ProposedClaim] = {}
        self._next_id = 1

    def register(self, claim: ProposedClaim) -> ProposedClaim:
        claim = replace(claim, id=self._next_id)
        self._claims[self._next_id] = claim
        self._next_id += 1

        return claim

    def create(self, claim: ProposedClaim) -> ProposedClaim:
        return self.register(claim)

    def get_by_id(self, claim_id: int) -> ProposedClaim | None:
        return self._claims.get(claim_id)

    def find_duplicate(self, *args, **kwargs) -> ProposedClaim | None:
        return None

    def list_by_project(self, project_id: int) -> list[ProposedClaim]:
        return [
            claim
            for claim in self._claims.values()
            if claim.project_id == project_id
        ]

    def list_by_document(self, document_id: int) -> list[ProposedClaim]:
        return [
            claim
            for claim in self._claims.values()
            if any(
                reference.document_id == document_id
                for reference in claim.evidence
            )
        ]

    def replace_evidence(self, claim_id: int, evidence) -> ProposedClaim:
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
        for project in self._projects.values():
            if project.code == code:
                return project

        return None

    def save(self, project: Project) -> Project:
        self._projects[project.id] = project  # type: ignore[index]

        return project

    def list_all(self, *, include_deleted: bool = False) -> list[Project]:
        return list(self._projects.values())

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



class FakeReviewCandidateRepository(ReviewCandidateRepository):
    def __init__(self) -> None:
        self._candidates: dict[int, ReviewCandidate] = {}
        self._next_id = 1

    def create(self, candidate: ReviewCandidate) -> ReviewCandidate:
        candidate = replace(candidate, id=self._next_id)
        self._candidates[self._next_id] = candidate
        self._next_id += 1

        return candidate

    def update(self, candidate: ReviewCandidate) -> ReviewCandidate:
        self._candidates[candidate.id] = candidate  # type: ignore[index]

        return candidate

    def get_by_id(self, candidate_id: int) -> ReviewCandidate | None:
        return self._candidates.get(candidate_id)

    def get_open_by_claim(
        self,
        proposed_claim_id: int,
    ) -> ReviewCandidate | None:
        for candidate in self._candidates.values():
            if (
                candidate.proposed_claim_id == proposed_claim_id
                and candidate.status in OPEN_STATUSES
            ):
                return candidate

        return None

    def list_pending(self) -> list[ReviewCandidate]:
        return [
            candidate
            for candidate in self._candidates.values()
            if candidate.status is ReviewStatus.PENDING
        ]

    def list_by_project(
        self,
        project_id: int,
        *,
        status: ReviewStatus | None = None,
    ) -> list[ReviewCandidate]:
        return [
            candidate
            for candidate in self._candidates.values()
            if candidate.project_id == project_id
            and (status is None or candidate.status is status)
        ]


class FakeReviewHistoryRepository(ReviewHistoryRepository):
    def __init__(self) -> None:
        self._events: list[ReviewHistoryEvent] = []
        self._next_id = 1

    def append(self, event: ReviewHistoryEvent) -> ReviewHistoryEvent:
        event = replace(event, id=self._next_id)
        self._next_id += 1
        self._events.append(event)

        return event

    def list_by_candidate(
        self,
        review_candidate_id: int,
    ) -> list[ReviewHistoryEvent]:
        return [
            event
            for event in self._events
            if event.review_candidate_id == review_candidate_id
        ]


def _project(
    project_id: int,
    lifecycle_state: ProjectLifecycleState,
) -> Project:
    return Project(
        id=project_id,
        name=f"Project {project_id}",
        code=f"CODE-{project_id}",
        customer="Acme Utilities",
        epc=None,
        country=None,
        location=None,
        description=None,
        lifecycle_state=lifecycle_state,
        canonical_domain_version=UNVERSIONED_CANONICAL_DOMAIN,
        created_by=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


@pytest.fixture()
def candidate_repository() -> FakeReviewCandidateRepository:
    return FakeReviewCandidateRepository()


@pytest.fixture()
def history_repository() -> FakeReviewHistoryRepository:
    return FakeReviewHistoryRepository()


@pytest.fixture()
def project_repository() -> FakeProjectRepository:
    repository = FakeProjectRepository()
    repository.register(_project(10, ProjectLifecycleState.ACTIVE))
    repository.register(_project(20, ProjectLifecycleState.ACTIVE))
    repository.register(_project(30, ProjectLifecycleState.ARCHIVED))

    return repository


@pytest.fixture()
def claim_repository() -> FakeProposedClaimRepository:
    repository = FakeProposedClaimRepository()
    repository.register(
        ProposedClaim(
            id=None,
            project_id=10,
            claim_type=ClaimType.RELATIONSHIP,
            subject=ClaimSubject(value="Cable C-295"),
            predicate=ClaimPredicate(value="FEEDS"),
            object=ClaimObject(value="Transformer TR-02"),
            evidence=(),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
    )
    repository.register(
        ProposedClaim(
            id=None,
            project_id=30,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="Transformer TR-09"),
            predicate=None,
            object=None,
            evidence=(),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
    )
    repository.register(
        ProposedClaim(
            id=None,
            project_id=20,
            claim_type=ClaimType.EXISTENCE,
            subject=ClaimSubject(value="Cable C-410"),
            predicate=None,
            object=None,
            evidence=(),
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
    )

    return repository


def test_create_review_candidate_succeeds_for_a_reviewable_claim(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )

    assert candidate.id is not None
    assert candidate.project_id == 10
    assert candidate.proposed_claim_id == 1
    assert candidate.status is ReviewStatus.PENDING


def test_create_review_candidate_raises_for_an_unknown_claim(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    with pytest.raises(ReviewedProposedClaimNotFoundError):
        review_workflow_service.create_review_candidate(
            candidate_repository,
            claim_repository,
            project_repository,
            proposed_claim_id=999,
            now=CREATED_AT,
        )


def test_create_review_candidate_rejects_an_archived_project(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    with pytest.raises(ProjectNotReviewableError):
        review_workflow_service.create_review_candidate(
            candidate_repository,
            claim_repository,
            project_repository,
            proposed_claim_id=2,
            now=CREATED_AT,
        )


def test_create_review_candidate_rejects_a_duplicate_open_candidate(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )

    with pytest.raises(DuplicateOpenReviewCandidateError):
        review_workflow_service.create_review_candidate(
            candidate_repository,
            claim_repository,
            project_repository,
            proposed_claim_id=1,
            now=CREATED_AT,
        )


def test_create_review_candidate_allows_a_new_cycle_after_a_terminal_outcome(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    first = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    review_workflow_service.reject_review_candidate(
        candidate_repository,
        FakeReviewHistoryRepository(),
        project_repository,
        candidate_id=first.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        comment="Wrong identifier.",
        now=DECIDED_AT,
    )

    second = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=DECIDED_AT,
    )

    assert second.id != first.id
    assert second.status is ReviewStatus.PENDING


def test_approve_review_candidate_transitions_to_approved_and_records_history(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )

    approved = review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        now=DECIDED_AT,
    )

    assert approved.status is ReviewStatus.APPROVED
    assert approved.reviewed_by == "engineer@acme.com"
    assert approved.reviewed_at == DECIDED_AT

    events = history_repository.list_by_candidate(candidate.id)  # type: ignore[arg-type]

    assert len(events) == 1
    assert events[0].from_status is ReviewStatus.PENDING
    assert events[0].to_status is ReviewStatus.APPROVED


def test_reject_review_candidate_requires_a_comment(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )

    with pytest.raises(ReviewCommentRequiredError):
        review_workflow_service.reject_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            reviewed_by="engineer@acme.com",
            comment=None,
            now=DECIDED_AT,
        )


def test_approved_candidate_cannot_become_pending_again(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        now=DECIDED_AT,
    )

    with pytest.raises(InvalidReviewStatusTransitionError):
        review_workflow_service.resubmit_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            reviewed_by="author@acme.com",
            now=DECIDED_AT,
        )


def test_rejected_candidate_cannot_become_approved_without_a_new_cycle(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    review_workflow_service.reject_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        comment="Wrong identifier.",
        now=DECIDED_AT,
    )

    with pytest.raises(InvalidReviewStatusTransitionError):
        review_workflow_service.approve_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            reviewed_by="engineer@acme.com",
            now=DECIDED_AT,
        )


def test_needs_changes_loops_back_to_pending_via_resubmit(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    review_workflow_service.request_review_changes(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        comment="Please confirm the rated voltage.",
        now=DECIDED_AT,
    )

    resubmitted = review_workflow_service.resubmit_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="author@acme.com",
        now=DECIDED_AT,
    )

    assert resubmitted.status is ReviewStatus.PENDING

    approved = review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        now=DECIDED_AT,
    )

    assert approved.status is ReviewStatus.APPROVED

    events = history_repository.list_by_candidate(candidate.id)  # type: ignore[arg-type]

    assert [event.to_status for event in events] == [
        ReviewStatus.NEEDS_CHANGES,
        ReviewStatus.PENDING,
        ReviewStatus.APPROVED,
    ]


def test_approve_review_candidate_raises_for_an_unknown_candidate(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    project_repository: FakeProjectRepository,
) -> None:
    with pytest.raises(ReviewCandidateNotFoundError):
        review_workflow_service.approve_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=999,
            reviewed_by="engineer@acme.com",
            now=DECIDED_AT,
        )


def test_approve_review_candidate_rejects_a_project_archived_after_creation(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=3,
        now=CREATED_AT,
    )

    # Project 20 gets archived while the candidate sits open.
    project_repository.register(_project(20, ProjectLifecycleState.ARCHIVED))

    with pytest.raises(ProjectNotReviewableError):
        review_workflow_service.approve_review_candidate(
            candidate_repository,
            history_repository,
            project_repository,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            reviewed_by="engineer@acme.com",
            now=DECIDED_AT,
        )


def test_get_review_candidate_raises_for_an_unknown_candidate(
    candidate_repository: FakeReviewCandidateRepository,
) -> None:
    with pytest.raises(ReviewCandidateNotFoundError):
        review_workflow_service.get_review_candidate(
            candidate_repository,
            999,
        )


def test_list_pending_review_candidates_returns_only_pending(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    pending = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    approved = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=3,
        now=CREATED_AT,
    )
    review_workflow_service.approve_review_candidate(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=approved.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        now=DECIDED_AT,
    )

    result = review_workflow_service.list_pending_review_candidates(
        candidate_repository
    )

    assert [candidate.id for candidate in result] == [pending.id]


def test_list_review_candidates_for_project_does_not_leak_across_projects(
    candidate_repository: FakeReviewCandidateRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,  # project 10
        now=CREATED_AT,
    )
    review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=3,  # project 20
        now=CREATED_AT,
    )

    project_10 = (
        review_workflow_service.list_review_candidates_for_project(
            candidate_repository,
            10,
        )
    )
    project_20 = (
        review_workflow_service.list_review_candidates_for_project(
            candidate_repository,
            20,
        )
    )

    assert len(project_10) == 1
    assert project_10[0].proposed_claim_id == 1
    assert len(project_20) == 1
    assert project_20[0].proposed_claim_id == 3


def test_get_review_history_returns_events_in_order(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
    claim_repository: FakeProposedClaimRepository,
    project_repository: FakeProjectRepository,
) -> None:
    candidate = review_workflow_service.create_review_candidate(
        candidate_repository,
        claim_repository,
        project_repository,
        proposed_claim_id=1,
        now=CREATED_AT,
    )
    review_workflow_service.request_review_changes(
        candidate_repository,
        history_repository,
        project_repository,
        candidate_id=candidate.id,  # type: ignore[arg-type]
        reviewed_by="engineer@acme.com",
        comment="Please confirm the rated voltage.",
        now=DECIDED_AT,
    )

    history = review_workflow_service.get_review_history(
        candidate_repository,
        history_repository,
        candidate.id,  # type: ignore[arg-type]
    )

    assert [event.to_status for event in history] == [
        ReviewStatus.NEEDS_CHANGES
    ]


def test_get_review_history_raises_for_an_unknown_candidate(
    candidate_repository: FakeReviewCandidateRepository,
    history_repository: FakeReviewHistoryRepository,
) -> None:
    with pytest.raises(ReviewCandidateNotFoundError):
        review_workflow_service.get_review_history(
            candidate_repository,
            history_repository,
            999,
        )
