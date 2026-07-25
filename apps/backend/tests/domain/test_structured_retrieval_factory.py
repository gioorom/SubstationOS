from __future__ import annotations

import pytest

from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    BlankLexicalTermError,
    ExcessiveLexicalTermCountError,
    InvalidCanonicalEntityReferenceError,
    InvalidNeighborhoodDepthError,
    InvalidProjectIdError,
    InvalidRetrievalLimitError,
    LexicalTermTooLongError,
    MissingRetrievalCriterionError,
    UnsupportedCriterionCombinationError,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
    parse_canonical_entity_reference,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalCriterionKind,
    RetrievalMode,
)


def _create(**overrides):
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


def test_project_id_must_be_positive():
    with pytest.raises(InvalidProjectIdError):
        _create(project_id=0)


def test_limit_below_minimum_is_rejected():
    with pytest.raises(InvalidRetrievalLimitError):
        _create(limit=0)


def test_limit_above_maximum_is_rejected():
    with pytest.raises(InvalidRetrievalLimitError):
        _create(limit=201)


def test_limit_at_the_boundaries_is_accepted():
    assert _create(limit=1).limit == 1
    assert _create(limit=200).limit == 200


def test_neighborhood_depth_must_be_zero_when_not_included():
    with pytest.raises(InvalidNeighborhoodDepthError):
        _create(include_neighborhood=False, neighborhood_depth=1)


def test_neighborhood_depth_must_be_one_when_included():
    with pytest.raises(InvalidNeighborhoodDepthError):
        _create(include_neighborhood=True, neighborhood_depth=0)

    with pytest.raises(InvalidNeighborhoodDepthError):
        _create(include_neighborhood=True, neighborhood_depth=2)

    request = _create(include_neighborhood=True, neighborhood_depth=1)
    assert request.include_neighborhood is True


def test_at_least_one_criterion_is_required():
    with pytest.raises(MissingRetrievalCriterionError):
        _create(mode=RetrievalMode.COMBINED, canonical_entity_id=None)


def test_blank_lexical_term_is_rejected():
    with pytest.raises(BlankLexicalTermError):
        _create(
            mode=RetrievalMode.LEXICAL_SEARCH,
            canonical_entity_id=None,
            lexical_terms=("valid", "   "),
        )


def test_excessive_lexical_term_count_is_rejected():
    with pytest.raises(ExcessiveLexicalTermCountError):
        _create(
            mode=RetrievalMode.LEXICAL_SEARCH,
            canonical_entity_id=None,
            lexical_terms=tuple(f"term{i}" for i in range(9)),
        )


def test_lexical_term_too_long_is_rejected():
    with pytest.raises(LexicalTermTooLongError):
        _create(
            mode=RetrievalMode.LEXICAL_SEARCH,
            canonical_entity_id=None,
            lexical_terms=("x" * 65,),
        )


@pytest.mark.parametrize(
    "mode,kwargs",
    [
        (RetrievalMode.ENTITY_LOOKUP, dict(canonical_entity_id=None, entity_type="CABLE")),
        (RetrievalMode.ENTITY_TYPE_SEARCH, dict(canonical_entity_id=None, entity_type=None, relationship_type="FEEDS")),
        (RetrievalMode.RELATIONSHIP_SEARCH, dict(canonical_entity_id=None, relationship_type=None, entity_type="CABLE")),
        (RetrievalMode.ATTRIBUTE_SEARCH, dict(canonical_entity_id=None, attribute_name=None, entity_type="CABLE")),
        (RetrievalMode.LEXICAL_SEARCH, dict(canonical_entity_id=None, lexical_terms=(), entity_type="CABLE")),
    ],
)
def test_single_purpose_modes_reject_a_missing_or_mismatched_criterion(mode, kwargs):
    with pytest.raises(UnsupportedCriterionCombinationError):
        _create(mode=mode, **kwargs)


def test_entity_lookup_rejects_a_foreign_criterion_kind():
    with pytest.raises(UnsupportedCriterionCombinationError):
        _create(
            mode=RetrievalMode.ENTITY_LOOKUP,
            canonical_entity_id="CABLE:C-295",
            entity_type="CABLE",
        )


def test_combined_mode_accepts_any_non_empty_mix():
    request = _create(
        mode=RetrievalMode.COMBINED,
        canonical_entity_id=None,
        entity_type="CABLE",
        attribute_name="rated_voltage",
    )
    kinds = {criterion.kind for criterion in request.criteria}
    assert kinds == {
        RetrievalCriterionKind.ENTITY_TYPE,
        RetrievalCriterionKind.ATTRIBUTE_NAME,
    }


def test_criteria_are_canonically_ordered_regardless_of_input_order():
    request = _create(
        mode=RetrievalMode.COMBINED,
        canonical_entity_id=None,
        attribute_name="rated_voltage",
        entity_type="CABLE",
        relationship_type="FEEDS",
    )
    kinds_in_order = [criterion.kind for criterion in request.criteria]
    assert kinds_in_order == [
        RetrievalCriterionKind.ENTITY_TYPE,
        RetrievalCriterionKind.RELATIONSHIP_TYPE,
        RetrievalCriterionKind.ATTRIBUTE_NAME,
    ]


def test_blank_optional_fields_do_not_produce_criteria():
    request = _create(
        mode=RetrievalMode.ENTITY_LOOKUP,
        canonical_entity_id="CABLE:C-295",
        entity_type="   ",
    )
    assert len(request.criteria) == 1


def test_parse_canonical_entity_reference_splits_type_and_id():
    entity_type, canonical_id = parse_canonical_entity_reference("CABLE:C-295")
    assert entity_type == "CABLE"
    assert canonical_id == "C-295"


@pytest.mark.parametrize("raw", ["", "CABLE", "CABLE:", ":C-295", "novalue"])
def test_parse_canonical_entity_reference_rejects_malformed_input(raw):
    with pytest.raises(InvalidCanonicalEntityReferenceError):
        parse_canonical_entity_reference(raw)
