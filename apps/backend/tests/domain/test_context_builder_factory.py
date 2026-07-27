from __future__ import annotations

import pytest

from app.domain.context_builder.context_builder_exceptions import (
    BlankMetadataEntryKeyError,
    InvalidBudgetPolicyValueError,
    InvalidProjectIdError,
)
from app.domain.context_builder.context_builder_factory import (
    ContextBuildRequestFactory,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidateCollection,
)

EMPTY_COLLECTION = KnowledgeCandidateCollection(
    candidates=(), total_before_limit=0, returned_count=0, applied_limit=20
)


def _create(**overrides):
    defaults = dict(project_id=1, candidates=EMPTY_COLLECTION)
    defaults.update(overrides)
    return ContextBuildRequestFactory.create(**defaults)


def test_project_id_must_be_positive():
    with pytest.raises(InvalidProjectIdError):
        _create(project_id=0)


def test_default_budget_policy_is_applied_when_not_overridden():
    request = _create()
    assert request.configuration.budget_policy.max_candidates == 100
    assert request.configuration.budget_policy.max_entities == 50


def test_budget_policy_overrides_are_applied():
    request = _create(max_candidates=10, max_entities=3, max_warnings=0)
    assert request.configuration.budget_policy.max_candidates == 10
    assert request.configuration.budget_policy.max_entities == 3
    assert request.configuration.budget_policy.max_warnings == 0


def test_max_candidates_below_minimum_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_candidates=0)


def test_max_candidates_above_maximum_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_candidates=1001)


def test_negative_per_kind_limit_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_entities=-1)


def test_empty_candidate_collection_is_not_an_error():
    request = _create(candidates=EMPTY_COLLECTION)
    assert request.candidates.candidates == ()


def test_metadata_entries_are_carried_onto_the_request():
    request = _create(
        metadata_entries=(("mode", "entity_lookup"), ("scoring_policy", "1.0"))
    )
    assert len(request.metadata_entries) == 2
    assert request.metadata_entries[0].key == "mode"
    assert request.metadata_entries[0].value == "entity_lookup"


def test_blank_metadata_entry_key_is_rejected():
    with pytest.raises(BlankMetadataEntryKeyError):
        _create(metadata_entries=(("   ", "value"),))


def test_retrieval_policy_version_defaults_to_none_and_can_be_supplied():
    assert _create().retrieval_policy_version is None
    assert _create(retrieval_policy_version="1.0").retrieval_policy_version == "1.0"


def test_configuration_carries_versioned_policies():
    request = _create()
    assert request.configuration.budget_policy.version == "1.0"
    assert request.configuration.selection_policy.version == "1.0"
    assert request.configuration.context_builder_version == "1.0"
