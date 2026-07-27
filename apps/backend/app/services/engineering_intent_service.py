"""
Application service for Engineering Request Classification (EPIC 5,
Milestone 22). Deliberately thin: it delegates entirely to the pure
domain classifier - **no classification rule, precedence decision,
confidence derivation, or ambiguity rule lives here.** Performs no
persistence and no I/O of any kind.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_intent.engineering_intent_classifier import (
    classify_engineering_request,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentClassificationResult,
)


def classify(
    *,
    project_id: int,
    engineering_session_id: str,
    conversation_id: str,
    turn_id: str,
    request_text: str,
    classified_at: datetime,
    working_memory_has_open_question: bool = False,
    working_memory_active_response_count: int = 0,
) -> EngineeringIntentClassificationResult:
    classification_input = EngineeringIntentClassificationInput(
        project_id=project_id,
        engineering_session_id=engineering_session_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        request_text=request_text,
        classified_at=classified_at,
        working_memory_has_open_question=working_memory_has_open_question,
        working_memory_active_response_count=(
            working_memory_active_response_count
        ),
    )

    return classify_engineering_request(classification_input)
