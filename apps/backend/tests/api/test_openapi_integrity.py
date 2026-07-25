"""
OpenAPI/routing integrity checks (Milestone 12, Workstream 4). These
inspect ``app.main.app`` directly - importing it is safe in tests since
it no longer touches the database at import time (no ``create_all()``,
see docs/architecture/database_migrations.md) and generating the
OpenAPI schema performs no database query at all.
"""

from __future__ import annotations

from collections import Counter

import app.main
from fastapi.routing import APIRoute

app_instance = app.main.app


def _api_routes() -> list[APIRoute]:
    """
    Flattens ``app_instance.routes`` into real ``APIRoute`` objects.
    This FastAPI version wraps every ``include_router()``-registered
    router in a lazy ``_IncludedRouter`` object rather than exposing its
    routes directly on ``app.routes`` - only routes declared straight on
    ``app`` (``/``, ``/health``) appear as bare ``APIRoute`` instances.
    ``_IncludedRouter.original_router`` is the actual ``APIRouter``
    instance each of this project's routers built, and its own
    ``.routes`` are real, fully-tagged ``APIRoute`` objects.
    """

    routes: list[APIRoute] = []

    for route in app_instance.routes:
        if isinstance(route, APIRoute):
            routes.append(route)
        elif type(route).__name__ == "_IncludedRouter":
            routes.extend(
                sub_route
                for sub_route in route.original_router.routes
                if isinstance(sub_route, APIRoute)
            )

    return routes


def test_application_imports_and_openapi_schema_generates() -> None:
    schema = app_instance.openapi()

    assert schema["openapi"]
    assert schema["paths"]


def test_no_duplicate_operation_ids() -> None:
    schema = app_instance.openapi()

    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    duplicates = [
        operation_id
        for operation_id, count in Counter(operation_ids).items()
        if count > 1
    ]

    assert duplicates == []


def test_no_duplicate_path_and_method_pairs() -> None:
    """
    Checked against the route table directly, not the already-deduplicated
    OpenAPI dict: two routes sharing an exact (path, method) would
    silently shadow one another at runtime (FastAPI matches the first
    registered route), which the OpenAPI schema alone cannot reveal.
    """

    pairs = [
        (route.path, method)
        for route in _api_routes()
        for method in route.methods
    ]

    duplicates = [
        pair for pair, count in Counter(pairs).items() if count > 1
    ]

    assert duplicates == []


def test_legacy_and_governed_knowledge_graph_paths_do_not_collide() -> (
    None
):
    """
    The legacy router (app.routers.knowledge_graph) and the governed
    routers (app.routers.project_knowledge_graph,
    app.routers.graph_query) intentionally live in different URL
    namespaces (bare '/projects/{id}/knowledge-graph' and
    '/projects/{id}/entities...' for legacy, versus
    '/projects/{id}/knowledge-graph/nodes...' and
    '/projects/{id}/graph/...' for governed). Checked here as an exact
    (path, method) check restricted to those two path families
    specifically - a plain path-uniqueness check would wrongly flag
    every route that legitimately serves both GET and POST/PATCH/DELETE
    on the same path.
    """

    legacy_and_governed_routes = [
        route
        for route in _api_routes()
        if "/knowledge-graph" in route.path or "/graph/" in route.path
    ]

    pairs = [
        (route.path, method)
        for route in legacy_and_governed_routes
        for method in route.methods
    ]

    duplicates = [
        pair for pair, count in Counter(pairs).items() if count > 1
    ]

    assert duplicates == []


def test_every_active_router_contributes_at_least_one_route() -> None:
    tags_seen = {
        tag
        for route in _api_routes()
        for tag in (route.tags or [])
    }

    expected_tags = {
        "Documents",
        "Projects",
        "Knowledge Graph (Legacy)",
        "Engineering Index",
        "Proposed Claims",
        "Review Workflow",
        "Canonicalization",
        "Graph Builder",
        "Project Knowledge Graph",
        "Graph Query",
        "Structured Retrieval",
    }

    missing = expected_tags - tags_seen

    assert missing == set()


def test_legacy_router_is_marked_deprecated() -> None:
    legacy_routes = [
        route
        for route in _api_routes()
        if "Knowledge Graph (Legacy)" in (route.tags or [])
    ]

    assert legacy_routes
    assert all(route.deprecated for route in legacy_routes)


def test_governed_graph_routes_are_not_deprecated() -> None:
    governed_tags = {
        "Project Knowledge Graph",
        "Graph Query",
        "Graph Builder",
        "Structured Retrieval",
    }

    governed_routes = [
        route
        for route in _api_routes()
        if governed_tags & set(route.tags or [])
    ]

    assert governed_routes
    assert not any(route.deprecated for route in governed_routes)


def test_governed_knowledge_pipeline_routes_declare_response_models() -> (
    None
):
    """
    Project convention (see every governed router built in Milestones
    9-11.3): every route that returns a body declares an explicit
    ``response_model``, never a bare dict/ORM object. A ``204 No
    Content`` route is correctly exempt - by definition it returns no
    body, so FastAPI convention is to declare no ``response_model`` at
    all (e.g. ``DELETE /proposed-claims/{claim_id}``,
    ``DELETE /documents/{document_id}/engineering-index``). Checked here
    for the governed knowledge-pipeline routers specifically - the
    legacy router predates this convention for some of its endpoints and
    is exempted, not silently included, per this milestone's "do not
    rename/rewrite legacy code without a demonstrated defect"
    instruction.
    """

    governed_tags = {
        "Engineering Index",
        "Proposed Claims",
        "Review Workflow",
        "Canonicalization",
        "Graph Builder",
        "Project Knowledge Graph",
        "Graph Query",
        "Structured Retrieval",
    }

    governed_routes = [
        route
        for route in _api_routes()
        if governed_tags & set(route.tags or [])
        and route.status_code != 204
    ]

    missing_response_model = [
        route.path
        for route in governed_routes
        if route.response_model is None
    ]

    assert missing_response_model == []
