"""
Architecture tests for the Governed Knowledge Graph.

Structural, on the AST or the filesystem, never on prose. These keep the
graph a **projection** after everybody who remembers why has left:

- the engineering pipeline must never learn that a graph exists;
- Human Review must never learn it either;
- the graph must never reach into an engineering implementation;
- no promotion may write an engineering or review table;
- the graph must hold no mutable state that is not derived.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

GRAPH_DOMAIN = APP_ROOT / "domain" / "governed_knowledge_graph"
GRAPH_INFRASTRUCTURE = (
    APP_ROOT / "infrastructure" / "governed_knowledge_graph"
)

ENGINEERING_DOMAINS = (
    "canonical_pdf",
    "canonical_text",
    "engineering_evidence",
    "engineering_entities",
    "engineering_facts",
    "engineering_semantics",
    "ontology",
)

GRAPH_PACKAGE = "app.domain.governed_knowledge_graph"


def _modules(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


# --- The contexts do not know each other --------------------------------


def test_no_engineering_domain_module_imports_the_graph() -> None:
    """
    **The pipeline must not know it is projected.**

    The moment a rule could consult the graph, engineering output would
    depend on what somebody had approved, and the determinism the whole
    platform rests on would be gone.
    """

    offenders: list[str] = []

    for context in ENGINEERING_DOMAINS:
        for module in _modules(APP_ROOT / "domain" / context):
            for imported in _imports(module):
                if imported.startswith(GRAPH_PACKAGE):
                    offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_human_review_does_not_import_the_graph() -> None:
    """
    A review is a judgement about a statement, not an instruction to
    publish. Promotion is a separate act with a separate capability, and
    the review context must stay unaware that it exists.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "human_review"):
        for imported in _imports(module):
            if imported.startswith(GRAPH_PACKAGE):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_graph_domain_imports_no_engineering_or_review_module() -> None:
    """
    The subtler direction. `promotion_rules` decides what may be promoted
    - which sounds like it needs a statement and a review, and does not:
    it takes a `PromotionCandidate` of plain strings that the application
    service assembles. That indirection is what this test protects, and
    what lets every promotion rule be tested without a pipeline.
    """

    forbidden = tuple(
        f"app.domain.{context}" for context in ENGINEERING_DOMAINS
    ) + ("app.domain.human_review",)

    offenders: list[str] = []

    for module in _modules(GRAPH_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_graph_domain_imports_no_infrastructure() -> None:
    forbidden = (
        "sqlalchemy",
        "fastapi",
        "starlette",
        "app.models",
        "app.infrastructure",
        "app.routers",
        "app.schemas",
        "app.services",
        "app.database",
    )

    offenders: list[str] = []

    for module in _modules(GRAPH_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_only_the_promotion_service_joins_the_three_contexts() -> None:
    """
    One place, and it is named. A second module reading semantics and
    reviews to decide what belongs in the graph would be a second,
    quietly diverging definition of governed knowledge.
    """

    joiners: list[str] = []

    for module in _modules(APP_ROOT / "services"):
        imports = _imports(module)

        touches_graph = any(
            item.startswith(GRAPH_PACKAGE) for item in imports
        )
        touches_semantics = any(
            "engineering_semantics" in item for item in imports
        )

        if touches_graph and touches_semantics:
            joiners.append(module.name)

    assert joiners == ["knowledge_promotion_service.py"]


# --- The graph writes nothing upstream ----------------------------------


def test_no_graph_module_references_an_upstream_record() -> None:
    """
    Promotion reads semantics and reviews through their repositories and
    writes only the `governed_graph_*` tables.
    """

    upstream_records = (
        "EngineeringSemanticSetRecord",
        "EngineeringSemanticStatementRecord",
        "EngineeringFactRecord",
        "EngineeringEntityRecord",
        "EngineeringEvidenceRecord",
        "ReviewRecord",
    )

    modules = (
        _modules(GRAPH_DOMAIN)
        + _modules(GRAPH_INFRASTRUCTURE)
        + [APP_ROOT / "services" / "knowledge_promotion_service.py"]
    )

    offenders: list[str] = []

    for module in modules:
        source = module.read_text(encoding="utf-8")

        for record in upstream_records:
            if record in source:
                offenders.append(f"{module.name} references {record}")

    assert offenders == []


def test_the_promotion_service_runs_no_pipeline_stage_and_records_no_review() -> (
    None
):
    source = (
        APP_ROOT / "services" / "knowledge_promotion_service.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "interpret_document_facts",
        "construct_engineering",
        "resolve_engineering",
        "extract_engineering",
        "canonicalize",
        "record_review",
        # The review repository's own append. A plain `list.append` is
        # not a violation, so the receiver is named rather than the
        # method - a bare `.append(` would flag every accumulator here.
        "reviews.append(",
    ):
        assert forbidden not in source, forbidden


def test_the_graph_repository_touches_only_its_own_tables() -> None:
    source = (
        GRAPH_INFRASTRUCTURE
        / "sqlalchemy_governed_graph_repository.py"
    ).read_text(encoding="utf-8")

    assert "GovernedGraphNodeRecord" in source
    assert "GovernedGraphEdgeRecord" in source

    for forbidden in (
        "EngineeringSemantic",
        "EngineeringFact",
        "EngineeringEntity",
        "ReviewRecord",
        "DocumentRecord",
    ):
        assert forbidden not in source


# --- Nothing enters the graph except through a promotion ----------------


def test_the_repository_offers_no_way_to_write_ungoverned_knowledge() -> None:
    """
    Every write takes an object the promotion service built from an
    approved statement. There is no `create_node(label=…)`, which is what
    makes "no other source may insert engineering knowledge" a property
    of the interface rather than a promise.
    """

    source = (GRAPH_DOMAIN / "graph_repository.py").read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {
        "upsert_node",
        "upsert_edge",
        "record_generation",
        "clear",
        "find_node",
        "find_edge",
        "find_edge_by_statement",
        "list_nodes",
        "list_edges",
        "edges_for_node",
        "all_edges",
        "all_nodes",
        "latest_generation",
        "count_active",
    }


def test_promotion_rules_are_a_pure_function() -> None:
    """No repository, no request, no clock - a candidate in, a decision out."""

    path = GRAPH_DOMAIN / "promotion_rules.py"

    assert _imports(path) <= {
        "__future__",
        "dataclasses",
        "enum",
        "app.domain.governed_knowledge_graph.graph_vocabulary",
    }


def test_the_promotion_rule_has_exactly_one_definition() -> None:
    """
    Incremental promotion and a full rebuild must never disagree about
    what is promotable, so both call the same function and nothing else
    re-implements it.
    """

    evaluators = [
        module.name
        for module in _modules(APP_ROOT)
        if "def evaluate(" in module.read_text(encoding="utf-8")
        and "governed_knowledge_graph" in str(module)
    ]

    assert evaluators == ["promotion_rules.py"]


# --- The graph holds no state that is not derived -----------------------


def test_the_graph_tables_carry_no_ungoverned_field() -> None:
    """
    No confidence, score or weight. Knowledge is in the graph because an
    engineer approved it; a number expressing how much to trust it would
    reintroduce exactly the ungoverned trust signal ADR-0004 rejected.

    No free-form property bag either - that would make this the generic
    property graph the context exists not to be.
    """

    path = APP_ROOT / "models" / "governed_knowledge_graph.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    columns = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    for forbidden in (
        "confidence",
        "score",
        "weight",
        "properties",
        "attributes",
        "metadata",
        "payload",
        "notes",
    ):
        assert forbidden not in columns, forbidden


def test_every_graph_object_carries_its_provenance() -> None:
    """
    Explainability is mandatory, and structural: the provenance columns
    are `nullable=False` on both tables, so an untraceable row cannot be
    written.
    """

    source = (
        APP_ROOT / "models" / "governed_knowledge_graph.py"
    ).read_text(encoding="utf-8")

    for field in (
        "statement_key",
        "review_id",
        "reviewer_display_name",
        "semantic_rule_id",
        "semantic_rule_version",
        "support_fingerprint",
        "content_checksum",
    ):
        assert f"{field}: Mapped" in source, field

    # Non-nullable on both tables: an untraceable row cannot be written.
    assert "nullable=True" not in source.split("statement_key")[1][:200]


def test_the_graph_tables_have_no_foreign_key() -> None:
    """
    Not to the semantic tables - a re-run replaces a set, and a constraint
    would either block the pipeline or cascade a historical projection
    into nothing. Not to reviews or users either.
    """

    source = (
        APP_ROOT / "models" / "governed_knowledge_graph.py"
    ).read_text(encoding="utf-8")

    assert "ForeignKey" not in source


def test_identity_is_derived_and_never_taken_from_a_label() -> None:
    source = (GRAPH_DOMAIN / "graph_identity.py").read_text(
        encoding="utf-8"
    )

    assert "hashlib.sha256" in source
    assert "entity_key" in source
    assert "statement_key" in source

    tree = ast.parse(source)

    # No function here may take a label: identity that could be composed
    # from one is identity that eventually is.
    parameters = {
        argument.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for argument in node.args.args
    }

    assert "label" not in parameters
    assert "display_name" not in parameters


def test_the_clear_operation_exists_only_on_the_graph() -> None:
    """
    Dropping everything is safe **only** for a derived projection.
    Nothing else in this system has such an operation, and nothing else
    may acquire one.
    """

    holders = [
        module.name
        for module in _modules(APP_ROOT / "domain")
        if "def clear(" in module.read_text(encoding="utf-8")
    ]

    assert holders == ["graph_repository.py"]


def test_the_vocabulary_admits_only_governed_concepts() -> None:
    """
    Two node kinds and one edge kind. A `Voltage`, `Protection`,
    `Connection`, `Function` or `Location` kind would be inventing
    engineering ontology - and the semantics context refuses to interpret
    voltage upstream for exactly that reason.
    """

    source = (GRAPH_DOMAIN / "graph_vocabulary.py").read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    def members(name: str) -> list[str]:
        node = next(
            item
            for item in ast.walk(tree)
            if isinstance(item, ast.ClassDef) and item.name == name
        )

        return [
            target.id
            for statement in node.body
            if isinstance(statement, ast.Assign)
            for target in statement.targets
            if isinstance(target, ast.Name)
        ]

    assert sorted(members("GraphNodeKind")) == [
        "ENGINEERING_ASSET",
        "ENGINEERING_QUANTITY",
    ]
    assert members("GraphEdgeKind") == ["HAS_RATED_POWER"]


# --- No query language --------------------------------------------------


def test_no_graph_query_language_is_imported_or_implemented() -> None:
    forbidden = ("cypher", "neo4j", "graphql", "sparql", "gremlin")

    for module in (
        _modules(GRAPH_DOMAIN)
        + _modules(GRAPH_INFRASTRUCTURE)
        + [
            APP_ROOT / "services" / "knowledge_promotion_service.py",
            APP_ROOT / "routers" / "governed_knowledge_graph.py",
        ]
    ):
        source = module.read_text(encoding="utf-8").lower()

        for item in forbidden:
            assert f"import {item}" not in source, module.name
