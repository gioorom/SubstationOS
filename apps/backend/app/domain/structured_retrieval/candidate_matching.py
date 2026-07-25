"""
Candidate Construction (Milestone 13's pipeline stage of the same
name). Pure functions that turn already-fetched Graph Query views
(``GraphNodeView``/``GraphRelationshipView``) plus one matched
criterion into raw, single-component ``KnowledgeCandidate`` objects.
Never fetches data itself (the service layer owns every Graph Query
call); never merges duplicates across criteria (``candidate_aggregation.py``
owns that). One raw candidate here always carries exactly one score
component, one reason, and one match - the smallest unit of evidence.
"""

from __future__ import annotations

from app.domain.graph_query.graph_query_models import (
    GraphNodeView,
    GraphRelationshipView,
)
from app.domain.structured_retrieval import lexical_matching, scoring_policy
from app.domain.structured_retrieval.candidate_identity import (
    attribute_candidate_id,
    entity_candidate_id,
    relationship_candidate_id,
    relationship_natural_key,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateAttribute,
    KnowledgeCandidateKind,
    KnowledgeCandidateReference,
    KnowledgeCandidateRelationship,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    LexicalMatchMode,
    RetrievalCriterion,
    RetrievalCriterionKind,
    RetrievalMatch,
    RetrievalReason,
    ScoreComponentCategory,
)


def _node_reference(node: GraphNodeView) -> KnowledgeCandidateReference:
    return KnowledgeCandidateReference(
        graph_entity_id=node.graph_entity_id,
        entity_type=node.entity_type,
        canonical_id=node.canonical_id,
    )


def _single_component_score(
    component: KnowledgeCandidateScoreComponent,
) -> KnowledgeCandidateScore:
    return KnowledgeCandidateScore(
        total=component.weight, components=(component,)
    )


def _node_execution_ids(node: GraphNodeView) -> tuple[int, ...]:
    """
    Honest, best-effort provenance (Milestone 13's "use provenance
    already available in the governed graph state... do not invent
    provenance"): a node's ``created_by_execution_id`` is the
    ``GraphExecution`` that first wrote it, when that column was
    populated. Older or fake-repository-backed rows may leave it
    ``None`` - represented here as simply absent, never guessed.
    """

    return (
        (node.created_by_execution_id,)
        if node.created_by_execution_id is not None
        else ()
    )


def _relationship_execution_ids(
    relationship: GraphRelationshipView,
) -> tuple[int, ...]:
    return (
        (relationship.created_by_execution_id,)
        if relationship.created_by_execution_id is not None
        else ()
    )


