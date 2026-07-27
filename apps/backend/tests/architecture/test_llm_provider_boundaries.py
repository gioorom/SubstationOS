"""
Architecture tests for the LLM Provider Abstraction Layer (EPIC 4,
Milestone 16) - a lightweight, repository-native ``ast``-based import
check, the same technique
``tests/architecture/test_bounded_context_dependencies.py`` already
established (no architecture-testing framework introduced). Kept in
its own file rather than folded into that one: the LLM Provider
Abstraction Layer is deliberately **not** a bounded context under
``app/domain/**`` (per this milestone's own instructions - "do not
create a new engineering bounded context merely to hold external
provider details"), so it does not participate in that file's
domain-context dependency-order table at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def _python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _files_under(*targets: Path) -> list[Path]:
    files: list[Path] = []

    for target in targets:
        if target.is_dir():
            files.extend(_python_files(target))
        elif target.is_file():
            files.append(target)

    return files


# --- The provider-neutral application layer -----------------------------
#
# app/application/ports/** and app/application/models/** are the
# provider-neutral contract itself - the one surface that must never
# know a provider exists. app/application/services/** and
# app/application/config/** are excluded from this particular check:
# the registry/service layer legitimately orchestrates whichever
# concrete adapter a caller (the router, the composition root) resolved
# and passed in, and reads PromptPackage/PromptValidation (allowed,
# shared-vocabulary domain types) - but even they must never import a
# provider SDK, a concrete adapter module, or another bounded context's
# service/router (see test_application_services_do_not_import_forbidden_modules
# below, a distinct, narrower check).

_APPLICATION_CONTRACT_SURFACE = (
    APP_ROOT / "application" / "ports",
    APP_ROOT / "application" / "models",
)

_FORBIDDEN_FOR_APPLICATION_CONTRACTS = (
    "anthropic",
    "openai",
    "azure",
    "ollama",
    "requests",
    "httpx",
    "sqlalchemy",
    "app.infrastructure.llm",
    "app.infrastructure.graph_query",
    "app.infrastructure.project_knowledge_graph",
    "app.services.graph_query_service",
    "app.routers.graph_query",
    "app.services.structured_retrieval_service",
    "app.routers.structured_retrieval",
    "app.services.context_builder_service",
    "app.routers.context_builder",
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
)


def test_application_contracts_do_not_import_forbidden_modules() -> None:
    offenders = [
        f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
        for path in _files_under(*_APPLICATION_CONTRACT_SURFACE)
        for module in _imported_module_names(path)
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in _FORBIDDEN_FOR_APPLICATION_CONTRACTS
        )
    ]

    assert offenders == []


# --- The full application layer (services/config included) -------------
#
# A narrower check: even the orchestration layer (registry, request
# service, configuration) must never import a provider SDK, a concrete
# provider adapter module, SQLAlchemy, or another bounded context's
# service/router. It legitimately imports concrete adapters nowhere -
# that wiring belongs to app/routers/llm_provider.py, the composition
# root - so this list is identical in spirit to the contract-only
# check above, just applied to the whole app/application tree.

_APPLICATION_LLM_SURFACE = (APP_ROOT / "application",)


def test_application_llm_layer_does_not_import_forbidden_modules() -> None:
    offenders = [
        f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
        for path in _files_under(*_APPLICATION_LLM_SURFACE)
        for module in _imported_module_names(path)
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in _FORBIDDEN_FOR_APPLICATION_CONTRACTS
        )
    ]

    assert offenders == []


# --- The Anthropic infrastructure adapter --------------------------------

_ANTHROPIC_INFRA_SURFACE = (APP_ROOT / "infrastructure" / "llm" / "anthropic",)

_FORBIDDEN_FOR_ANTHROPIC_ADAPTER = (
    # The official Anthropic SDK (and httpx, which it uses for timeout
    # configuration) are legitimately required here as of Milestone 17
    # - this is the *one* place in the codebase allowed to import them
    # for the new, governed invocation path (see
    # test_anthropic_sdk_is_confined_to_the_anthropic_adapter_package
    # below for the boundary that actually matters: nothing *outside*
    # this package may import them). No other provider SDK, and no
    # SQLAlchemy, is ever legitimate here.
    "openai",
    "sqlalchemy",
    # Knowledge graph / retrieval / canonicalization internals.
    "app.domain.project_knowledge_graph",
    "app.domain.graph_query",
    "app.domain.graph_builder",
    "app.domain.canonicalization",
    "app.domain.engineering_index",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.infrastructure.project_knowledge_graph",
    "app.infrastructure.graph_query",
    "app.infrastructure.canonicalization",
    "app.infrastructure.engineering_index",
    # Engineering domain services / persistence repositories / HTTP
    # routers of any kind - the adapter is a pure translation module.
    "app.services.graph_query_service",
    "app.services.structured_retrieval_service",
    "app.services.context_builder_service",
    "app.services.prompt_builder_service",
    "app.services.knowledge_graph",
    "app.routers",
    "app.models",
)


def test_anthropic_adapter_does_not_import_forbidden_modules() -> None:
    offenders = [
        f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
        for path in _files_under(*_ANTHROPIC_INFRA_SURFACE)
        for module in _imported_module_names(path)
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in _FORBIDDEN_FOR_ANTHROPIC_ADAPTER
        )
    ]

    assert offenders == []


def test_anthropic_sdk_is_confined_to_the_anthropic_adapter_package() -> None:
    """
    The Anthropic SDK (Milestone 17) may be imported in exactly two
    places: ``app/infrastructure/llm/anthropic/**`` (the new, governed
    invocation path this milestone builds) and the pre-existing,
    isolated legacy ``app/services/ai/**`` path
    (``claude_provider.py``, ADR-0009) - explicitly out of this
    milestone's scope to touch or route new behavior through (see
    ADR-0014's Legacy Isolation section). This test scans *every*
    other Python file in the application (domain, application layer,
    every other infrastructure package, other services, routers,
    schemas) and asserts none of them import ``anthropic`` - the
    codified form of "Anthropic is an adapter, never a domain
    dependency," checked positively (confined to these two known
    locations) rather than only negatively (forbidden elsewhere, which
    the other tests in this file already check piecemeal for the new
    path specifically).
    """

    exempt_files = set(_files_under(*_ANTHROPIC_INFRA_SURFACE)) | set(
        _files_under(APP_ROOT / "services" / "ai")
    )

    offenders = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _python_files(APP_ROOT)
        if path not in exempt_files
        and any(
            module == "anthropic" or module.startswith("anthropic.")
            for module in _imported_module_names(path)
        )
    ]

    assert offenders == []


# --- The fake test adapter never accidentally depends on a provider -----

_FAKE_ADAPTER_SURFACE = (APP_ROOT / "infrastructure" / "llm" / "base",)


def test_fake_adapter_has_no_provider_or_network_dependency() -> None:
    offenders = [
        f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
        for path in _files_under(*_FAKE_ADAPTER_SURFACE)
        for module in _imported_module_names(path)
        if any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for forbidden in ("anthropic", "openai", "requests", "httpx", "sqlalchemy")
        )
    ]

    assert offenders == []
