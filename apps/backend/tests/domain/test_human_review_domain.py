"""
The Human Review domain, tested as pure values.

No database, no request, no clock of its own. The centrepiece is the
applicability section: it specifies, one case at a time, what happens to a
recorded judgement when the pipeline runs again - which is the hardest
question this milestone had to answer and the one a careless
implementation gets wrong silently.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.domain.human_review.review_applicability import (
    CurrentPipelineState,
    ReviewApplicability,
    evaluate,
    has_integrity,
)
from app.domain.human_review.review_events import (
    ReviewBecameHistorical,
    ReviewEventType,
    ReviewRequiresRevalidation,
    event_for_applicability,
)
from app.domain.human_review.review_exceptions import (
    InvalidReviewCommentError,
    InvalidReviewSnapshotError,
    InvalidReviewTargetError,
    ReviewPolicyViolationError,
)
from app.domain.human_review.review_models import (
    MAX_COMMENT_LENGTH,
    Review,
    ReviewComment,
    ReviewerIdentity,
)
from app.domain.human_review.review_policy import (
    DECISIONS_REQUIRING_COMMENT,
    check,
    requires_comment,
)
from app.domain.human_review.review_projection import (
    build_history,
    project,
)
from app.domain.human_review.review_snapshot import (
    ReviewSnapshot,
    fingerprint_support,
)
from app.domain.human_review.review_target import (
    ReviewTarget,
    ReviewTargetType,
)
from app.domain.human_review.review_vocabulary import (
    REASONS_FOR_DECISION,
    ReviewDecision,
    ReviewReason,
    reason_permitted,
)

NOW = datetime(2026, 7, 30, 9, 0, 0)

STATEMENT_KEY = "a" * 64


def _snapshot(**overrides) -> ReviewSnapshot:
    defaults = dict(
        content_checksum="c" * 64,
        semantic_rule_id="rated_power_from_associated_power_quantity",
        semantic_rule_version="1.0",
        semantic_contract_version="1.0",
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint=fingerprint_support(("fact-1",)),
        support_count=1,
    )
    defaults.update(overrides)

    return ReviewSnapshot(**defaults)


def _review(
    *,
    decision: ReviewDecision = ReviewDecision.APPROVED,
    reason: ReviewReason = ReviewReason.CONFIRMED_BY_SOURCE,
    comment: str | None = None,
    recorded_at: datetime = NOW,
    snapshot: ReviewSnapshot | None = None,
    review_id: int = 1,
) -> Review:
    return Review(
        review_id=review_id,
        target=ReviewTarget.semantic_statement(STATEMENT_KEY, 10),
        decision=decision,
        reason=reason,
        comment=None if comment is None else ReviewComment(comment),
        reviewer=ReviewerIdentity(
            user_id=7,
            display_name="Ada Lovelace",
            email="ada@substationos.test",
            role="engineer",
        ),
        snapshot=snapshot or _snapshot(),
        recorded_at=recorded_at,
    )


# --- The target ----------------------------------------------------------


def test_a_target_names_an_artefact_and_never_contains_one() -> None:
    """
    The structural guarantee the whole context rests on: there is no
    field into which a semantic statement could be copied.
    """

    fields = set(ReviewTarget.__dataclass_fields__)

    assert fields == {"target_type", "target_key", "document_id"}


def test_only_semantic_statements_are_reviewable_today() -> None:
    """
    Generic, and currently one member. Adding evidence, entities and
    facts "ready for later" would be three values no endpoint accepts and
    no projection understands.
    """

    assert {item.value for item in ReviewTargetType} == {
        "semantic_statement"
    }


@pytest.mark.parametrize(
    "key, document_id",
    [("", 10), ("   ", 10), ("x" * 129, 10), ("key", 0), ("key", -1)],
)
def test_a_target_that_identifies_nothing_is_refused(
    key: str, document_id: int
) -> None:
    with pytest.raises(InvalidReviewTargetError):
        ReviewTarget.semantic_statement(key, document_id)


# --- The vocabulary ------------------------------------------------------


def test_there_are_exactly_three_decisions() -> None:
    assert {item.value for item in ReviewDecision} == {
        "approved",
        "rejected",
        "needs_investigation",
    }


def test_every_decision_declares_which_reasons_it_admits() -> None:
    """Total over the enum, so no decision has an undefined vocabulary."""

    assert set(REASONS_FOR_DECISION) == set(ReviewDecision)
    assert all(REASONS_FOR_DECISION[item] for item in ReviewDecision)


def test_a_rejection_reason_cannot_accompany_an_approval() -> None:
    """
    "Approved because the interpretation is incorrect" is a sentence the
    trail must not be able to contain.
    """

    assert not reason_permitted(
        ReviewDecision.APPROVED, ReviewReason.INCORRECT_INTERPRETATION
    )
    assert reason_permitted(
        ReviewDecision.REJECTED, ReviewReason.INCORRECT_INTERPRETATION
    )


def test_other_is_available_for_every_decision() -> None:
    """The escape hatch, and the one reason that always needs prose."""

    for decision in ReviewDecision:
        assert reason_permitted(decision, ReviewReason.OTHER)


# --- The policy ----------------------------------------------------------


def test_a_rejection_requires_an_explanation() -> None:
    with pytest.raises(ReviewPolicyViolationError) as caught:
        check(
            ReviewDecision.REJECTED,
            ReviewReason.INCORRECT_INTERPRETATION,
            None,
        )

    assert any("requires a comment" in item for item in caught.value.violations)


def test_needing_investigation_requires_an_explanation() -> None:
    assert requires_comment(
        ReviewDecision.NEEDS_INVESTIGATION,
        ReviewReason.AMBIGUOUS_EVIDENCE,
    )


def test_an_approval_under_a_catalogued_reason_may_stand_alone() -> None:
    """
    Requiring prose for the common, uncontroversial case is how a review
    process becomes something engineers work around.
    """

    check(
        ReviewDecision.APPROVED, ReviewReason.CONFIRMED_BY_SOURCE, None
    )


def test_other_always_requires_an_explanation() -> None:
    """It says only that the catalogue did not fit."""

    assert requires_comment(ReviewDecision.APPROVED, ReviewReason.OTHER)

    with pytest.raises(ReviewPolicyViolationError):
        check(ReviewDecision.APPROVED, ReviewReason.OTHER, None)


def test_a_mismatched_reason_is_refused() -> None:
    with pytest.raises(ReviewPolicyViolationError) as caught:
        check(
            ReviewDecision.APPROVED,
            ReviewReason.INCORRECT_INTERPRETATION,
            None,
        )

    assert any(
        "is not a reason for" in item for item in caught.value.violations
    )


def test_every_violation_is_reported_at_once() -> None:
    """
    A reviewer should learn everything wrong with their submission in one
    attempt, not one round trip at a time.
    """

    with pytest.raises(ReviewPolicyViolationError) as caught:
        check(
            ReviewDecision.REJECTED,
            ReviewReason.CONFIRMED_BY_SOURCE,
            None,
        )

    assert len(caught.value.violations) == 2


def test_the_decisions_requiring_comment_are_the_inconclusive_ones() -> None:
    assert DECISIONS_REQUIRING_COMMENT == frozenset(
        {ReviewDecision.REJECTED, ReviewDecision.NEEDS_INVESTIGATION}
    )


# --- Comments ------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_a_comment_that_says_nothing_is_refused(text: str) -> None:
    with pytest.raises(InvalidReviewCommentError):
        ReviewComment(text)


def test_a_comment_is_bounded() -> None:
    with pytest.raises(InvalidReviewCommentError):
        ReviewComment("x" * (MAX_COMMENT_LENGTH + 1))


def test_a_comment_is_stripped() -> None:
    assert ReviewComment("  la sigla è ambigua  ").text == (
        "la sigla è ambigua"
    )


# --- The snapshot --------------------------------------------------------


def test_a_snapshot_records_identity_and_never_the_artefact() -> None:
    """
    A snapshot holding what the statement *said* would be a copy of
    engineering knowledge living outside the pipeline that produced it.
    """

    fields = set(ReviewSnapshot.__dataclass_fields__)

    for forbidden in (
        "statement_type",
        "subject_entity_key",
        "object_entity_key",
        "value",
        "unit",
        "supporting_fact_keys",
    ):
        assert forbidden not in fields


@pytest.mark.parametrize(
    "missing",
    [
        "content_checksum",
        "semantic_rule_id",
        "semantic_rule_version",
        "semantic_contract_version",
        "resolution_policy_version",
        "fact_policy_version",
        "semantic_policy_version",
        "support_fingerprint",
    ],
)
def test_a_snapshot_that_identifies_nothing_is_refused(
    missing: str,
) -> None:
    with pytest.raises(InvalidReviewSnapshotError):
        _snapshot(**{missing: ""})


def test_a_support_fingerprint_ignores_the_order_facts_arrive_in() -> None:
    """The *set* of facts is the identity, not the order returned."""

    assert fingerprint_support(("b", "a")) == fingerprint_support(("a", "b"))


def test_a_support_fingerprint_distinguishes_different_support() -> None:
    assert fingerprint_support(("a",)) != fingerprint_support(("a", "b"))


def test_a_support_fingerprint_cannot_be_confused_by_concatenation() -> None:
    """``("ab", "c")`` and ``("a", "bc")`` must not fingerprint alike."""

    assert fingerprint_support(("ab", "c")) != fingerprint_support(
        ("a", "bc")
    )


# --- Applicability: what a pipeline re-run does to a judgement -----------


def test_a_review_still_applies_when_nothing_changed() -> None:
    """
    The re-run reproduced the same `statement_key`, so the review is
    about the statement in front of the engineer today. Nothing to do.
    """

    snapshot = _snapshot()

    current = CurrentPipelineState(
        exists=True,
        target_key_present=True,
        content_checksum=snapshot.content_checksum,
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint=snapshot.support_fingerprint,
    )

    assert evaluate(snapshot, current) is ReviewApplicability.APPLIES


def test_a_semantic_rule_change_requires_revalidation() -> None:
    """
    `statement_key` hashes the rule version, so a rule bump produces a
    differently-keyed statement. The old judgement is **marked**, never
    discarded, and never carried across - that would attribute to an
    engineer an opinion about something they never saw.
    """

    current = CurrentPipelineState(
        exists=True,
        target_key_present=False,
        content_checksum="c" * 64,
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="2.0",
    )

    assert (
        evaluate(_snapshot(), current)
        is ReviewApplicability.REQUIRES_REVALIDATION
    )


def test_a_re_ingested_document_requires_revalidation() -> None:
    """Different bytes, different facts, different keys."""

    current = CurrentPipelineState(
        exists=True,
        target_key_present=False,
        content_checksum="d" * 64,
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
    )

    assert (
        evaluate(_snapshot(), current)
        is ReviewApplicability.REQUIRES_REVALIDATION
    )


def test_a_statement_that_simply_disappeared_requires_revalidation() -> None:
    """
    The rules ran and produced no statement for this subject - it became
    ambiguous, or its supporting fact was declined. The judgement is not
    thrown away; it is marked for a human to look at.
    """

    current = CurrentPipelineState(
        exists=True,
        target_key_present=False,
        content_checksum="c" * 64,
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
    )

    assert (
        evaluate(_snapshot(), current)
        is ReviewApplicability.REQUIRES_REVALIDATION
    )


def test_a_review_is_orphaned_when_there_is_nothing_to_compare() -> None:
    """
    The semantic stage has not been run since, or its set is gone. Nothing
    is wrong with the review - there is simply nothing to check it
    against, and that is not the same as the pipeline having moved on.
    """

    assert (
        evaluate(_snapshot(), CurrentPipelineState.absent())
        is ReviewApplicability.ORPHANED
    )


def test_a_new_statement_appearing_does_not_disturb_an_existing_review() -> (
    None
):
    """
    Statements are matched by key. Another statement appearing in the set
    is not this statement changing.
    """

    snapshot = _snapshot()

    current = CurrentPipelineState(
        exists=True,
        target_key_present=True,
        content_checksum=snapshot.content_checksum,
        resolution_policy_version="1.0",
        fact_policy_version="1.0",
        semantic_policy_version="1.0",
        support_fingerprint=snapshot.support_fingerprint,
    )

    assert evaluate(snapshot, current) is ReviewApplicability.APPLIES


def test_applicability_is_total_over_its_inputs() -> None:
    """Every combination resolves; none of them is "unknown"."""

    for exists in (True, False):
        for present in (True, False):
            result = evaluate(
                _snapshot(),
                CurrentPipelineState(
                    exists=exists, target_key_present=present
                ),
            )

            assert result in set(ReviewApplicability)


def test_a_review_is_never_silently_discarded() -> None:
    """
    There is no applicability meaning "gone". The record survives every
    pipeline change; only its relationship to today's pipeline changes.
    """

    assert {item.value for item in ReviewApplicability} == {
        "applies",
        "requires_revalidation",
        "orphaned",
    }


# --- Snapshot integrity --------------------------------------------------


def test_a_matching_key_with_matching_support_has_integrity() -> None:
    snapshot = _snapshot()

    assert has_integrity(
        snapshot,
        CurrentPipelineState(
            exists=True,
            target_key_present=True,
            support_fingerprint=snapshot.support_fingerprint,
        ),
    )


def test_a_matching_key_with_different_support_is_an_integrity_failure() -> (
    None
):
    """
    Should be impossible - `statement_key` hashes the fact source. Which
    is exactly why it is checked: if it ever happens, the identity of an
    engineering artefact has stopped meaning what it claims.
    """

    assert not has_integrity(
        _snapshot(),
        CurrentPipelineState(
            exists=True,
            target_key_present=True,
            support_fingerprint=fingerprint_support(("other-fact",)),
        ),
    )


def test_integrity_is_vacuous_when_there_is_nothing_to_compare() -> None:
    assert has_integrity(
        _snapshot(),
        CurrentPipelineState(exists=True, target_key_present=False),
    )


# --- Projection ----------------------------------------------------------


def test_a_target_nobody_reviewed_has_no_decision() -> None:
    """
    Distinct from every decision, and never rendered as one.
    """

    projection = project(
        ReviewTarget.semantic_statement(STATEMENT_KEY, 10),
        (),
        CurrentPipelineState.absent(),
    )

    assert projection.current is None
    assert projection.decision is None
    assert projection.is_reviewed is False
    assert projection.review_count == 0


def test_the_current_decision_is_the_newest_review() -> None:
    """
    A projection, never a stored flag. Taking the newest rather than
    scanning for a status is what keeps it impossible for a stored
    `current` to disagree with the order reviews were written in.
    """

    newest = _review(
        decision=ReviewDecision.REJECTED,
        reason=ReviewReason.INCORRECT_INTERPRETATION,
        comment="la potenza non è quella nominale",
        recorded_at=NOW + timedelta(days=1),
        review_id=2,
    )
    oldest = _review(review_id=1)

    projection = project(
        newest.target,
        (newest, oldest),
        CurrentPipelineState(exists=True, target_key_present=True),
    )

    assert projection.decision is ReviewDecision.REJECTED
    assert projection.review_count == 2


def test_the_projection_type_has_no_settable_decision() -> None:
    """
    Structural: there is no field on the projection or on a review that a
    caller could write a "current" flag into.
    """

    assert "current_decision" not in Review.__dataclass_fields__
    assert "is_current" not in Review.__dataclass_fields__
    assert "superseded" not in Review.__dataclass_fields__
    assert "status" not in Review.__dataclass_fields__


def test_history_marks_everything_but_the_newest_as_superseded() -> None:
    entries = build_history(
        (
            _review(review_id=3, recorded_at=NOW + timedelta(days=2)),
            _review(review_id=2, recorded_at=NOW + timedelta(days=1)),
            _review(review_id=1),
        ),
        CurrentPipelineState(exists=True, target_key_present=True),
    )

    assert [entry.superseded for entry in entries] == [False, True, True]


def test_history_reports_each_entry_own_applicability() -> None:
    """
    An entry recorded before a rule change reports
    `requires_revalidation` even when a newer review applies, because
    that is the truth about the judgement that entry records.
    """

    old = _review(
        review_id=1, snapshot=_snapshot(semantic_rule_version="0.9")
    )

    entries = build_history(
        (old,),
        CurrentPipelineState(exists=True, target_key_present=False),
    )

    assert (
        entries[0].applicability
        is ReviewApplicability.REQUIRES_REVALIDATION
    )


def test_building_a_history_is_deterministic() -> None:
    history = (
        _review(review_id=2, recorded_at=NOW + timedelta(days=1)),
        _review(review_id=1),
    )
    state = CurrentPipelineState(exists=True, target_key_present=True)

    assert build_history(history, state) == build_history(history, state)


# --- Events --------------------------------------------------------------


def test_a_review_that_still_applies_produces_no_observation() -> None:
    """An event saying "still fine" would be noise in a record that has
    to stay readable."""

    assert (
        event_for_applicability(
            _review().target, _review(), ReviewApplicability.APPLIES
        )
        is None
    )


def test_an_orphaned_review_became_historical() -> None:
    event = event_for_applicability(
        _review().target, _review(), ReviewApplicability.ORPHANED
    )

    assert isinstance(event, ReviewBecameHistorical)
    assert event.event_type is ReviewEventType.BECAME_HISTORICAL


def test_a_moved_on_pipeline_requires_revalidation() -> None:
    event = event_for_applicability(
        _review().target,
        _review(),
        ReviewApplicability.REQUIRES_REVALIDATION,
    )

    assert isinstance(event, ReviewRequiresRevalidation)
    assert event.reviewed_rule_identity == (
        "rated_power_from_associated_power_quantity@1.0"
    )


def test_the_event_catalogue_is_closed() -> None:
    assert {item.value for item in ReviewEventType} == {
        "review_recorded",
        "review_superseded",
        "review_became_historical",
        "review_requires_revalidation",
    }