def _entity_candidate(
    project_id: int,
    node: GraphNodeView,
    criterion: RetrievalCriterion,
    component: KnowledgeCandidateScoreComponent,
    description: str,
) -> KnowledgeCandidate:
    reference = _node_reference(node)

    return KnowledgeCandidate(
        candidate_id=entity_candidate_id(project_id, node.graph_entity_id),
        project_id=project_id,
        candidate_kind=KnowledgeCandidateKind.ENTITY,
        primary_reference=reference,
        matched_attributes=(),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(node.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=_node_execution_ids(node),
        score=_single_component_score(component),
        reasons=(
            RetrievalReason(
                category=component.category,
                criterion_kind=criterion.kind,
                description=description,
            ),
        ),
        matches=(
            RetrievalMatch(
                criterion_kind=criterion.kind,
                criterion_value=criterion.value,
            ),
        ),
        sort_key=(-component.weight, 0, node.canonical_id, ""),
    )


def _attribute_candidate(
    project_id: int,
    node: GraphNodeView,
    attribute_name: str,
    attribute_value: str,
    criterion: RetrievalCriterion,
    component: KnowledgeCandidateScoreComponent,
    description: str,
) -> KnowledgeCandidate:
    reference = _node_reference(node)

    return KnowledgeCandidate(
        candidate_id=attribute_candidate_id(
            project_id, node.graph_entity_id, attribute_name
        ),
        project_id=project_id,
        candidate_kind=KnowledgeCandidateKind.ATTRIBUTE,
        primary_reference=reference,
        matched_attributes=(
            KnowledgeCandidateAttribute(
                name=attribute_name, value=attribute_value
            ),
        ),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(node.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=_node_execution_ids(node),
        score=_single_component_score(component),
        reasons=(
            RetrievalReason(
                category=component.category,
                criterion_kind=criterion.kind,
                description=description,
            ),
        ),
        matches=(
            RetrievalMatch(
                criterion_kind=criterion.kind,
                criterion_value=criterion.value,
            ),
        ),
        sort_key=(-component.weight, 2, node.canonical_id, ""),
    )


def _relationship_candidate(
    project_id: int,
    relationship: GraphRelationshipView,
    criterion: RetrievalCriterion,
    component: KnowledgeCandidateScoreComponent,
    description: str,
) -> KnowledgeCandidate:
    subject = KnowledgeCandidateReference(
        graph_entity_id=relationship.source_entity_id,
        entity_type=relationship.source_entity_id.entity_type,
        canonical_id=relationship.source_entity_id.canonical_id,
    )
    obj = KnowledgeCandidateReference(
        graph_entity_id=relationship.target_entity_id,
        entity_type=relationship.target_entity_id.entity_type,
        canonical_id=relationship.target_entity_id.canonical_id,
    )
    natural_key = relationship_natural_key(
        relationship.source_entity_id,
        relationship.relationship_type,
        relationship.target_entity_id,
    )

    return KnowledgeCandidate(
        candidate_id=relationship_candidate_id(
            project_id,
            relationship.source_entity_id,
            relationship.relationship_type,
            relationship.target_entity_id,
        ),
        project_id=project_id,
        candidate_kind=KnowledgeCandidateKind.RELATIONSHIP,
        primary_reference=subject,
        matched_attributes=(),
        matched_relationships=(
            KnowledgeCandidateRelationship(
                subject=subject,
                relationship_type=relationship.relationship_type,
                object=obj,
            ),
        ),
        related_entities=(obj,),
        source_fact_ids=(),
        graph_node_ids=(
            relationship.source_entity_id.value,
            relationship.target_entity_id.value,
        ),
        graph_relationship_ids=(natural_key,),
        graph_execution_ids=_relationship_execution_ids(relationship),
        score=_single_component_score(component),
        reasons=(
            RetrievalReason(
                category=component.category,
                criterion_kind=criterion.kind,
                description=description,
            ),
        ),
        matches=(
            RetrievalMatch(
                criterion_kind=criterion.kind,
                criterion_value=criterion.value,
            ),
        ),
        sort_key=(-component.weight, 1, natural_key, ""),
    )


def match_entity_by_id(
    project_id: int,
    criterion: RetrievalCriterion,
    node: GraphNodeView | None,
) -> list[KnowledgeCandidate]:
    if node is None:
        return []

    component = KnowledgeCandidateScoreComponent(
        category=ScoreComponentCategory.EXACT_CANONICAL_ID_MATCH,
        weight=scoring_policy.WEIGHT_EXACT_CANONICAL_ID_MATCH,
        detail=node.graph_entity_id.value,
    )

    return [
        _entity_candidate(
            project_id,
            node,
            criterion,
            component,
            f"Exact canonical entity id match for '{criterion.value}'.",
        )
    ]


def match_entities_by_type(
    project_id: int,
    criterion: RetrievalCriterion,
    nodes: list[GraphNodeView],
) -> list[KnowledgeCandidate]:
    candidates: list[KnowledgeCandidate] = []

    for node in nodes:
        component = KnowledgeCandidateScoreComponent(
            category=ScoreComponentCategory.ENTITY_TYPE_MATCH,
            weight=scoring_policy.WEIGHT_ENTITY_TYPE_MATCH,
            detail=node.entity_type,
        )
        candidates.append(
            _entity_candidate(
                project_id,
                node,
                criterion,
                component,
                f"Entity type matches '{criterion.value}'.",
            )
        )

    return candidates


def match_entities_by_attribute(
    project_id: int,
    name_criterion: RetrievalCriterion | None,
    value_criterion: RetrievalCriterion | None,
    nodes: list[GraphNodeView],
) -> list[KnowledgeCandidate]:
    """
    Handles three shapes: name only (attribute presence), name + value
    (presence and, within that named attribute, an exact value match -
    two separate candidates so each is scored on its own merit), or
    value only (a scan across every attribute on every supplied node
    for an exact value match, regardless of attribute name).
    """

    candidates: list[KnowledgeCandidate] = []

    for node in nodes:
        if name_criterion is not None:
            if name_criterion.value not in node.properties:
                continue

            attribute_value = node.properties[name_criterion.value]

            name_component = KnowledgeCandidateScoreComponent(
                category=ScoreComponentCategory.ATTRIBUTE_NAME_MATCH,
                weight=scoring_policy.WEIGHT_ATTRIBUTE_NAME_MATCH,
                detail=name_criterion.value,
            )
            candidates.append(
                _attribute_candidate(
                    project_id,
                    node,
                    name_criterion.value,
                    attribute_value,
                    name_criterion,
                    name_component,
                    f"Attribute '{name_criterion.value}' is present.",
                )
            )

            if (
                value_criterion is not None
                and attribute_value == value_criterion.value
            ):
                value_component = KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.ATTRIBUTE_VALUE_MATCH,
                    weight=scoring_policy.WEIGHT_ATTRIBUTE_VALUE_MATCH,
                    detail=value_criterion.value,
                )
                candidates.append(
                    _attribute_candidate(
                        project_id,
                        node,
                        name_criterion.value,
                        attribute_value,
                        value_criterion,
                        value_component,
                        "Attribute value matches "
                        f"'{value_criterion.value}'.",
                    )
                )
        elif value_criterion is not None:
            for attribute_name, attribute_value in node.properties.items():
                if attribute_value != value_criterion.value:
                    continue

                component = KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.ATTRIBUTE_VALUE_MATCH,
                    weight=scoring_policy.WEIGHT_ATTRIBUTE_VALUE_MATCH,
                    detail=value_criterion.value,
                )
                candidates.append(
                    _attribute_candidate(
                        project_id,
                        node,
                        attribute_name,
                        attribute_value,
                        value_criterion,
                        component,
                        "Attribute value matches "
                        f"'{value_criterion.value}'.",
                    )
                )

    return candidates


