"""
Application services for Canonicalization (Milestone 11). Each function
is a single use case, orchestrating the domain
(``app.domain.canonicalization``) through the ``CanonicalFactRepository``
port, together with the Review Workflow, Proposed Claims, and Project
bounded contexts' own read-only repository access - never a raw database
session.

This module converts one ``APPROVED`` Review Candidate into a
``CanonicalFact``. It performs no review of its own (Review Workflow
already decided), no extraction (Proposed Claims already produced the
claim), and writes nothing into the Project Knowledge Graph - that is
Milestone 11.1's job, consuming what this module produces.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.canonicalization.canonicalization_exceptions import (
    CanonicalFactNotFoundError,
    CanonicalizationClaimNotFoundError,
    CanonicalizationProjectNotFoundError,
    CanonicalizationReviewCandidateNotFoundError,
    ProjectNotCanonicalizableError,
)
from app.domain.canonicalization.canonicalization_factory import (
    CanonicalizationFactory,
)
from app.domain.canonicalization.canonicalization_models import (
    CanonicalFact,
    CanonicalizationResult,
)
from app.domain.canonicalization.canonicalization_repository import (
    CanonicalFactRepository,
)
from app.domain.project.project_repository import ProjectRepository
from app.domain.proposed_claims.proposed_claim_models import ProposedClaim
from app.domain.proposed_claims.proposed_claim_repository import (
    ProposedClaimRepository,
)
from app.domain.review_workflow.review_candidate_repository import (
    ReviewCandidateRepository,
)
from app.domain.review_workflow.review_workflow_models import (
    ReviewCandidate,
)


def _require_existing_candidate(
    candidate_repository: ReviewCandidateRepository,
    review_candidate_id: int,
) -> ReviewCandidate:
    candidate = candidate_repository.get_by_id(review_candidate_id)

    if candidate is None:
        raise CanonicalizationReviewCandidateNotFoundError(
            review_candidate_id
        )

    return candidate


def _require_existing_claim(
    claim_repository: ProposedClaimRepository,
    proposed_claim_id: int,
) -> ProposedClaim:
    claim = claim_repository.get_by_id(proposed_claim_id)

    if claim is None:
        raise CanonicalizationClaimNotFoundError(proposed_claim_id)

    return claim


def _require_canonicalizable_project(
    project_repository: ProjectRepository,
    project_id: int,
) -> None:
    project = project_repository.get_by_id(project_id)

    if project is None:
        raise CanonicalizationProjectNotFoundError(project_id)

    if not project.is_mutable():
        raise ProjectNotCanonicalizableError(
            project.id,  # type: ignore[arg-type]
            project.lifecycle_state,
        )


def canonicalize_review_candidate(
    fact_repository: CanonicalFactRepository,
    candidate_repository: ReviewCandidateRepository,
    claim_repository: ProposedClaimRepository,
    project_repository: ProjectRepository,
    *,
    review_candidate_id: int,
    now: datetime,
) -> CanonicalizationResult:
    """
    Canonicalizes one approved Review Candidate into a ``CanonicalFact``.

    Idempotent: if this candidate was already canonicalized, the
    existing fact is returned with ``created=False`` and nothing new is
    written - canonicalizing the same approved candidate twice never
    produces a duplicate fact. Raises
    ``CanonicalizationReviewCandidateNotFoundError`` /
    ``CanonicalizationClaimNotFoundError`` for missing references,
    ``ReviewCandidateNotApprovedError`` for a candidate that is not
    ``APPROVED``, and ``ProjectNotCanonicalizableError`` for an
    Archived or Deleted Project.
    """

    existing = fact_repository.get_by_review_candidate(
        review_candidate_id
    )

    if existing is not None:
        return CanonicalizationResult(fact=existing, created=False)

    candidate = _require_existing_candidate(
        candidate_repository,
        review_candidate_id,
    )
    claim = _require_existing_claim(
        claim_repository,
        candidate.proposed_claim_id,
    )
    _require_canonicalizable_project(project_repository, claim.project_id)

    fact = CanonicalizationFactory.canonicalize_claim(
        claim=claim,
        candidate=candidate,
        now=now,
    )
    saved = fact_repository.save(fact)

    return CanonicalizationResult(fact=saved, created=True)


def get_canonical_fact(
    fact_repository: CanonicalFactRepository,
    fact_id: int,
) -> CanonicalFact:
    fact = fact_repository.get_by_id(fact_id)

    if fact is None:
        raise CanonicalFactNotFoundError(fact_id)

    return fact


def list_canonical_facts_for_project(
    fact_repository: CanonicalFactRepository,
    project_id: int,
) -> list[CanonicalFact]:
    return fact_repository.list_by_project(project_id)


def list_canonical_facts_for_document(
    fact_repository: CanonicalFactRepository,
    document_id: int,
) -> list[CanonicalFact]:
    return fact_repository.list_by_document(document_id)
