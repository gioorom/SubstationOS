"""
The withdrawal of ``POST /projects/{id}/context-builder/build``
(EPIC 31.3).

The endpoint took a legacy ``KnowledgeCandidateCollection`` - the output
of ``/structured-retrieval/search`` - and assembled a ``ContextPackage``
from it. After this milestone a ``ContextPackage`` is a **governed**
artefact: every item asserts a statement key, a review id and a named
reviewer.

There is no honest request body for that any more. Accepting one would
let any authenticated caller mint a context that *looks* reviewed, which
is precisely the ADR-0004 failure three milestones were spent removing.
So the route is gone rather than repointed, and this file is what
remains of its test suite: proof that it is gone, and that the two
neighbouring stage-inspection routes still work.

`governed_context_assembly.md` records the decision. Assembling a
governed context is what the Engineering Engine does, from retrieval it
ran itself under its own scope and authorization.
"""

from __future__ import annotations

import app.main
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


def _paths() -> set[str]:
    """Every served path, including those contributed by included
    routers (which the app records as wrappers rather than as flat
    ``APIRoute``s)."""

    paths: set[str] = set()

    for route in app.main.app.routes:
        if isinstance(route, APIRoute):
            paths.add(route.path)
        elif type(route).__name__ == "_IncludedRouter":
            paths.update(
                sub_route.path
                for sub_route in route.original_router.routes
                if isinstance(sub_route, APIRoute)
            )

    return paths


def test_the_context_builder_build_route_no_longer_exists() -> None:
    """Against the live route table, not against a comment."""

    assert "/projects/{project_id}/context-builder/build" not in _paths()


def test_no_router_module_serves_context_assembly() -> None:
    """Deleted, not merely unregistered - a module that still exists is a
    module something can register again."""

    from pathlib import Path

    router = (
        Path(app.main.__file__).parent / "routers" / "context_builder.py"
    )

    assert not router.exists()


def test_posting_to_the_retired_route_is_a_plain_404(
    api_client: TestClient,
) -> None:
    """
    No ``410 Gone`` shim.

    The same reasoning ADR-0025 applied to the legacy graph routes: a
    shim preserves a URL whose only honest answer is that the request it
    accepted should never have produced governed knowledge, and it leaves
    a route to maintain and explain forever.
    """

    response = api_client.post(
        "/projects/1/context-builder/build", json={"candidates": {}}
    )

    assert response.status_code == 404


def test_the_neighbouring_stage_routes_still_exist() -> None:
    """
    Prompt Builder and Engineering Response keep their
    ``context_package`` bodies.

    They persist nothing, write no graph, and return a prompt or a
    response artefact, so a fabricated body harms only the caller's own
    answer. Context Assembly is different because it is the step where
    "this is governed knowledge" is *claimed*, and that claim must come
    from retrieval rather than from a request.
    """

    paths = _paths()

    assert "/projects/{project_id}/prompt-builder/build" in paths
    assert "/projects/{project_id}/engineering-response/build" in paths
