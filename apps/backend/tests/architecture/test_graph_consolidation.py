"""
Architecture tests for the graph consolidation (EPIC 31.1 → 31.4).

These are the standing proof that **one** runtime engineering knowledge
graph exists and no second one comes back. Every assertion is structural
- on the filesystem, the AST, the live route table or the ORM metadata -
and each one would otherwise be invisible the day somebody restores a
file from history.

---

## What "one graph" means here, precisely

A **runtime engineering knowledge graph** is a bounded context that
stores graph-shaped engineering knowledge (nodes and relationships
between engineering concepts) and serves it to a runtime consumer.

After EPIC 31.4 there is exactly one: `governed_knowledge_graph`, fed
only by governed promotion from approved semantic statements.

Deliberately **not** counted, and each for a stated reason:

| Not a graph | Why |
|---|---|
| `engineering_facts`, `engineering_semantics` | Pipeline artefacts. A fact relates two entities, but nothing queries them as a graph and no projection is built from them. |
| `human_review`, `audit_events` | Records of judgement and of action. |
| `canonical_facts`, `proposed_claims`, `review_candidates` | Human-authored claims and the legacy review history over them. They are the *input* the retired projection was computed from, not a projection. |
| historical migrations, ADRs, archived docs | History. A migration that names a dropped table is doing its job. |

## The three retirements, and what each ended

| EPIC | Retired | Was fed by |
|---|---|---|
| 31.1 | `project_entities`, `entity_relations` | LLM extraction on upload, no review gate |
| 31.4 | `graph_builder`, `project_knowledge_graph`, `graph_query`, legacy `structured_retrieval` | Canonical Facts, from legacy-workflow claims |
| — | `governed_knowledge_graph` **survives** | Approved semantic statements |

EPIC 31.2 moved the Engineering Engine onto governed retrieval and 31.3
removed the last compatibility adapter; those two made 31.4 possible
without changing what the platform could answer.
"""


from __future__ import annotations

import ast
from pathlib import Path

import app.main
from fastapi.routing import APIRoute

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"

#: Every module EPIC 31.1 deleted. Named individually rather than by
#: glob, so restoring any one of them fails a test that says why.
RETIRED_MODULES = (
    APP_ROOT / "services" / "knowledge_graph.py",
    APP_ROOT / "routers" / "knowledge_graph.py",
    APP_ROOT / "schemas" / "knowledge_graph.py",
    APP_ROOT / "models" / "knowledge_graph.py",
    APP_ROOT / "services" / "ai",
    APP_ROOT / "services" / "entity_extractor.py",
    APP_ROOT / "services" / "topology",
)

#: The import paths that no longer resolve.
RETIRED_IMPORTS = (
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.models.knowledge_graph",
    "app.services.ai",
    "app.services.entity_extractor",
    "app.services.topology",
)

#: The two ORM classes that went with them.
RETIRED_SYMBOLS = ("ProjectEntity", "EntityRelation")


#: Every module EPIC 31.4 deleted: the Canonical Facts graph lineage and
#: the legacy retrieval that read it. Named per layer, so restoring any
#: single one fails a test that says which.
RETIRED_LINEAGE_PATHS = tuple(
    APP_ROOT / layer / name
    for layer in ("domain", "infrastructure")
    for name in ("graph_builder", "graph_query", "project_knowledge_graph")
) + (
    APP_ROOT / "domain" / "structured_retrieval",
    APP_ROOT / "models" / "graph_builder.py",
    APP_ROOT / "models" / "project_knowledge_graph.py",
    APP_ROOT / "routers" / "graph_builder.py",
    APP_ROOT / "routers" / "graph_query.py",
    APP_ROOT / "routers" / "project_knowledge_graph.py",
    APP_ROOT / "routers" / "structured_retrieval.py",
    APP_ROOT / "schemas" / "graph_builder.py",
    APP_ROOT / "schemas" / "graph_query.py",
    APP_ROOT / "schemas" / "project_knowledge_graph.py",
    APP_ROOT / "schemas" / "structured_retrieval.py",
    APP_ROOT / "services" / "graph_builder_service.py",
    APP_ROOT / "services" / "graph_execution_service.py",
    APP_ROOT / "services" / "graph_query_service.py",
    APP_ROOT / "services" / "structured_retrieval_service.py",
)


