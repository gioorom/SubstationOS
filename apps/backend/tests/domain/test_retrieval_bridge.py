"""
Domain tests for the Classification-to-Retrieval Bridge (Milestone
23B.3).

Every test starts from a **real classified request** - the actual
classifier, not a hand-built intent - so what is proved here is the
genuine end-to-end mapping an engineer's sentence undergoes, not a
mapping of fixtures invented to suit the bridge.

Pure and fast: no I/O, no database, no provider, no LLM.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.engineering_intent.engineering_intent_classifier import (
    classify_engineering_request,
)
from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentClassificationInput,
    EngineeringIntentType,
)
from app.domain.retrieval_bridge.retrieval_bridge import (
    derive_retrieval_configuration,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RetrievalBridgeFailureCode,
)
from app.domain.retrieval_bridge.retrieval_bridge_policy import (
    RETRIEVAL_POLICY_BY_INTENT,
    SUPPORTED_INTENT_TYPES,
)
from app.domain.retrieval_bridge.retrieval_mode import RetrievalMode

NOW = datetime(2026, 1, 1, 5, 0, 0)
PROJECT_ID = 1


def _classify(text: str, *, project_id: int = PROJECT_ID):
    return classify_engineering_request(
        EngineeringIntentClassificationInput(
            project_id=project_id,
            engineering_session_id="sess-1",
            conversation_id="conv-1",
            turn_id="turn-1",
            request_text=text,
            classified_at=NOW,
        )
    ).intent


def _bridge(text: str, **overrides):
    return derive_retrieval_configuration(
        _classify(text, **overrides), derived_at=NOW
    )


# --- The three supported intents ------------------------------------------


def test_a_knowledge_query_naming_a_canonical_entity_maps_to_entity_lookup() -> (
    None
):
    result = _bridge("Quale TA è installato sul cavo C-295?")

    assert result.resolved is True
    configuration = result.configuration
    assert configuration.mode is RetrievalMode.ENTITY_LOOKUP
    assert configuration.canonical_entity_id == "CABLE:C-295"
    assert configuration.lexical_terms == ()
    assert configuration.include_neighborhood is False
    # The resolved entity type is reported on the designation, never as a
    # retrieval criterion - ENTITY_LOOKUP admits the canonical id only.
    assert configuration.entity_type is None
    assert result.designations[0].entity_type == "CABLE"


def test_a_knowledge_query_without_a_canonical_entity_maps_to_lexical() -> None:
    result = _bridge("Quale TA è installato sul montante T2?")

    assert result.resolved is True
    configuration = result.configuration
    assert configuration.mode is RetrievalMode.LEXICAL_SEARCH
    assert configuration.canonical_entity_id is None
    assert configuration.lexical_terms == ("T2",)


def test_a_document_lookup_maps_designations_to_lexical_terms() -> None:
    """The Engineering Index searches by identifier as written."""

    result = _bridge("Trova il documento del montante T2")

    assert result.resolved is True
    assert result.metadata.intent_type is EngineeringIntentType.DOCUMENT_LOOKUP
    assert result.configuration.mode is RetrievalMode.LEXICAL_SEARCH
    assert result.configuration.lexical_terms == ("T2",)


def test_a_document_lookup_never_produces_a_canonical_reference() -> None:
    """Even when a designation *is* canonicalizable: no document mentions
    the string "CABLE:C-295", so handing one to the index would search for
    something that cannot be there."""

    result = _bridge("Trova il documento del cavo C-295")

    assert result.resolved is True
    assert result.configuration.canonical_entity_id is None
    assert result.configuration.entity_type is None
    assert result.configuration.lexical_terms == ("C-295",)


def test_an_explanation_maps_to_lexical_with_neighborhood_expansion() -> None:
    """The one place the bridge widens scope, and only by fixed policy:
    an explanation asks how things relate."""

    result = _bridge("Spiegami il funzionamento della protezione 87T")

    assert result.resolved is True
    configuration = result.configuration
    assert configuration.mode is RetrievalMode.LEXICAL_SEARCH
    assert configuration.lexical_terms == ("87T",)
    assert configuration.include_neighborhood is True
    assert configuration.neighborhood_depth == 1


def test_an_explanation_naming_a_canonical_entity_uses_entity_lookup() -> None:
    result = _bridge("Spiegami il funzionamento del cavo C-295")

    assert result.resolved is True
    assert result.configuration.mode is RetrievalMode.ENTITY_LOOKUP
    assert result.configuration.canonical_entity_id == "CABLE:C-295"
    assert result.configuration.include_neighborhood is True


# --- Designation extraction and resolution ---------------------------------


def test_a_canonicalizable_designation_is_reported_as_a_canonical_reference() -> (
    None
):
    result = _bridge("Quale TA è installato sul cavo C-295?")

    designation = result.designations[0]
    assert designation.text == "C-295"
    assert designation.resolution is DesignationResolution.CANONICAL_REFERENCE
    assert designation.entity_type == "CABLE"
    assert designation.canonical_id == "C-295"


def test_an_unrecognized_designation_becomes_a_lexical_term_never_a_guess() -> (
    None
):
    """"87T" is a real designation this system's canonical vocabulary does
    not cover. It is carried forward verbatim - never invented into a
    canonical identifier."""

    result = _bridge("Spiegami il funzionamento della protezione 87T")

    designation = result.designations[0]
    assert designation.text == "87T"
    assert designation.resolution is DesignationResolution.LEXICAL_TERM
    assert designation.canonical_id is None
    assert designation.canonical_reference is None


def test_trailing_punctuation_is_stripped_from_a_designation() -> None:
    result = _bridge("Quale TA è installato sul montante T2?")

    assert result.designations[0].text == "T2"


def test_designations_are_preserved_exactly_as_written() -> None:
    """A designation is a field identifier; consumers that need it folded
    fold it themselves."""

    result = _bridge("Trova il documento del montante T2")

    assert result.configuration.lexical_terms == ("T2",)


def test_a_repeated_designation_is_carried_once() -> None:
    result = _bridge("Trova il documento del montante T2 e del quadro t2")

    assert result.configuration.lexical_terms == ("T2",)


def test_bare_words_are_not_treated_as_designations() -> None:
    """"trasformatore" is a type name, not an instance. Searching for it
    would broaden retrieval to every transformer in the project."""

    result = _bridge("Spiegami il funzionamento del trasformatore")

    assert result.resolved is False
    assert result.designations == ()


def test_bare_numbers_are_not_treated_as_designations() -> None:
    """Nothing distinguishes an equipment number from a voltage or a
    page."""

    result = _bridge("Spiegami il funzionamento dei 400 kV")

    assert result.resolved is False


def test_several_designations_all_become_lexical_terms() -> None:
    result = _bridge(
        "Spiegami il funzionamento della protezione 87T sul montante T2"
    )

    assert result.configuration.lexical_terms == ("87T", "T2")
    assert result.statistics.designation_count == 2
    assert result.statistics.lexical_term_count == 2
    assert result.statistics.canonical_reference_count == 0


# --- Failure taxonomy -------------------------------------------------------


def test_no_designation_yields_insufficient_evidence_not_a_broader_search() -> (
    None
):
    """The central rule: retrieval is never silently broadened."""

    result = _bridge("Spiegami il funzionamento del trasformatore")

    assert result.resolved is False
    assert result.configuration is None
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INSUFFICIENT_EVIDENCE
    )


def test_two_distinct_canonical_entities_yield_conflicting_evidence() -> None:
    """Retrieval resolves one canonical entity; picking either would
    silently answer about one while the engineer named two."""

    result = _bridge("Spiegami il cavo C-295 e il cavo C-300")

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.CONFLICTING_EVIDENCE
    )
    assert "CABLE:C-295" in result.failure.detail
    assert "CABLE:C-300" in result.failure.detail


def test_the_same_canonical_entity_named_twice_is_not_a_conflict() -> None:
    result = _bridge("Spiegami il cavo C-295 e il cavo C295")

    assert result.resolved is True
    assert result.configuration.canonical_entity_id == "CABLE:C-295"


@pytest.mark.parametrize(
    "intent_type",
    [
        intent
        for intent in EngineeringIntentType
        if intent not in RETRIEVAL_POLICY_BY_INTENT
    ],
)
def test_an_unmapped_intent_yields_unsupported_mapping(
    intent_type: EngineeringIntentType,
) -> None:
    """No default policy: an intent absent from the table is refused, not
    given a retrieval shape nobody chose for it."""

    intent = replace(
        _classify("Quale TA è installato sul cavo C-295?"),
        intent_type=intent_type,
    )

    result = derive_retrieval_configuration(intent, derived_at=NOW)

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING
    )


def test_a_comparison_request_is_refused_rather_than_mapped() -> None:
    """Milestone 23B.3's scope is explicit: no Comparison, Navigation,
    Verification or Drawing behaviour is added."""

    result = _bridge("Confronta il cavo C-295 con il cavo C-300")

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.UNSUPPORTED_INTENT_MAPPING
    )


def test_an_intent_with_a_non_positive_project_is_rejected() -> None:
    intent = _classify("Quale TA è installato sul cavo C-295?")
    broken = replace(
        intent, project_id=0, metadata=replace(intent.metadata, project_id=0)
    )

    result = derive_retrieval_configuration(broken, derived_at=NOW)

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INVALID_BRIDGE_INPUT
    )


def test_an_intent_disagreeing_with_its_own_metadata_is_rejected() -> None:
    intent = _classify("Quale TA è installato sul cavo C-295?")
    broken = replace(intent, project_id=2)

    result = derive_retrieval_configuration(broken, derived_at=NOW)

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INVALID_BRIDGE_INPUT
    )


def test_too_many_designations_are_refused_rather_than_silently_dropped() -> (
    None
):
    """Structured Retrieval accepts at most eight lexical terms. Dropping
    the surplus would answer a narrower question than the one asked."""

    designations = " ".join(f"T{index}" for index in range(1, 11))
    result = _bridge(f"Trova il documento di {designations}")

    assert result.resolved is False
    assert result.failure.code is (
        RetrievalBridgeFailureCode.INVALID_RETRIEVAL_CONFIGURATION
    )


def test_a_refusal_still_reports_what_was_found() -> None:
    """A refusal that reported nothing would be indistinguishable from a
    bug."""

    result = _bridge("Spiegami il cavo C-295 e il cavo C-300")

    assert result.resolved is False
    assert len(result.designations) == 2
    assert result.statistics.canonical_reference_count == 2


# --- Determinism ------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Quale TA è installato sul cavo C-295?",
        "Trova il documento del montante T2",
        "Spiegami il funzionamento della protezione 87T",
        "Spiegami il funzionamento del trasformatore",
    ],
)
def test_the_same_request_always_produces_the_same_result(text: str) -> None:
    assert _bridge(text) == _bridge(text)


def test_designation_order_follows_the_request_not_the_alphabet() -> None:
    first = _bridge("Trova il documento di T9 e T1")
    second = _bridge("Trova il documento di T1 e T9")

    assert first.configuration.lexical_terms == ("T9", "T1")
    assert second.configuration.lexical_terms == ("T1", "T9")


# --- Provenance and policy --------------------------------------------------


def test_the_result_records_which_policy_produced_it() -> None:
    result = _bridge("Trova il documento del montante T2")

    assert result.metadata.retrieval_bridge_version
    assert result.metadata.bridge_policy_version
    assert result.metadata.engineering_intent_id
    assert result.metadata.derived_at == NOW


def test_the_policy_table_covers_exactly_the_intents_with_workflows() -> None:
    assert set(SUPPORTED_INTENT_TYPES) == {
        EngineeringIntentType.KNOWLEDGE_QUERY,
        EngineeringIntentType.DOCUMENT_LOOKUP,
        EngineeringIntentType.ENGINEERING_EXPLANATION,
        EngineeringIntentType.VERIFICATION_REQUEST,
    }


def test_no_policy_widens_scope_beyond_a_single_neighborhood_hop() -> None:
    for policy in RETRIEVAL_POLICY_BY_INTENT.values():
        assert policy.neighborhood_depth in (0, 1)
        assert policy.result_limit > 0