def match_relationships_by_type(
    project_id: int,
    criterion: RetrievalCriterion,
    relationships: list[GraphRelationshipView],
) -> list[KnowledgeCandidate]:
    candidates: list[KnowledgeCandidate] = []

    for relationship in relationships:
        if relationship.relationship_type.value != criterion.value:
            continue

        component = KnowledgeCandidateScoreComponent(
            category=ScoreComponentCategory.RELATIONSHIP_TYPE_MATCH,
            weight=scoring_policy.WEIGHT_RELATIONSHIP_TYPE_MATCH,
            detail=relationship.relationship_type.value,
        )
        candidates.append(
            _relationship_candidate(
                project_id,
                relationship,
                criterion,
                component,
                f"Relationship type matches '{criterion.value}'.",
            )
        )

    return candidates


def _find_lexical_node_match(
    term: str, node: GraphNodeView
) -> tuple[str, str] | None:
    normalized_term = lexical_matching.normalize_token(term)

    if (
        normalized_term == lexical_matching.normalize_token(
            node.canonical_id
        )
        or lexical_matching.normalize_identifier(term)
        == lexical_matching.normalize_identifier(node.canonical_id)
        or lexical_matching.matches_prefix(term, node.canonical_id)
    ):
        return ("canonical identifier", node.canonical_id)

    if normalized_term == lexical_matching.normalize_token(
        node.entity_type
    ):
        return ("entity type", node.entity_type)

    for key, value in node.properties.items():
        if normalized_term == lexical_matching.normalize_token(key):
            return (f"attribute key '{key}'", key)
        if normalized_term == lexical_matching.normalize_token(value):
            return (f"attribute value of '{key}'", value)

    return None


def _find_lexical_relationship_match(
    term: str, relationship: GraphRelationshipView
) -> tuple[str, str] | None:
    relationship_type = relationship.relationship_type.value
    normalized_term = lexical_matching.normalize_token(term)

    if (
        normalized_term
        == lexical_matching.normalize_token(relationship_type)
        or lexical_matching.matches_prefix(term, relationship_type)
    ):
        return ("relationship type", relationship_type)

    return None


def match_lexical(
    project_id: int,
    criteria: list[RetrievalCriterion],
    match_mode: LexicalMatchMode,
    nodes: list[GraphNodeView],
    relationships: list[GraphRelationshipView],
) -> list[KnowledgeCandidate]:
    """
    Matches every supplied lexical term against canonical identifier,
    entity type, and attribute key/value fields on nodes, and
    relationship type on relationships. In ``ALL`` mode, a candidate
    must match every term somewhere in its own fields; in ``ANY`` mode,
    matching a single term is enough - evaluated independently per
    candidate (a node's terms are matched against only that node's own
    fields, never mixed with another node's).
    """

    candidates: list[KnowledgeCandidate] = []
    terms = [criterion.value for criterion in criteria]

    for node in nodes:
        matched: dict[str, tuple[str, str]] = {}
        for term in terms:
            field = _find_lexical_node_match(term, node)
            if field is not None:
                matched[term] = field

        if not matched:
            continue
        if match_mode is LexicalMatchMode.ALL and len(matched) < len(terms):
            continue

        for term, (field_name, matched_value) in matched.items():
            component = KnowledgeCandidateScoreComponent(
                category=ScoreComponentCategory.LEXICAL_TOKEN_MATCH,
                weight=scoring_policy.WEIGHT_LEXICAL_TOKEN_MATCH,
                detail=term,
            )
            criterion = RetrievalCriterion(
                kind=RetrievalCriterionKind.LEXICAL_TERM, value=term
            )
            candidates.append(
                _entity_candidate(
                    project_id,
                    node,
                    criterion,
                    component,
                    f"Lexical term '{term}' matched {field_name} "
                    f"('{matched_value}').",
                )
            )

    for relationship in relationships:
        matched = {}
        for term in terms:
            field = _find_lexical_relationship_match(term, relationship)
            if field is not None:
                matched[term] = field

        if not matched:
            continue
        if match_mode is LexicalMatchMode.ALL and len(matched) < len(terms):
            continue

        for term, (field_name, matched_value) in matched.items():
            component = KnowledgeCandidateScoreComponent(
                category=ScoreComponentCategory.LEXICAL_TOKEN_MATCH,
                weight=scoring_policy.WEIGHT_LEXICAL_TOKEN_MATCH,
                detail=term,
            )
            criterion = RetrievalCriterion(
                kind=RetrievalCriterionKind.LEXICAL_TERM, value=term
            )
            candidates.append(
                _relationship_candidate(
                    project_id,
                    relationship,
                    criterion,
                    component,
                    f"Lexical term '{term}' matched {field_name} "
                    f"('{matched_value}').",
                )
            )

    return candidates
