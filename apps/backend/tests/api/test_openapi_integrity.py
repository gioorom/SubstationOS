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
        "Engineering Index",
        "Proposed Claims",
        "Review Workflow",
        "Canonicalization",
        "Graph Builder",
        "Project Knowledge Graph",
        "Graph Query",
        "Structured Retrieval",
        "Context Builder",
        "Prompt Builder",
        "LLM Provider",
        "Governed Knowledge Graph",
    }

    missing = expected_tags - tags_seen

    assert missing == set()


def test_the_legacy_knowledge_graph_router_no_longer_exists() -> None:
    """
    Inverted by EPIC 31.1.

    This test used to assert that the legacy router was *marked
    deprecated*. The router is now gone, along with the service and the
    two ungoverned tables it read, so the assertion becomes the stronger
    one: no route anywhere serves the retired graph.

    Kept rather than deleted, because "the legacy graph is gone" is worth
    a standing check - a re-introduction would otherwise be invisible.
    """

    tags = {tag for route in _api_routes() for tag in (route.tags or [])}

    assert "Knowledge Graph (Legacy)" not in tags

    paths = {route.path for route in _api_routes()}

    # The three retired reads. `/projects/{id}/knowledge-graph/nodes` and
    # its siblings survive: those belong to the Canonical Facts lineage
    # (Milestone 11.2), which this milestone deliberately retained.
    assert "/projects/{project_id}/entities" not in paths
    assert "/projects/{project_id}/knowledge-graph" not in paths


