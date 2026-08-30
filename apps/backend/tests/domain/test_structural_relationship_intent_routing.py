"""
What reaches the shared-structural-location workflow, and what must not
(EPIC 32.2).

The capability is narrow: governed **structural location**, and nothing
else. The routing has to be exactly as narrow, because a request that
reaches this workflow gets a confident deterministic answer - and a
confident answer to a question the engineer did not ask is worse than no
answer at all.

The negative cases below are the point of this file. Each names a
question the platform genuinely cannot answer, and asserts it is not
quietly routed to the one workflow that would answer something adjacent.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_intent.engineering_intent_classifier import (
    classify_engineering_request,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentType,
)

NOW = datetime(2026, 1, 1, 6, 0, 0)


def _intent(text: str) -> EngineeringIntentType:
    return classify_engineering_request(
        EngineeringIntentClassificationInput(
            project_id=1,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text=text,
            classified_at=NOW,
        )
    ).intent.intent_type


# --- Positive routing -----------------------------------------------------


def test_the_english_question_routes_to_the_structural_workflow() -> None:
    for text in (
        "Are +E01-QA1 and +E01-QB1 in the same structural location?",
        "Do TR1 and TR2 share a structural location?",
        "Is QA1 in the same governed location as QB1?",
    ):
        assert _intent(text) is (
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ), text


def test_the_italian_question_routes_to_the_structural_workflow() -> None:
    for text in (
        "TR1 e TR2 sono nella stessa ubicazione strutturale?",
        "QA1 e QB1 hanno la stessa ubicazione?",
    ):
        assert _intent(text) is (
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ), text


# --- Negative routing: questions this capability cannot answer ------------


def test_a_connectivity_question_is_not_routed_here() -> None:
    """
    Connectivity is not containment. Nothing in the governed ontology
    records that two objects are joined, so a connectivity question
    routed here would receive an answer about a different property.
    """

    for text in (
        "Is TR1 connected to QB1?",
        "Are TR1 and TR2 electrically connected?",
        "TR1 e TR2 sono collegati?",
        "Does TR1 feed QB1?",
    ):
        assert _intent(text) is not (
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ), text


def test_a_bay_or_panel_question_is_not_routed_here() -> None:
    """
    `STRUCTURAL_LOCATION` is deliberately unclassified: ``+E01`` is a
    designated place, and whether it is a bay, a panel or a room is a
    classification no governed vocabulary makes. Answering "same bay"
    with "same structural location" would assert the classification.
    """

    for text in (
        "Are TR1 and TR2 in the same bay?",
        "Are QA1 and QB1 in the same panel?",
        "Are TR1 and TR2 in the same room?",
        "TR1 e TR2 sono nello stesso scomparto?",
    ):
        assert _intent(text) is not (
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ), text


def test_a_physical_proximity_question_is_not_routed_here() -> None:
    """
    "Same place" in an engineering conversation usually means physical
    proximity. Sharing a reference designation aspect is not proximity -
    two devices sharing ``+E01`` may be metres apart.
    """

    for text in (
        "Are TR1 and TR2 in the same place?",
        "Are TR1 and TR2 next to each other?",
    ):
        assert _intent(text) is not (
            EngineeringIntentType.STRUCTURAL_RELATIONSHIP_QUERY
        ), text


def test_existing_intents_are_not_captured_by_the_new_routing() -> None:
    """The new phrases must not steal requests the platform already
    answers."""

    assert _intent("Verify the rated power of TR1.") is (
        EngineeringIntentType.VERIFICATION_REQUEST
    )
    assert _intent("Confronta TR1 e TR2.") is (
        EngineeringIntentType.ENGINEERING_COMPARISON
    )
