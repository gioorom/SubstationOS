from __future__ import annotations

from app.domain.structured_retrieval.retrieval_query_planner import (
    RetrievalQueryPlanner,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalCriterionKind,
    RetrievalMode,
    RetrievalQueryOperation,
)


def _request(**overrides):
    defaults = dict(
        project_id=1,
        mode=RetrievalMode.ENTITY_LOOKUP,
        limit=20,
        include_neighborhood=False,
        neighborhood_depth=0,
        canonical_entity_id="CABLE:C-295",
    )
    defaults.update(overrides)
    return StructuredRetrievalRequestFactory.create(**defaults)


def test_entity_lookup_requires_only_entity_by_id():
    plan = RetrievalQueryPlanner.plan(_request())
    assert plan.required_operations == (RetrievalQueryOperation.ENTITY_BY_ID,)
    assert plan.optional_operations == ()


def test_entity_type_search_requires_entities_by_type():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.ENTITY_TYPE_SEARCH,
            canonical_entity_id=None,
            entity_type="CABLE",
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ENTITIES_BY_TYPE,
    )


def test_relationship_search_requires_all_relationships():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.RELATIONSHIP_SEARCH,
            canonical_entity_id=None,
            relationship_type="FEEDS",
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ALL_RELATIONSHIPS,
    )


def test_attribute_name_alone_requires_entities_by_attribute():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.ATTRIBUTE_SEARCH,
            canonical_entity_id=None,
            attribute_name="rated_voltage",
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ENTITIES_BY_ATTRIBUTE,
    )


def test_attribute_name_and_value_together_do_not_duplicate_operations():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.ATTRIBUTE_SEARCH,
            canonical_entity_id=None,
            attribute_name="rated_voltage",
            attribute_value="132kV",
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ENTITIES_BY_ATTRIBUTE,
    )


def test_attribute_value_alone_requires_a_full_entity_scan():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.ATTRIBUTE_SEARCH,
            canonical_entity_id=None,
            attribute_value="132kV",
        )
    )
    assert plan.required_operations == (RetrievalQueryOperation.ALL_ENTITIES,)


def test_lexical_search_requires_both_full_scans():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.LEXICAL_SEARCH,
            canonical_entity_id=None,
            lexical_terms=("cable",),
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ALL_ENTITIES,
        RetrievalQueryOperation.ALL_RELATIONSHIPS,
    )


def test_combined_mode_unions_operations_without_duplicates():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.COMBINED,
            canonical_entity_id=None,
            entity_type="CABLE",
            relationship_type="FEEDS",
            lexical_terms=("cable",),
        )
    )
    assert plan.required_operations == (
        RetrievalQueryOperation.ENTITIES_BY_TYPE,
        RetrievalQueryOperation.ALL_RELATIONSHIPS,
        RetrievalQueryOperation.ALL_ENTITIES,
    )


def test_neighborhood_expansion_is_optional_not_required():
    plan = RetrievalQueryPlanner.plan(
        _request(include_neighborhood=True, neighborhood_depth=1)
    )
    assert plan.optional_operations == (RetrievalQueryOperation.NEIGHBORHOOD,)
    assert RetrievalQueryOperation.NEIGHBORHOOD not in plan.required_operations
    assert plan.expand_neighborhood is True
    assert plan.neighborhood_depth == 1


def test_criterion_order_follows_the_fixed_canonical_order_not_input_order():
    plan = RetrievalQueryPlanner.plan(
        _request(
            mode=RetrievalMode.COMBINED,
            canonical_entity_id=None,
            attribute_name="rated_voltage",
            entity_type="CABLE",
        )
    )
    assert plan.criterion_order == (
        RetrievalCriterionKind.ENTITY_TYPE,
        RetrievalCriterionKind.ATTRIBUTE_NAME,
    )


def test_max_candidates_echoes_the_request_limit():
    plan = RetrievalQueryPlanner.plan(_request(limit=42))
    assert plan.max_candidates == 42


def test_plan_is_pure_and_repeatable():
    request = _request()
    first = RetrievalQueryPlanner.plan(request)
    second = RetrievalQueryPlanner.plan(request)
    assert first == second