def test_governed_graph_routes_are_not_deprecated() -> None:
    governed_tags = {
        "Project Knowledge Graph",
        "Graph Query",
        "Graph Builder",
        "Structured Retrieval",
        "Context Builder",
        "Prompt Builder",
        "LLM Provider",
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
        "Context Builder",
        "Prompt Builder",
        "LLM Provider",
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


def _response_schema_names(schema: dict) -> set[str]:
    """
    Every component schema reachable from a response body.

    Walks the `$ref` graph from each response outwards, so a credential
    field is caught whether it sits on the response model itself or three
    levels down inside it.
    """

    definitions = schema.get("components", {}).get("schemas", {})
    pending: list[str] = []

    def collect_refs(node: object) -> list[str]:
        if isinstance(node, dict):
            found: list[str] = []
            reference = node.get("$ref")

            if isinstance(reference, str) and reference.startswith(
                "#/components/schemas/"
            ):
                found.append(reference.rsplit("/", 1)[1])

            for value in node.values():
                found.extend(collect_refs(value))

            return found

        if isinstance(node, list):
            return [name for item in node for name in collect_refs(item)]

        return []

    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue

            for response in operation.get("responses", {}).values():
                pending.extend(collect_refs(response))

    reachable: set[str] = set()

    while pending:
        name = pending.pop()

        if name in reachable or name not in definitions:
            continue

        reachable.add(name)
        pending.extend(collect_refs(definitions[name]))

    return reachable


def test_no_response_schema_anywhere_exposes_a_credential() -> None:
    """
    No schema reachable from a **response** may carry an API key, a
    credential, a secret or a password (Milestone 16's own requirement),
    checked across every path rather than only the LLM Provider ones.

    Scoped to responses since EPIC 30.3, and the scoping is the point:
    a password must be able to travel *inbound* - there is no other way
    to log in or to change one - and must never travel back out. The
    companion test below asserts the second half.
    """

    schema = app_instance.openapi()
    definitions = schema.get("components", {}).get("schemas", {})
    forbidden_substrings = (
        "api_key",
        "apikey",
        "credential",
        "secret",
        "password",
    )

    offenders = [
        f"{name}.{property_name}"
        for name in _response_schema_names(schema)
        for property_name in definitions[name].get("properties", {})
        if any(
            forbidden in property_name.lower()
            for forbidden in forbidden_substrings
        )
    ]

    assert offenders == []


def test_the_models_that_accept_a_password_are_never_returned() -> None:
    """
    The other half. `LoginRequest`, `CreateUserRequest` and
    `ChangePasswordRequest` exist to carry a password in; a response that
    echoed one of them would send it straight back out.
    """

    reachable = _response_schema_names(app_instance.openapi())

    for name in (
        "LoginRequest",
        "CreateUserRequest",
        "ChangePasswordRequest",
    ):
        assert name not in reachable


def test_no_schema_anywhere_can_carry_a_session_token() -> None:
    """
    The session token leaves the server exactly once, in a `Set-Cookie`
    header. No model in the contract has a field it could be written to.

    Deliberately matched on *authentication* token names rather than on
    the word "token": this domain is full of legitimate ones - canonical
    text has `token_start` and `token_end`, LLM usage has `input_tokens`
    - and a test that flagged those would be turned off rather than
    fixed.
    """

    schema = app_instance.openapi()

    forbidden = (
        "session_token",
        "access_token",
        "refresh_token",
        "auth_token",
        "bearer",
        "token_fingerprint",
    )

    offenders = [
        f"{name}.{property_name}"
        for name, definition in schema.get("components", {})
        .get("schemas", {})
        .items()
        for property_name in definition.get("properties", {})
        if any(item in property_name.lower() for item in forbidden)
    ]

    assert offenders == []


def test_llm_invoke_endpoint_is_registered() -> None:
    schema = app_instance.openapi()
    assert "/projects/{project_id}/llm/invoke" in schema["paths"]
    assert "post" in schema["paths"]["/projects/{project_id}/llm/invoke"]


def test_engineering_response_build_endpoint_is_registered() -> None:
    schema = app_instance.openapi()
    path = "/projects/{project_id}/engineering-response/build"
    assert path in schema["paths"]
    assert "post" in schema["paths"][path]


def test_engineering_session_endpoints_are_registered() -> None:
    schema = app_instance.openapi()
    base = "/projects/{project_id}/engineering-session"
    for path in (
        base,
        f"{base}/append-response",
        f"{base}/change-state",
        f"{base}/update-configuration",
    ):
        assert path in schema["paths"]
        assert "post" in schema["paths"][path]


def test_conversation_endpoints_are_registered() -> None:
    schema = app_instance.openapi()
    base = "/projects/{project_id}/conversation"
    for path in (
        base,
        f"{base}/start-turn",
        f"{base}/add-message",
        f"{base}/attach-response",
        f"{base}/complete-turn",
        f"{base}/change-status",
    ):
        assert path in schema["paths"]
        assert "post" in schema["paths"][path]


def test_working_memory_endpoints_are_registered() -> None:
    schema = app_instance.openapi()
    base = "/projects/{project_id}/working-memory"
    for path in (f"{base}/build", f"{base}/rebuild"):
        assert path in schema["paths"]
        assert "post" in schema["paths"][path]


def test_engineering_intent_classify_endpoint_is_registered() -> None:
    schema = app_instance.openapi()
    path = "/projects/{project_id}/engineering-intents/classify"
    assert path in schema["paths"]
    assert "post" in schema["paths"][path]


def test_engineering_engine_execute_endpoint_is_registered() -> None:
    schema = app_instance.openapi()
    path = "/projects/{project_id}/engineering-engine/execute"
    assert path in schema["paths"]
    assert "post" in schema["paths"][path]


def test_engineering_engine_request_body_never_accepts_a_workflow_plan() -> (
    None
):
    """The server selects the workflow and constructs the plan - a
    caller can never supply one (Milestone 23A's own rule)."""

    schema = app_instance.openapi()
    body_schema = schema["components"]["schemas"][
        "EngineeringEngineExecuteRequestBody"
    ]

    forbidden = {"plan", "workflow_plan", "steps", "workflow_id", "status"}
    assert forbidden.isdisjoint(body_schema["properties"].keys())


def test_engineering_intent_request_body_never_accepts_a_classification() -> (
    None
):
    """The classification API must never accept a caller-supplied
    result - no intent type, confidence, evidence, or secondary match
    field exists on its request schema (Milestone 22's own rule)."""

    schema = app_instance.openapi()
    body_schema = schema["components"]["schemas"][
        "EngineeringIntentClassifyRequestBody"
    ]

    forbidden = {
        "intent_type",
        "confidence",
        "evidence",
        "secondary_intent_types",
        "engineering_intent_id",
    }
    assert forbidden.isdisjoint(body_schema["properties"].keys())


def test_llm_provider_neutral_schemas_are_not_anthropic_shaped() -> None:
    """
    The provider-neutral request contract (``LLMMessageRoleRead``-style
    enum, ``LLMMessage``, ``LLMRequest``) must not merely relabel
    Anthropic's own API shape. ``LLMMessageRole`` proves this
    structurally: it is a superset of Anthropic's own two-role
    vocabulary (``user``/``assistant``), carrying roles
    (``instruction``, ``context``, ``tool``) Anthropic's Messages API
    has no equivalent for - if the neutral contract had silently
    collapsed to Anthropic's own shape, only ``user``/``assistant``
    would appear here.
    """

    schema = app_instance.openapi()
    role_schema = schema["components"]["schemas"]["LLMMessageRole"]

    assert set(role_schema["enum"]) == {
        "instruction",
        "context",
        "user",
        "assistant",
        "tool",
    }
