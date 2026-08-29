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
from tests._governed_context import designation_result

#: A governed query that matched nothing. An honest engineering answer -
#: the graph holds nothing approved about ``TR1`` - never an error.
NO_MATCH = (designation_result("TR1", ()),)


def _create(**overrides):
    defaults = dict(project_id=1, results=NO_MATCH)
    defaults.update(overrides)
    return ContextBuildRequestFactory.create(**defaults)


def test_project_id_must_be_positive():
    with pytest.raises(InvalidProjectIdError):
        _create(project_id=0)


def test_default_budget_policy_is_applied_when_not_overridden():
    request = _create()
    assert request.configuration.budget_policy.max_items == 100
    assert request.configuration.budget_policy.max_assets == 50


def test_budget_policy_overrides_are_applied():
    request = _create(max_items=10, max_assets=3, max_warnings=0)
    assert request.configuration.budget_policy.max_items == 10
    assert request.configuration.budget_policy.max_assets == 3
    assert request.configuration.budget_policy.max_warnings == 0


def test_max_items_below_minimum_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_items=0)


def test_max_items_above_maximum_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_items=1001)


def test_negative_per_kind_limit_is_rejected():
    with pytest.raises(InvalidBudgetPolicyValueError):
        _create(max_assets=-1)


def test_a_governed_query_that_matched_nothing_is_not_an_error():
    request = _create(results=NO_MATCH)
    assert request.results[0].items == ()


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


def test_the_assembly_configuration_is_versioned():
    """Assembly behaviour is versioned, and the version describes
    behaviour rather than a deployment."""

    configuration = _create().configuration

    assert configuration.context_assembly_version == "2.0"
    assert configuration.selection_policy.version == "2.0"
    assert configuration.budget_policy.version == "2.0"


def test_the_factory_accepts_governed_results_and_nothing_else():
    """There is no constructor that takes anything but governed
    retrieval results, which is what makes "Context Assembly reads only
    governed knowledge" a property of the type."""

    import inspect

    signature = inspect.signature(ContextBuildRequestFactory.create)

    assert "results" in signature.parameters
    assert "candidates" not in signature.parameters
