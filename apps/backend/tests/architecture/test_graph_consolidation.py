"""
Architecture tests for the graph consolidation (EPIC 31.1).

These are the standing proof that the legacy Knowledge Graph is gone and
does not come back. Every assertion is structural - on the filesystem,
the AST or the live route table - and each one would otherwise be
invisible the day somebody restores a file from history.

---

## What "one graph" means here, precisely

After EPIC 31.1 there is exactly **one governed engineering knowledge
graph**: `governed_knowledge_graph`, fed only by approved semantic
statements.

The Canonical Facts lineage (`graph_builder`, `project_knowledge_graph`,
`graph_query`) is **retained and still read at runtime** by Structured
Retrieval and the Engineering Engine. It is not a second governed
knowledge graph - it is the retrieval substrate of the LLM answering
stack, fed from a different lineage - but it *is* a second graph
implementation, and pretending otherwise in a test would be a lie.

So these tests assert what is true: the legacy path is gone, nothing
imports it, and the Canonical Facts lineage is present-and-accounted-for
rather than silently tolerated. `knowledge_graph.md` §2 and ADR-0025
state what closing that last gap requires.
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


# --- Exactly one governed knowledge graph -------------------------------


def test_there_is_exactly_one_governed_graph_context() -> None:
    """
    One bounded context whose job is governed engineering knowledge.

    `project_knowledge_graph` is deliberately **not** counted as one: it
    is the Canonical Facts retrieval substrate the Engineering Engine
    reads, retained by this milestone and documented as such. The test
    below pins that it is still exactly that, and nothing more.
    """

    graph_contexts = sorted(
        path.name
        for path in (APP_ROOT / "domain").iterdir()
        if path.is_dir()
        and "graph" in path.name
        and "__pycache__" not in path.name
    )

    assert graph_contexts == [
        "governed_knowledge_graph",
        "graph_builder",
        "graph_query",
        "project_knowledge_graph",
    ]


def test_the_engineering_engine_no_longer_reads_the_retained_lineage() -> (
    None
):
    """
    **EPIC 31.2 changed this test's subject, and that is the headline.**

    Until this milestone the Canonical Facts lineage was retained
    *because the Engineering Engine read it*, and this file asserted
    exactly that. It no longer does: engineering retrieval comes from the
    Governed Knowledge Graph, and the engine's two composition roots name
    the governed reader and no graph-query repository at all.

    What the assertion became is the same signal pointed the other way -
    if the engine ever reacquires a legacy graph dependency, this fails
    and says why.
    """

    for path in (
        APP_ROOT / "services" / "engineering_engine" / "composition.py",
        APP_ROOT / "routers" / "engineering_engine.py",
    ):
        source = _code(path)

        assert "governed_knowledge_reader" in source, path.name
        assert "GraphQueryRepository" not in source, path.name


def test_the_retained_lineage_is_still_reachable_through_its_own_api() -> (
    None
):
    """
    Why `project_knowledge_graph` is still here after EPIC 31.2, stated
    rather than assumed.

    Nothing in the engineering answering stack reads it any more. It
    remains because it is still a **live API capability** - four route
    groups (`/graph-builder`, `/graph-executions`, `/projects/{id}/graph`
    and `/projects/{id}/structured-retrieval`) serve it, and removing a
    served capability is a product decision rather than a cleanup.

    ADR-0026 records the objective condition that permits retirement:
    those routes going away. The day they do, this test fails and says
    the lineage has become genuinely dead.
    """

    routes = {route.path for route in _api_routes()}

    assert any(path.startswith("/graph-builder") for path in routes)
    assert any("/structured-retrieval" in path for path in routes)

    repository = (
        APP_ROOT
        / "infrastructure"
        / "graph_query"
        / "sqlalchemy_graph_query_repository.py"
    ).read_text(encoding="utf-8")

    assert "ProjectGraphNodeRecord" in repository


def test_the_two_lineages_do_not_share_a_repository() -> None:
    """
    No module reads both graphs. A single reader would be the "conditional
    logic depending on graph implementation" this milestone forbids.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "services") + _modules(
        APP_ROOT / "routers"
    ):
        if (
            "governed_knowledge_graph" in _code(module)
            and "project_knowledge_graph" in _code(module)
        ):
            offenders.append(module.name)

    assert offenders == []


def test_no_duplicate_governed_graph_repository_exists() -> None:
    implementations = sorted(
        path.name
        for path in _modules(APP_ROOT / "infrastructure")
        if "GovernedGraphRepository" in _code(path)
    )

    assert implementations == ["sqlalchemy_governed_graph_repository.py"]
