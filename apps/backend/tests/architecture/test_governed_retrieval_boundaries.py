"""
Architecture tests for Governed Structured Retrieval (EPIC 31.2).

Structural, on the AST or the filesystem, never on prose. These are the
standing proof of the boundary the milestone created, after everybody
who remembers why has left:

```
Governed Knowledge Graph  ──read──▶  Governed Structured Retrieval
                                              │
                                              ▼
                                     Engineering Engine
```

- retrieval may **read** the governed graph and may never write it;
- the governed graph must never learn that retrieval exists;
- the deterministic pipeline must know about neither;
- the Engineering Engine must reach governed knowledge only through
  retrieval, never through a repository of its own;
- exactly one module projects governed results into the legacy candidate
  vocabulary, so the day that module is deleted is the day the old
  mental model is gone.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

RETRIEVAL_DOMAIN = APP_ROOT / "domain" / "governed_retrieval"
RETRIEVAL_INFRASTRUCTURE = APP_ROOT / "infrastructure" / "governed_retrieval"
RETRIEVAL_SERVICE = APP_ROOT / "services" / "governed_retrieval_service.py"

GRAPH_DOMAIN = APP_ROOT / "domain" / "governed_knowledge_graph"

RETRIEVAL_PACKAGE = "app.domain.governed_retrieval"

#: The deterministic pipeline. None of it may know that anything reads
#: what it produces.
ENGINEERING_DOMAINS = (
    "canonical_pdf",
    "canonical_text",
    "engineering_evidence",
    "engineering_entities",
    "engineering_facts",
    "engineering_semantics",
    "ontology",
)


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


def _code(path: Path) -> str:
    """Source with docstrings stripped, so a module that *explains* a
    rule is not flagged for naming what it forbids."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef)
        ) and ast.get_docstring(node):
            node.body = node.body[1:] or [ast.Pass()]

    return ast.unparse(tree)


# --- The contexts do not know each other --------------------------------