#: The import paths that no longer resolve.
RETIRED_LINEAGE_IMPORTS = (
    "app.domain.graph_builder",
    "app.domain.graph_query",
    "app.domain.project_knowledge_graph",
    "app.domain.structured_retrieval",
    "app.infrastructure.graph_builder",
    "app.infrastructure.graph_query",
    "app.infrastructure.project_knowledge_graph",
    "app.models.graph_builder",
    "app.models.project_knowledge_graph",
    "app.routers.graph_builder",
    "app.routers.graph_query",
    "app.routers.project_knowledge_graph",
    "app.routers.structured_retrieval",
    "app.schemas.graph_builder",
    "app.schemas.graph_query",
    "app.schemas.project_knowledge_graph",
    "app.schemas.structured_retrieval",
    "app.services.graph_builder_service",
    "app.services.graph_execution_service",
    "app.services.graph_query_service",
    "app.services.structured_retrieval_service",
)


#: The seven tables migration ``f4a90c27b615`` drops.
RETIRED_GRAPH_TABLES = (
    "graph_operation_batches",
    "graph_operations",
    "graph_executions",
    "graph_execution_operation_results",
    "graph_execution_fingerprints",
    "project_graph_nodes",
    "project_graph_relationships",
)


def _modules(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _code(path: Path) -> str:
    """
    Source with comments and docstrings stripped.

    The textual checks below must not flag this milestone's own prose:
    several modules name the retired tables precisely in order to explain
    why they are gone, and a test that punished the explanation would be
    turned off rather than fixed.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef)
        ) and ast.get_docstring(node):
            node.body = node.body[1:] or [ast.Pass()]

    return ast.unparse(tree)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


def _api_routes() -> list[APIRoute]:
    routes: list[APIRoute] = []

    for route in app.main.app.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif type(route).__name__ == "_IncludedRouter":
            routes.extend(
                sub_route
                for sub_route in route.original_router.routes
                if isinstance(sub_route, APIRoute)
            )

    return routes


# --- The legacy graph is gone -------------------------------------------


def test_every_retired_module_is_actually_deleted() -> None:
    """
    Not deprecated, not commented out - gone. A module that still exists
    is a module something can still import.
    """

    survivors = [
        str(path.relative_to(BACKEND_ROOT))
        for path in RETIRED_MODULES
        if path.exists()
    ]

    assert survivors == []


def test_no_runtime_code_imports_the_retired_graph() -> None:
    offenders: list[str] = []

    for module in _modules(APP_ROOT):
        for imported in _imports(module):
            if any(
                imported == item or imported.startswith(f"{item}.")
                for item in RETIRED_IMPORTS
            ):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_no_runtime_code_references_the_retired_tables() -> None:
    """
    Catches a reference that survived as a string or a stale annotation,
    which an import check alone would miss.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT):
        source = _code(module)

        for symbol in RETIRED_SYMBOLS:
            if symbol in source:
                offenders.append(f"{module.name} mentions {symbol}")

        for table in ("project_entities", "entity_relations"):
            if table in source:
                offenders.append(f"{module.name} mentions {table}")

    assert offenders == []


def test_no_route_serves_the_retired_graph() -> None:
    """Dead-route detection, against the live route table."""

    paths = {route.path for route in _api_routes()}
    tags = {tag for route in _api_routes() for tag in (route.tags or [])}

    assert "Knowledge Graph (Legacy)" not in tags

    for retired in (
        "/projects/{project_id}/knowledge-graph",
        "/projects/{project_id}/entities",
        "/projects/{project_id}/entities/{entity_id}",
    ):
        assert retired not in paths, retired


