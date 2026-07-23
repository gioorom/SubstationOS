from __future__ import annotations

from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.domain.review_workflow.review_status import ReviewStatus


class ReviewWorkflowError(Exception):
    """
    Base class for every exception raised by the Review Workflow
    bounded context.
    """


class InvalidReviewerError(ReviewWorkflowError):
    def __init__(self, reviewed_by: str) -> None:
        self.reviewed_by = reviewed_by

        super().__init__(
            f"Invalid reviewer: '{reviewed_by}'. A reviewer identity is "
            "required to record a decision."
        )


class InvalidReviewCommentError(ReviewWorkflowError):
    def __init__(self, text: str) -> None:
        self.text = text

        super().__init__(
            f"Invalid review comment: '{text}'. A comment, when given, "
            "must not be blank."
        )


class ReviewCommentRequiredError(ReviewWorkflowError):
    """
    ``REJECTED`` and ``NEEDS_CHANGES`` decisions must explain themselves;
    an outcome with no comment gives the document's author nothing to
    act on.
    """

    def __init__(self, status: ReviewStatus) -> None:
        self.status = status

        super().__init__(
            f"A review comment is required for a '{status.value}' "
            "decision."
        )


class InvalidReviewStatusTransitionError(ReviewWorkflowError):
    def __init__(
        self,
        current: ReviewStatus,
        target: ReviewStatus,
    ) -> None:
        self.current = current
        self.target = target

        super().__init__(
            f"Cannot move a review candidate from '{current.value}' to "
            f"'{target.value}'."
        )


class ReviewCandidateNotFoundError(ReviewWorkflowError):
    def __init__(self, candidate_id: int) -> None:
        self.candidate_id = candidate_id

        super().__init__(f"Review candidate '{candidate_id}' not found.")


class ReviewedProposedClaimNotFoundError(ReviewWorkflowError):
    """
    The Proposed Claim a Review Candidate was to be created against does
    not exist.
    """

    def __init__(self, proposed_claim_id: int) -> None:
        self.proposed_claim_id = proposed_claim_id

        super().__init__(
            f"Proposed claim '{proposed_claim_id}' not found."
        )


class DuplicateOpenReviewCandidateError(ReviewWorkflowError):
    """
    A Proposed Claim may have at most one open (``PENDING`` or
    ``NEEDS_CHANGES``) Review Candidate at a time. A new review cycle
    for the same claim is only possible once the open candidate reaches
    a terminal outcome (``APPROVED``/``REJECTED``).
    """

    def __init__(
        self,
        proposed_claim_id: int,
        existing_candidate_id: int,
    ) -> None:
        self.proposed_claim_id = proposed_claim_id
        self.existing_candidate_id = existing_candidate_id

        super().__init__(
            f"Proposed claim '{proposed_claim_id}' already has an open "
            f"review candidate ('{existing_candidate_id}')."
        )


class ReviewedProjectNotFoundError(ReviewWorkflowError):
    """
    The Project a reviewed Proposed Claim points to no longer resolves -
    a data-integrity anomaly (projects are only ever soft-deleted, never
    hard-deleted), not an ordinary "not found" the caller can act on by
    retrying with different input.
    """

    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(
            f"Project '{project_id}' referenced by a Review Candidate "
            "could not be found."
        )


class ProjectNotReviewableError(ReviewWorkflowError):
    """
    Review actions are writes against a Project's data; Archived and
    Deleted projects are read-only, per the Project Lifecycle - the same
    rule the Engineering Index enforces for indexing.
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
            "is read-only; its Review Workflow cannot be written to."
        )
