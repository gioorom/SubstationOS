from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.engineering_intent.engineering_intent_exceptions import (
    InvalidProjectIdError,
    InvalidRequestTextError,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentConfidence,
    EngineeringIntentType,
)
from app.services import engineering_intent_service

NOW = datetime(2026, 1, 1, 15, 0, 0)


def _classify(request_text: str, **overrides):
    defaults = dict(
        project_id=1,
        engineering_session_id="svc-sess-1",
        conversation_id="svc-conv-1",
        turn_id="svc-turn-1",
        request_text=request_text,
        classified_at=NOW,
    )
    defaults.update(overrides)
    return engineering_intent_service.classify(**defaults)


def test_classify_returns_a_valid_classification() -> None:
    result = _classify("Confronta le revisioni 01 e 02")

    assert result.project_id == 1
    assert result.intent.intent_type is (
        EngineeringIntentType.ENGINEERING_COMPARISON
    )
    assert result.intent.confidence is EngineeringIntentConfidence.HIGH
    assert result.validation.valid is True


def test_classify_passes_structural_working_memory_signals_through() -> None:
    result = _classify(
        "Verifica lo schema",
        working_memory_has_open_question=True,
        working_memory_active_response_count=3,
    )

    # These signals are accepted and carried without changing the
    # deterministic textual classification - they exist for future
    # structural use, never hidden semantic inference.
    assert result.intent.intent_type is (
        EngineeringIntentType.VERIFICATION_REQUEST
    )
    assert result.validation.valid is True


def test_classify_rejects_a_non_positive_project_id() -> None:
    with pytest.raises(InvalidProjectIdError):
        _classify("Confronta", project_id=0)


def test_classify_rejects_unclassifiable_request_text() -> None:
    with pytest.raises(InvalidRequestTextError):
        _classify("   ")


def test_classify_is_deterministic() -> None:
    first = _classify("Apri la pagina con lo schema")
    second = _classify("Apri la pagina con lo schema")

    assert first.intent == second.intent
