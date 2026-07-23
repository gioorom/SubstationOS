from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.review_workflow.review_status import ReviewStatus
from app.domain.review_workflow.review_workflow_models import ReviewComment


def _comment_text(value: object) -> object:
    """
    ``ReviewCandidate.review_comment``/``ReviewHistoryEvent.comment``
    are domain ``ReviewComment`` value objects, not bare strings -
    unwrap ``.text`` before Pydantic validates the field.
    """

    if isinstance(value, ReviewComment):
        return value.text

    return value


class ReviewCandidateCreate(BaseModel):
    proposed_claim_id: int


class ReviewDecisionCreate(BaseModel):
    reviewed_by: str = Field(min_length=1, max_length=150)

    comment: str | None = Field(
        default=None,
        max_length=2000,
    )


class ReviewCandidateRead(BaseModel):
    id: int
    project_id: int
    proposed_claim_id: int
    status: ReviewStatus
    review_comment: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_review_comment = field_validator(
        "review_comment",
        mode="before",
    )(_comment_text)


class ReviewHistoryEventRead(BaseModel):
    id: int
    review_candidate_id: int
    from_status: ReviewStatus
    to_status: ReviewStatus
    reviewed_by: str
    comment: str | None
    occurred_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )

    _unwrap_comment = field_validator(
        "comment",
        mode="before",
    )(_comment_text)