def test_the_governed_graph_does_not_import_retrieval() -> None:
    """
    The direction that matters. A graph that could call retrieval would
    be a graph whose content could depend on what somebody searched for.
    """

    offenders: list[str] = []

    for module in _modules(GRAPH_DOMAIN):
        for imported in _imports(module):
            if imported.startswith(RETRIEVAL_PACKAGE):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_no_engineering_domain_module_imports_retrieval() -> None:
    """The pipeline must not know it is queried, for the same reason it
    must not know it is projected."""

    offenders: list[str] = []

    for context in ENGINEERING_DOMAINS:
        for module in _modules(APP_ROOT / "domain" / context):
            for imported in _imports(module):
                if imported.startswith(RETRIEVAL_PACKAGE):
                    offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_human_review_does_not_import_retrieval() -> None:
    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "human_review"):
        for imported in _imports(module):
            if imported.startswith(RETRIEVAL_PACKAGE):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_retrieval_domain_imports_no_infrastructure() -> None:
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

    for module in _modules(RETRIEVAL_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_retrieval_domain_reads_only_the_governed_graph() -> None:
    """
    Retrieval depends on the governed graph's vocabulary and on nothing
    else in the domain layer - not the pipeline, not Human Review, and
    not the Canonical Facts lineage it replaced.
    """

    permitted_domain_prefixes = (
        "app.domain.governed_retrieval",
        "app.domain.governed_knowledge_graph",
    )

    offenders: list[str] = []

    for module in _modules(RETRIEVAL_DOMAIN):
        for imported in _imports(module):
            if not imported.startswith("app.domain."):
                continue

            if not imported.startswith(permitted_domain_prefixes):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


# --- Retrieval cannot write ---------------------------------------------


def test_the_read_port_declares_no_write_operation() -> None:
    """
    "Retrieval never writes" is a property of the interface rather than a
    promise: there is nothing on this port to call.
    """

    source = (RETRIEVAL_DOMAIN / "governed_knowledge_reader.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    assert methods == {
        "find_node",
        "find_edge",
        "nodes",
        "nodes_by_identity",
        "edges",
        "edges_from_subjects",
        "latest_generation",
    }


def test_no_retrieval_module_can_write_a_graph_projection() -> None:
    forbidden = (
        "upsert_node",
        "upsert_edge",
        "record_generation",
        "clear()",
        "GovernedGraphRepository",
        "session.add",
        "commit()",
        "delete(",
    )

    modules = (
        _modules(RETRIEVAL_DOMAIN)
        + _modules(RETRIEVAL_INFRASTRUCTURE)
        + [RETRIEVAL_SERVICE]
    )

    offenders: list[str] = []

    for module in modules:
        source = _code(module)

        for item in forbidden:
            if item in source:
                offenders.append(f"{module.name} contains {item}")

    assert offenders == []


def test_only_the_domain_free_service_performs_retrieval_io() -> None:
    """Every read goes through the port, from one module. A second
    reader would be a second place for the scope rules to be applied -
    and eventually to be applied differently."""

    offenders = [
        module.name
        for module in _modules(RETRIEVAL_DOMAIN)
        if "reader." in _code(module)
    ]

    assert offenders == []


# --- Retrieval implements no governance ---------------------------------


def test_retrieval_never_recomputes_review_eligibility() -> None:
    """
    The promotion contract already guarantees that an `ACTIVE` object was
    authorised by a review that is `APPROVED` and whose applicability is
    `APPLIES`. Recomputing that here would create a second governance
    implementation, and the day the two disagreed neither would be
    authoritative.
    """

    forbidden = (
        "ReviewDecision",
        "ReviewApplicability",
        "APPROVED",
        "APPLIES",
        "human_review",
        "promotion_rules",
    )

    modules = _modules(RETRIEVAL_DOMAIN) + [RETRIEVAL_SERVICE]

    offenders: list[str] = []

    for module in modules:
        source = _code(module)

        for item in forbidden:
            if item in source:
                offenders.append(f"{module.name} references {item}")

    assert offenders == []


def test_retrieval_carries_no_confidence_score_or_weight() -> None:
    """
    Ranking is by match strategy, which is a fact about the comparison.
    A number expressing how much to trust the knowledge would reintroduce
    exactly the ungoverned trust signal ADR-0004 rejected.
    """

    forbidden = ("confidence", "probability", "relevance")

    for module in _modules(RETRIEVAL_DOMAIN) + [RETRIEVAL_SERVICE]:
        source = _code(module).lower()

        for item in forbidden:
            assert item not in source, f"{module.name}: {item}"


def test_no_property_bag_reaches_the_governed_retrieval_path() -> None:
    """
    No `properties`, `attributes`, `metadata` or `payload` dictionary
    anywhere in the governed retrieval path. Reintroducing one to ease
    the migration would undo ADR-0024's central decision.
    """

    forbidden = (
        "properties:",
        "attributes:",
        "payload:",
        "properties=",
        "attributes=",
        "payload=",
    )

    for module in _modules(RETRIEVAL_DOMAIN) + [RETRIEVAL_SERVICE]:
        source = module.read_text(encoding="utf-8")

        for item in forbidden:
            assert item not in source, f"{module.name}: {item}"


# --- No query language ---------------------------------------------------


def test_no_graph_query_language_is_imported_or_implemented() -> None:
    forbidden = ("cypher", "neo4j", "graphql", "sparql", "gremlin")

    modules = (
        _modules(RETRIEVAL_DOMAIN)
        + _modules(RETRIEVAL_INFRASTRUCTURE)
        + [RETRIEVAL_SERVICE, APP_ROOT / "routers" / "governed_retrieval.py"]
    )

    for module in modules:
        source = module.read_text(encoding="utf-8").lower()

        for item in forbidden:
            assert f"import {item}" not in source, module.name


def test_the_retrieval_api_accepts_no_arbitrary_filter() -> None:
    """
    The only inputs are a designation, a scope and a limit. A generic
    filter object would be a query language wearing a REST hat.
    """

    source = _code(APP_ROOT / "routers" / "governed_retrieval.py")

    for forbidden in ("filters", "where", "expression", "raw_query", "dict["):
        assert forbidden not in source, forbidden


# --- The Engineering Engine reaches governed knowledge one way ----------


def test_the_engine_no_longer_wires_the_legacy_graph_repository() -> None:
    """
    The milestone's headline, asserted structurally: the engine's
    composition root and its API composition root name the governed
    reader and no legacy graph repository at all.
    """

    for path in (
        APP_ROOT / "services" / "engineering_engine" / "composition.py",
        APP_ROOT / "routers" / "engineering_engine.py",
    ):
        source = _code(path)

        assert "governed_knowledge_reader" in source, path.name
        assert "GraphQueryRepository" not in source, path.name
        assert "graph_query" not in source, path.name


def test_no_engine_module_imports_legacy_retrieval() -> None:
    """
    Not the service, not the repository, not the request factory. The
    engine's retrieval is governed retrieval, with no second path.
    """

    forbidden = (
        "app.domain.graph_query",
        "app.infrastructure.graph_query",
        "app.services.graph_query_service",
        "app.services.structured_retrieval_service",
        "app.domain.structured_retrieval.structured_retrieval_factory",
    )

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "services" / "engineering_engine"):
        for imported in _imports(module):
            if imported in forbidden:
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_temporary_context_projection_is_gone() -> None:
    """
    EPIC 31.2's compatibility adapter is **deleted**, not merely unused.

    It projected governed results into the legacy ``KnowledgeCandidate``
    vocabulary so that retrieval and context could migrate separately.
    Both have migrated, so a module that still existed would be a legacy
    mental model waiting to be re-imported.
    """

    adapter = (
        APP_ROOT
        / "services"
        / "engineering_engine"
        / "governed_context_projection.py"
    )

    assert not adapter.exists()