def test_the_retired_tables_are_not_in_the_orm_metadata() -> None:
    """
    The mapper is the authority on what a fresh database gets. A table
    still registered here would be recreated by `create_all` in the test
    fixtures even though the migration drops it.
    """

    from app.database.database import Base

    assert "project_entities" not in Base.metadata.tables
    assert "entity_relations" not in Base.metadata.tables


# --- Ingestion writes no graph ------------------------------------------


def test_uploading_a_document_invokes_no_downstream_consumer() -> None:
    """
    **The ADR-0004 violation, structurally ended.**

    `upload_document` used to inject `knowledge_graph.ingest_document`
    as the pipeline's downstream consumer, writing LLM-extracted
    entities into the queryable graph on every upload with no review
    gate. The consumer is now `None`, and this asserts it on the source
    rather than trusting a comment.
    """

    source = _code(APP_ROOT / "routers" / "documents.py")

    assert "consumer=None" in source
    assert "ingest_document" not in source


def test_no_router_writes_a_graph_during_ingestion() -> None:
    """
    Promotion is the only path into the governed graph, and it is an
    explicit, capability-gated action on its own route.
    """

    for name in ("documents.py", "document_ingestion.py"):
        source = _code(APP_ROOT / "routers" / name)

        for forbidden in (
            "GovernedGraphNodeRecord",
            "GovernedGraphEdgeRecord",
            "knowledge_promotion_service",
            "upsert_node",
            "upsert_edge",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


def test_only_the_promotion_service_writes_the_governed_graph() -> None:
    """No duplicate promotion path survives, and none was added."""

    writers = [
        module.name
        for module in _modules(APP_ROOT / "services")
        if "upsert_edge" in _code(module)
    ]

    assert writers == ["knowledge_promotion_service.py"]


# --- Exactly one runtime engineering graph ------------------------------


def test_there_is_exactly_one_runtime_engineering_graph_context() -> None:
    """
    **The invariant this whole milestone series exists to reach.**

    One bounded context whose job is graph-shaped engineering knowledge.
    Asserted on the domain packages that actually exist, so restoring a
    retired one fails here rather than being noticed later.
    """

    graph_contexts = sorted(
        path.name
        for path in (APP_ROOT / "domain").iterdir()
        if path.is_dir()
        and "graph" in path.name
        and "__pycache__" not in path.name
    )

    assert graph_contexts == ["governed_knowledge_graph"]


def test_no_retired_lineage_package_survives_anywhere_in_runtime() -> None:
    """Domain, infrastructure, models, schemas, services and routers -
    all six layers, because a retired context that kept one layer would
    be a context somebody could rebuild the rest of."""

    survivors = [
        str(path.relative_to(BACKEND_ROOT))
        for path in RETIRED_LINEAGE_PATHS
        if path.exists()
    ]

    assert survivors == []


def test_no_runtime_module_imports_the_retired_lineage() -> None:
    """
    Import-level proof, not a filename check.

    ``retrieval_bridge`` is the module this would have caught: it
    imported ``RetrievalMode`` from legacy Structured Retrieval right up
    until EPIC 31.4 moved the enum into the bridge, which is its real
    owner now.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT):
        for imported in _imports(module):
            if any(
                imported == item or imported.startswith(f"{item}.")
                for item in RETIRED_LINEAGE_IMPORTS
            ):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_no_route_serves_the_retired_lineage() -> None:
    """
    Against the live route table.

    ``/projects/{id}/knowledge-graph/*`` is named explicitly: it was the
    Canonical Facts projection wearing a path one character away from the
    governed ``/knowledge-graph/*`` routes, which survive.
    """

    paths = {route.path for route in _api_routes()}
    tags = {tag for route in _api_routes() for tag in (route.tags or [])}

    for retired_tag in (
        "Graph Builder",
        "Graph Query",
        "Project Knowledge Graph",
        "Structured Retrieval",
    ):
        assert retired_tag not in tags, retired_tag

    for path in paths:
        assert not path.startswith("/graph-builder"), path
        assert not path.startswith("/graph-executions"), path
        assert not path.startswith("/graph-operation-batches"), path
        assert not path.startswith(
            "/projects/{project_id}/graph/"
        ), path
        assert not path.startswith(
            "/projects/{project_id}/knowledge-graph"
        ), path
        assert "structured-retrieval" not in path, path

    # The governed successors are still served.
    assert "/knowledge-graph/nodes" in paths
    assert "/projects/{project_id}/governed-retrieval/assets" in paths


def test_the_retired_graph_tables_are_not_in_the_orm_metadata() -> None:
    """
    The mapper is the authority on what a fresh database gets. A table
    still registered here would be recreated by `create_all` in the test
    fixtures even though the migration drops it.
    """

    from app.database.database import Base

    for table in RETIRED_GRAPH_TABLES:
        assert table not in Base.metadata.tables, table

    # The governed projection, and the human-authored inputs the retired
    # one was computed from, all survive.
    for table in (
        "governed_graph_nodes",
        "governed_graph_edges",
        "governed_graph_generations",
        "canonical_facts",
        "proposed_claims",
        "review_candidates",
    ):
        assert table in Base.metadata.tables, table


def test_no_governed_module_reaches_the_retired_lineage() -> None:
    """
    Named contexts rather than a directory sweep, so the failure message
    says which governed boundary was crossed.
    """

    governed = (
        "governed_knowledge_graph",
        "governed_retrieval",
        "context_builder",
        "prompt_builder",
        "engineering_response",
        "retrieval_bridge",
    )

    offenders: list[str] = []

    for context in governed:
        for module in _modules(APP_ROOT / "domain" / context):
            for imported in _imports(module):
                if any(
                    imported.startswith(item)
                    for item in RETIRED_LINEAGE_IMPORTS
                ):
                    offenders.append(f"{context}/{module.name}: {imported}")

    for module in _modules(APP_ROOT / "services" / "engineering_engine"):
        for imported in _imports(module):
            if any(
                imported.startswith(item) for item in RETIRED_LINEAGE_IMPORTS
            ):
                offenders.append(f"engineering_engine/{module.name}")

    assert offenders == []


def test_no_duplicate_governed_graph_repository_exists() -> None:
    implementations = sorted(
        path.name
        for path in _modules(APP_ROOT / "infrastructure")
        if "GovernedGraphRepository" in _code(path)
    )

    assert implementations == ["sqlalchemy_governed_graph_repository.py"]


# --- No alternate path into queryable knowledge -------------------------


def test_only_governed_promotion_authors_queryable_knowledge() -> None:
    """
    **ADR-0004's rule, with nothing left behind it.**

    One application service may write the governed projection. Every
    other way engineering content enters this platform - an upload, a
    pipeline stage, an LLM answer, a legacy review approval, a retrieval,
    a context assembly - reaches no queryable graph at all, because there
    is no longer a second graph for it to reach.

    Repository persistence methods are storage, not authority: the check
    is on the *services* layer, which is where an application decides
    that knowledge may be published.
    """

    authors = sorted(
        module.name
        for module in _modules(APP_ROOT / "services")
        if "upsert_edge" in _code(module) or "upsert_node" in _code(module)
    )

    assert authors == ["knowledge_promotion_service.py"]


def test_no_pipeline_or_review_module_writes_any_graph() -> None:
    """
    The producers of engineering content must not learn that a queryable
    projection exists. Before EPIC 31.4 this could only be asserted for
    the governed graph, because a second one was reachable; now it is the
    whole statement.
    """

    producers = (
        "document_ingestion",
        "canonicalization",
        "engineering_evidence",
        "engineering_entities",
        "engineering_facts",
        "engineering_semantics",
        "human_review",
        "review_workflow",
        "proposed_claims",
    )

    offenders: list[str] = []

    for context in producers:
        directory = APP_ROOT / "domain" / context

        if not directory.exists():
            continue

        for module in _modules(directory):
            for imported in _imports(module):
                if "governed_knowledge_graph" in imported or any(
                    imported.startswith(item)
                    for item in RETIRED_LINEAGE_IMPORTS
                ):
                    offenders.append(f"{context}/{module.name}: {imported}")

    assert offenders == []
