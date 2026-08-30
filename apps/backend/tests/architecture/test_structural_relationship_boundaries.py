"""
Architecture invariants for the governed structural relationship
(EPIC 32.P1).

The milestone that adds the first relationship between two structural
objects is also the milestone most likely to be *used* as a precedent.
These tests are the guardrails on that precedent: they assert that the
new capability entered through the same door as everything else, and
that adding it opened no shortcut for the next one.

The four claims, in order of how expensive it would be to get them
wrong:

1. **No layer gained the ability to write the graph.** Promotion remains
   the only authoring authority, and evidence, entities, facts,
   semantics and review still cannot reach a graph table.
2. **The vocabulary stayed closed and stayed honest.** Every new member
   traces to a rule that produces it, and no topology or classification
   vocabulary came with it.
3. **No inference was added anywhere upstream of reasoning.** The
   extractor, resolver, constructor and interpreter each read exactly
   one layer, and none of them composes two relationships into a third.
4. **The domain stayed pure.** No new infrastructure import, no cycle.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

GRAPH_DOMAIN = APP_ROOT / "domain" / "governed_knowledge_graph"
GRAPH_TABLES = ("governed_graph_nodes", "governed_graph_edges")

#: Every context that produces or judges the structural relationship
#: before it becomes governed knowledge. None of them may write a graph.
UPSTREAM_DOMAINS = (
    APP_ROOT / "domain" / "engineering_evidence",
    APP_ROOT / "domain" / "engineering_entities",
    APP_ROOT / "domain" / "engineering_facts",
    APP_ROOT / "domain" / "engineering_semantics",
    APP_ROOT / "domain" / "human_review",
)

UPSTREAM_SERVICES = (
    APP_ROOT / "services" / "engineering_evidence_service.py",
    APP_ROOT / "services" / "engineering_entity_service.py",
    APP_ROOT / "services" / "engineering_fact_service.py",
    APP_ROOT / "services" / "engineering_semantic_service.py",
    APP_ROOT / "services" / "human_review_service.py",
)


def _modules(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)

    return found


# --- 1. Nobody upstream gained graph write authority --------------------


def test_no_upstream_context_imports_the_governed_graph() -> None:
    """
    The invariant EPIC 32.P1 was most likely to break. Producing a
    relationship is not authority to publish one: the location statement
    reaches the graph because promotion read it, not because semantics
    pushed it.
    """

    for directory in UPSTREAM_DOMAINS:
        for module in _modules(directory):
            for imported in _imports(module):
                assert "governed_knowledge_graph" not in imported, (
                    f"{module.relative_to(APP_ROOT)} imports the governed "
                    "graph"
                )


def test_no_upstream_service_writes_a_graph_table() -> None:
    """A service that named a graph table would be a second way for
    knowledge to become queryable."""

    for path in UPSTREAM_SERVICES:
        if not path.exists():
            continue

        source = path.read_text(encoding="utf-8")

        for table in GRAPH_TABLES:
            assert table not in source, f"{path.name} names {table}"

        for record in ("GraphNodeRecord", "GraphEdgeRecord"):
            assert record not in source, f"{path.name} names {record}"


def test_promotion_remains_the_only_graph_authoring_service() -> None:
    """
    AF-KG-003, re-asserted after the vocabulary grew.

    Asserted on the **capability** rather than on ORM records, matching
    the freeze's own formulation: the graph is written through a port, so
    the question is which application responsibility may call it. A
    second name here would mean the new relationship arrived with a
    second way to publish knowledge.
    """

    authorities = sorted(
        path.name
        for path in _modules(APP_ROOT / "services")
        if "upsert_node" in path.read_text(encoding="utf-8")
        or "upsert_edge" in path.read_text(encoding="utf-8")
    )

    assert authorities == ["knowledge_promotion_service.py"]


# --- 2. The vocabulary stayed closed and honest -------------------------


def test_every_governed_edge_kind_comes_from_a_semantic_statement_type(
) -> None:
    """
    An edge kind with no statement behind it could never be promoted, so
    it would be ontology this platform asserts but cannot produce.
    """

    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        EDGE_KIND_FOR_STATEMENT_TYPE,
        GraphEdgeKind,
    )

    statement_types = {member.value for member in SemanticStatementType}

    assert set(EDGE_KIND_FOR_STATEMENT_TYPE) <= statement_types
    assert set(EDGE_KIND_FOR_STATEMENT_TYPE.values()) == set(GraphEdgeKind)


def test_every_governed_node_kind_comes_from_an_entity_type() -> None:
    from app.domain.engineering_entities.entity_models import EntityType
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        NODE_KIND_FOR_ENTITY_TYPE,
        GraphNodeKind,
    )

    entity_types = {member.value for member in EntityType}

    assert set(NODE_KIND_FOR_ENTITY_TYPE) <= entity_types
    assert set(NODE_KIND_FOR_ENTITY_TYPE.values()) == set(GraphNodeKind)


def test_every_semantic_statement_type_has_a_producing_rule() -> None:
    """A meaning nothing can assign would be vocabulary implying a
    capability."""

    from app.domain.engineering_semantics.semantic_rules import (
        SEMANTIC_RULES,
    )
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )

    produced = {rule.statement_type for rule in SEMANTIC_RULES}

    assert produced == set(SemanticStatementType)


def test_every_fact_predicate_has_a_producing_rule() -> None:
    from app.domain.engineering_facts.fact_construction_rules import (
        CONSTRUCTION_RULES,
    )
    from app.domain.engineering_facts.fact_predicates import FactPredicate

    produced = {rule.predicate for rule in CONSTRUCTION_RULES}

    assert produced == set(FactPredicate)


def test_every_evidence_type_has_a_producing_extraction_rule() -> None:
    from app.domain.engineering_evidence.evidence_models import EvidenceType
    from app.domain.engineering_evidence.evidence_rules import (
        EXTRACTION_RULES,
    )

    produced = {rule.evidence_type for rule in EXTRACTION_RULES}

    assert produced == set(EvidenceType)


def test_every_edge_kind_declares_its_endpoint_constraint() -> None:
    """An edge kind with no declared endpoints would be promotable in any
    direction, between any two node kinds."""

    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        EDGE_ENDPOINT_KINDS,
        GraphEdgeKind,
    )

    assert set(EDGE_ENDPOINT_KINDS) == set(GraphEdgeKind)


def test_no_topology_or_classification_vocabulary_was_introduced() -> None:
    """
    The named refusals. ``IS_LOCATED_IN`` is containment; none of these
    followed it in, and each would need its own evidence.
    """

    from app.domain.engineering_facts.fact_predicates import FactPredicate
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
        GraphNodeKind,
    )

    forbidden = {
        "CONNECTED_TO",
        "FEEDS",
        "SUPPLIES",
        "PROTECTS",
        "UPSTREAM_OF",
        "DOWNSTREAM_OF",
        "PART_OF",
        "CONTAINS",
        "HAS_TERMINAL",
        "ENERGIZED",
        "IS_TRANSFORMER",
        "IS_BREAKER",
        "BAY",
        "PANEL",
        "BUSBAR",
    }

    for vocabulary in (
        FactPredicate,
        SemanticStatementType,
        GraphEdgeKind,
        GraphNodeKind,
    ):
        declared = {member.name for member in vocabulary}

        assert not declared & forbidden, (
            f"{vocabulary.__name__} declares {declared & forbidden}"
        )


# --- 3. No inference was added upstream of reasoning --------------------


def test_the_semantic_interpreter_reads_facts_and_not_evidence() -> None:
    """
    The boundary that makes the location statement reviewable as an
    interpretation rather than as an extraction. If the interpreter could
    read evidence it could reinterpret an observation, and the fact would
    stop being the account of what was associated.
    """

    module = (
        APP_ROOT / "domain" / "engineering_semantics" / "semantic_interpreter.py"
    )

    for imported in _imports(module):
        assert "engineering_evidence" not in imported
        assert "engineering_entities" not in imported
        assert "canonical_text" not in imported


def test_the_fact_constructor_reads_entities_and_not_the_document() -> None:
    module = (
        APP_ROOT / "domain" / "engineering_facts" / "fact_constructor.py"
    )

    for imported in _imports(module):
        assert "canonical_text" not in imported
        assert "engineering_evidence" not in imported


def test_no_semantic_rule_composes_two_predicates() -> None:
    """
    A rule reading two predicates would be reasoning: it would conclude
    something neither fact states. Every rule here reads exactly one.
    """

    from app.domain.engineering_semantics.semantic_rules import (
        SEMANTIC_RULES,
    )

    for rule in SEMANTIC_RULES:
        assert isinstance(rule.supported_predicate, object)
        assert not isinstance(rule.supported_predicate, (tuple, list, set))


def test_a_fact_rule_never_reads_another_rules_output() -> None:
    """
    Every construction rule associates two **entity** types. A rule whose
    subject or object were a fact would be building a fact from a fact,
    which is inference wearing a construction rule's clothes.
    """

    from app.domain.engineering_entities.entity_models import EntityType
    from app.domain.engineering_facts.fact_construction_rules import (
        CONSTRUCTION_RULES,
    )

    for rule in CONSTRUCTION_RULES:
        assert isinstance(rule.subject_type, EntityType)
        assert isinstance(rule.object_type, EntityType)


def test_no_cross_document_resolution_was_introduced() -> None:
    """
    Entity keys stay document-scoped. Two documents writing ``+E01`` are
    two locations until somebody builds - and reviews - a capability that
    says otherwise.
    """

    source = (
        APP_ROOT / "domain" / "engineering_entities" / "entity_resolver.py"
    ).read_text(encoding="utf-8")

    assert "document_id" in source

    from app.domain.engineering_entities.entity_resolution_rules import (
        designation_grouping_key,
    )

    # The grouping key names what makes two observations one object, and
    # a document is not one of its inputs *because the resolver is only
    # ever handed one document's evidence*.
    assert designation_grouping_key("+E01", "observed", "1.0") == (
        "+E01",
        "observed",
        "1.0",
    )


# --- 4. Purity ----------------------------------------------------------


def test_the_new_vocabulary_modules_import_no_infrastructure() -> None:
    forbidden = (
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "app.models",
        "app.database",
        "app.infrastructure",
        "anthropic",
    )

    modules = [
        APP_ROOT / "domain" / "engineering_evidence" / "evidence_rules.py",
        APP_ROOT / "domain" / "engineering_evidence" / "evidence_patterns.py",
        APP_ROOT
        / "domain"
        / "engineering_entities"
        / "entity_resolution_rules.py",
        APP_ROOT
        / "domain"
        / "engineering_facts"
        / "fact_construction_rules.py",
        APP_ROOT / "domain" / "engineering_semantics" / "semantic_rules.py",
        GRAPH_DOMAIN / "graph_vocabulary.py",
    ]

    for module in modules:
        for imported in _imports(module):
            for banned in forbidden:
                assert not imported.startswith(banned), (
                    f"{module.name} imports {imported}"
                )


def test_the_location_rule_uses_no_geometry_or_scoring() -> None:
    """
    The refusals that keep this a syntax rule rather than a layout
    heuristic. There is no coordinate, no distance and no threshold
    anywhere in the path that produces the relationship.
    """

    modules = (
        APP_ROOT / "domain" / "engineering_evidence" / "evidence_rules.py",
        APP_ROOT / "domain" / "engineering_evidence" / "evidence_extractor.py",
        APP_ROOT / "domain" / "engineering_facts" / "fact_constructor.py",
        APP_ROOT / "domain" / "engineering_semantics" / "semantic_interpreter.py",
    )

    for module in modules:
        source = module.read_text(encoding="utf-8").lower()

        for banned in (
            "threshold",
            "distance",
            "similarity",
            "confidence",
            "embedding",
            "nearest",
        ):
            assert banned not in source, f"{module.name} mentions {banned}"