def test_no_module_projects_governed_results_into_candidates() -> None:
    """
    The stronger statement: nothing anywhere translates governed
    knowledge into the legacy candidate vocabulary. If a second adapter
    is ever written, this fails on the day it is written rather than on
    the day somebody notices.
    """

    projectors = sorted(
        module.name
        for module in _modules(APP_ROOT / "services")
        if "KnowledgeCandidate" in _code(module)
        and "governed_retrieval" in _code(module)
    )

    assert projectors == []


def test_the_governed_engine_path_holds_no_legacy_retrieval_type() -> None:
    """
    Neither ``KnowledgeCandidate`` nor the Canonical Facts identity types
    survive anywhere the Engineering Engine's governed path can reach.

    Docstrings are stripped before the check: several modules name these
    types precisely in order to explain why they are gone, and a test
    that punished the explanation would be turned off rather than fixed.
    """

    governed_path = (
        _modules(APP_ROOT / "domain" / "context_builder")
        + _modules(APP_ROOT / "domain" / "prompt_builder")
        + _modules(APP_ROOT / "domain" / "engineering_response")
        + _modules(APP_ROOT / "services" / "engineering_engine")
        + [APP_ROOT / "services" / "context_builder_service.py"]
    )

    offenders: list[str] = []

    for module in governed_path:
        source = _code(module)

        for symbol in (
            "KnowledgeCandidate",
            "GraphEntityId",
            "GraphRelationshipType",
        ):
            if symbol in source:
                offenders.append(f"{module.name} mentions {symbol}")

    assert offenders == []


def test_the_governed_engine_path_carries_no_score_shaped_ordering() -> None:
    """
    EPIC 31.2 removed relevance scores from retrieval; 31.3 removed the
    last score-shaped ordering value from the context path.

    A governed result is ordered by *how* it matched - a closed strategy
    vocabulary - never by a number, because a number in an engineering
    answer is read as confidence whatever it was called.
    """

    governed_path = (
        _modules(APP_ROOT / "domain" / "context_builder")
        + _modules(APP_ROOT / "domain" / "governed_retrieval")
        + _modules(APP_ROOT / "services" / "engineering_engine")
    )

    offenders: list[str] = []

    for module in governed_path:
        source = _code(module)

        for symbol in ("KnowledgeCandidateScore", "ScoreComponentCategory"):
            if symbol in source:
                offenders.append(f"{module.name} mentions {symbol}")

    assert offenders == []


