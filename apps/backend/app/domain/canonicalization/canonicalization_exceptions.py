from __future__ import annotations

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.review_workflow.review_status import ReviewStatus


class CanonicalizationError(Exception):
    """
    Base class for every exception raised by the Canonicalization
    bounded context.
    """


class CanonicalizationReviewCandidateNotFoundError(CanonicalizationError):
    def __init__(self, review_candidate_id: int) -> None:
        self.review_candidate_id = review_candidate_id

        super().__init__(
            f"Review candidate '{review_candidate_id}' not found."
        )


class CanonicalizationClaimNotFoundError(CanonicalizationError):
    def __init__(self, proposed_claim_id: int) -> None:
        self.proposed_claim_id = proposed_claim_id

        super().__init__(
            f"Proposed claim '{proposed_claim_id}' not found."
        )


class ReviewCandidateNotApprovedError(CanonicalizationError):
    """
    Only an ``APPROVED`` Review Candidate may be canonicalized -
    canonicalization is never performed on ``PENDING``, ``REJECTED``, or
    ``NEEDS_CHANGES`` output. Canonicalization performs no review of its
    own; it trusts Review Workflow's decision entirely.
    """

    def __init__(
        self,
        review_candidate_id: int,
        status: ReviewStatus,
    ) -> None:
        self.review_candidate_id = review_candidate_id
        self.status = status

        super().__init__(
            f"Review candidate '{review_candidate_id}' is "
            f"'{status.value}', not 'approved'; it cannot be "
            "canonicalized."
        )


class CrossProjectCanonicalizationError(CanonicalizationError):
    """
    A data-integrity anomaly: the Review Candidate's own ``project_id``
    must always equal the Proposed Claim it reviews - Review Workflow
    enforces this at candidate-creation time (ADR-0001), so this should
    never actually trigger in practice.
    """

    def __init__(
        self,
        claim_project_id: int,
        candidate_project_id: int,
    ) -> None:
        self.claim_project_id = claim_project_id
        self.candidate_project_id = candidate_project_id

        super().__init__(
            "Review candidate's project "
            f"('{candidate_project_id}') does not match its claim's "
            f"project ('{claim_project_id}')."
        )


class CanonicalizationProjectNotFoundError(CanonicalizationError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(
            f"Project '{project_id}' referenced by a Proposed Claim "
            "could not be found."
        )


class ProjectNotCanonicalizableError(CanonicalizationError):
    """
    Canonicalization writes new persistent data scoped to a Project;
    Archived and Deleted projects are read-only, per the Project
    Lifecycle - the same rule every other write path in this system
    enforces.
    """

    def __init__(
        self,
        project_id: int,
        lifecycle_state: ProjectLifecycleState,
    ) -> None:
        self.project_id = project_id
        self.lifecycle_state = lifecycle_state

        super().__init__(
            f"Project '{project_id}' is '{lifecycle_state.value}' and "
            "is read-only; no fact can be canonicalized into it."
        )


class UnsupportedClaimTypeError(CanonicalizationError):
    def __init__(self, claim_type: object) -> None:
        self.claim_type = claim_type

        super().__init__(
            f"'{claim_type}' is not a supported claim type. Supported "
            f"types: {', '.join(t.value for t in ClaimType)}."
        )


class UnrecognizedEntityReferenceError(CanonicalizationError):
    """
    ``raw_value`` does not match any recognized entity-reference shape
    (a letter prefix followed by a number, e.g. "C-295", "TR2"). This is
    a deterministic shape check, not fuzzy matching - an unrecognized
    reference is rejected, never guessed at.
    """

    def __init__(self, raw_value: str) -> None:
        self.raw_value = raw_value

        super().__init__(
            f"'{raw_value}' does not match a recognized entity "
            "reference shape (a letter prefix followed by a number, "
            "e.g. 'C-295')."
        )


class UnknownCanonicalEntityTypeError(CanonicalizationError):
    """
    ``raw_value`` has the shape of an entity reference, but its prefix
    token is not in the deterministic entity-type vocabulary this
    bounded context recognizes.
    """

    def __init__(self, raw_value: str, token: str) -> None:
        self.raw_value = raw_value
        self.token = token

        super().__init__(
            f"'{token}' (from '{raw_value}') is not a recognized "
            "canonical entity type."
        )


class UnknownCanonicalPredicateError(CanonicalizationError):
    """
    ``raw_value`` is not in the deterministic predicate-synonym
    vocabulary this bounded context recognizes. No semantic similarity
    or AI is used to guess a match.
    """

    def __init__(self, raw_value: str) -> None:
        self.raw_value = raw_value

        super().__init__(
            f"'{raw_value}' is not a recognized canonical predicate."
        )


class CanonicalFactNotFoundError(CanonicalizationError):
    def __init__(self, fact_id: int) -> None:
        self.fact_id = fact_id

        super().__init__(f"Canonical fact '{fact_id}' not found.")