def test_context_assembly_holds_no_property_bag() -> None:
    """
    No ``dict`` or ``Any`` **field** on any context contract.

    ADR-0024 refused a property bag in the governed graph; a context that
    reintroduced one would put it back one layer downstream, where it
    would be just as untyped and rather harder to find.

    Only class-body annotations are inspected: a local ``dict`` used to
    group items while assembling is working data, not a contract, and
    banning it would be banning Python rather than banning property
    bags.
    """

    module = APP_ROOT / "domain" / "context_builder" / (
        "context_builder_models.py"
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue

            annotation = ast.unparse(statement.annotation)

            if "dict" in annotation or "Any" in annotation:
                offenders.append(f"{node.name}: {annotation}")

    assert offenders == []


def test_context_assembly_never_recomputes_governance() -> None:
    """
    Governance stays upstream.

    The promotion contract already guarantees that an active governed
    object was authorised by a review that is currently APPROVED and
    APPLIES. A second definition here would eventually disagree with the
    first, and the disagreement would be invisible.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "context_builder") + [
        APP_ROOT / "services" / "context_builder_service.py"
    ]:
        source = _code(module)

        for symbol in (
            "APPROVED",
            "APPLIES",
            "REQUIRES_REVALIDATION",
            "human_review",
        ):
            if symbol in source:
                offenders.append(f"{module.name} mentions {symbol}")

    assert offenders == []


def test_context_assembly_reads_nothing_for_itself() -> None:
    """
    Context Assembly transforms already-retrieved governed data and
    issues no query of its own.

    That is what keeps the security boundary: retrieval applied the
    project and document scope and the caller's authorization, and an
    assembly that could read for itself would be able to widen either
    without anything downstream noticing.
    """

    forbidden = (
        "sqlalchemy",
        "app.models",
        "app.infrastructure",
        "app.database",
        "GovernedKnowledgeReader",
        "GovernedGraphRepository",
    )

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "context_builder") + [
        APP_ROOT / "services" / "context_builder_service.py"
    ]:
        source = _code(module)

        for symbol in forbidden:
            if symbol in source:
                offenders.append(f"{module.name} mentions {symbol}")

    assert offenders == []


def test_governed_retrieval_does_not_import_context_assembly() -> None:
    """The dependency points one way. Retrieval decides what matched;
    context decides how it is represented, and retrieval must not learn
    that a context exists."""

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "governed_retrieval"):
        for imported in _imports(module):
            if "context_builder" in imported:
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_governed_graph_does_not_import_context_assembly() -> None:
    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "governed_knowledge_graph"):
        for imported in _imports(module):
            if "context_builder" in imported:
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_human_review_does_not_import_context_assembly() -> None:
    offenders: list[str] = []

    for module in _modules(APP_ROOT / "domain" / "human_review"):
        for imported in _imports(module):
            if "context_builder" in imported:
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_comparison_path_obeys_the_same_boundaries() -> None:
    """
    A comparison is two governed retrievals and two governed contexts.

    The comparison handlers are the likeliest place for a legacy
    compatibility route to survive unnoticed, because they are the one
    workflow with two of everything - so they are asserted explicitly
    rather than covered by a directory sweep.
    """

    source = _code(
        APP_ROOT
        / "services"
        / "engineering_engine"
        / "comparison_step_handlers.py"
    )

    assert "governed_context_projection" not in source
    assert "KnowledgeCandidate" not in source
    assert "left_results" in source
    assert "right_results" in source


# --- One governed retrieval implementation ------------------------------


def test_no_duplicate_governed_knowledge_reader_exists() -> None:
    implementations = sorted(
        path.name
        for path in _modules(APP_ROOT / "infrastructure")
        if "GovernedKnowledgeReader" in _code(path)
    )

    assert implementations == ["sqlalchemy_governed_knowledge_reader.py"]


def test_the_retrieval_service_is_the_only_orchestrator() -> None:
    """One module executes governed retrieval. A second would be a
    second place for scope and ordering to be decided."""

    orchestrators = sorted(
        module.name
        for module in _modules(APP_ROOT / "services")
        if "GovernedKnowledgeReader" in _code(module)
    )

    assert orchestrators == ["governed_retrieval_service.py"]
