"""
Lightweight, repository-native architecture tests (Milestone 12,
Workstream 5). Parses this project's own source files with Python's
standard-library ``ast`` module to check import statements - no
architecture-testing framework is introduced; a table plus an AST walk
is enough for the dependency rules this codebase actually needs
enforced.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"


def _imported_module_names(path: Path) -> set[str]:
    """Every dotted module name this file imports, from both `import x`
    and `from x import y` statements."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def _python_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
    )


# --- Domain layer purity ------------------------------------------------


def test_domain_layer_does_not_import_sqlalchemy() -> None:
    offenders = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _python_files(DOMAIN_ROOT)
        if any(
            module == "sqlalchemy" or module.startswith("sqlalchemy.")
            for module in _imported_module_names(path)
        )
    ]

    assert offenders == []


def test_domain_layer_does_not_import_persistence_models() -> None:
    offenders = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _python_files(DOMAIN_ROOT)
        if any(
            module == "app.models" or module.startswith("app.models.")
            for module in _imported_module_names(path)
        )
    ]

    assert offenders == []


# --- Bounded-context dependency direction -------------------------------

# The knowledge pipeline, in dependency order (Documents -> Engineering
# Index -> Proposed Claims -> Review Workflow -> Canonicalization ->
# Graph Builder -> Project Knowledge Graph -> Graph Query). Each entry
# lists the *other* app/domain/<context> packages that context's domain
# layer may import from - anything else is a forbidden (backward or
# sideways) dependency. "project" (Project Lifecycle) is a shared
# foundation every context may depend on.
ALLOWED_DOMAIN_DEPENDENCIES: dict[str, frozenset[str]] = {
    "project": frozenset(),
    "engineering_index": frozenset({"project"}),
    "proposed_claims": frozenset({"project", "engineering_index"}),
    "review_workflow": frozenset({"project", "proposed_claims"}),
    "canonicalization": frozenset(
        {"project", "proposed_claims", "review_workflow"}
    ),
    # "proposed_claims" here is not a layering violation: ClaimType is a
    # single shared vocabulary type defined in proposed_claims, carried
    # unchanged onto CanonicalFact.claim_type by canonicalization, and
    # inspected again by graph_builder to decide which GraphOperation
    # shape to emit - the same "shared, stable type reused across
    # contexts" pattern GraphEntityId/GraphRelationshipType already use
    # for graph_builder/project_knowledge_graph/graph_query. Proposed
    # Claims remains upstream of Graph Builder either way (via
    # Canonicalization), so this is not a backward dependency.
    "graph_builder": frozenset(
        {"project", "canonicalization", "proposed_claims"}
    ),
    "project_knowledge_graph": frozenset({"project", "graph_builder"}),
    # Graph Query reuses the shared GraphEntityId/GraphRelationshipType
    # vocabulary from Graph Builder - never Project Knowledge Graph's
    # GraphStore (see test_graph_query_never_imports_graph_store below).
    "graph_query": frozenset({"project", "graph_builder"}),
    # Structured Retrieval (Milestone 13) consumes Graph Query's own
    # read-model types (GraphNodeView/GraphRelationshipView) and the
    # same shared GraphEntityId/GraphRelationshipType vocabulary Graph
    # Query itself depends on - never GraphStore, never Proposed
    # Claims/Review Workflow directly (see the dedicated tests below).
    "structured_retrieval": frozenset({"project", "graph_builder", "graph_query"}),
    # Context Builder (Milestone 14) consumes Structured Retrieval's own
    # output types (KnowledgeCandidateCollection/KnowledgeCandidate) as
    # its shared, stable input vocabulary - the same "reuse the upstream
    # read-oriented type" pattern Structured Retrieval itself
    # established for Graph Query. Context Builder never imports
    # graph_query or graph_builder directly: it never constructs a new
    # GraphEntityId/GraphRelationshipType itself, only holds references
    # to whatever a KnowledgeCandidate already carries.
    "context_builder": frozenset({"project", "structured_retrieval"}),
    # Prompt Builder (Milestone 15) consumes Context Builder's own
    # output type (ContextPackage) as its shared, stable input
    # vocabulary - the same pattern one level further downstream. It
    # also reads structured_retrieval's own KnowledgeCandidate/
    # KnowledgeCandidateKind vocabulary directly (ContextPackage embeds
    # KnowledgeCandidate objects verbatim - the same transitive
    # "shared, stable type" reuse graph_query/structured_retrieval
    # already established), but never imports graph_query or
    # graph_builder directly: it never constructs a new
    # GraphEntityId/GraphRelationshipType itself, only reads fields off
    # objects the ContextPackage already carries.
    "prompt_builder": frozenset(
        {"project", "context_builder", "structured_retrieval"}
    ),
}

# Contexts outside app/domain/ontology - not part of the knowledge
# pipeline's dependency-order table, exempt from it.
_EXEMPT_DOMAIN_PACKAGES = frozenset({"ontology"})


def _domain_context_of(module: str) -> str | None:
    if not module.startswith("app.domain."):
        return None

    parts = module.split(".")

    if len(parts) < 3:
        return None

    return parts[2]


def test_bounded_context_domain_dependencies_follow_the_allowed_graph() -> (
    None
):
    violations: list[str] = []

    for context, allowed in ALLOWED_DOMAIN_DEPENDENCIES.items():
        context_root = DOMAIN_ROOT / context

        if not context_root.is_dir():
            continue

        for path in _python_files(context_root):
            for module in _imported_module_names(path):
                other = _domain_context_of(module)

                if other is None or other == context:
                    continue

                if other in _EXEMPT_DOMAIN_PACKAGES:
                    continue

                if other not in allowed:
                    violations.append(
                        f"{path.relative_to(APP_ROOT.parent)} "
                        f"(context '{context}') imports '{module}' "
                        f"(context '{other}'), which is not in its "
                        "allowed dependency set"
                    )

    assert violations == []


# --- Graph Query never imports GraphStore -------------------------------

_GRAPH_QUERY_SURFACE = (
    DOMAIN_ROOT / "graph_query",
    APP_ROOT / "infrastructure" / "graph_query",
    APP_ROOT / "services" / "graph_query_service.py",
    APP_ROOT / "routers" / "graph_query.py",
)

_FORBIDDEN_FOR_GRAPH_QUERY = (
    "app.domain.project_knowledge_graph.graph_store",
    "app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store",
)


def _files_under(*targets: Path) -> list[Path]:
    files: list[Path] = []

    for target in targets:
        if target.is_dir():
            files.extend(_python_files(target))
        elif target.is_file():
            files.append(target)

    return files


def test_graph_query_never_imports_graph_store() -> None:
    offenders = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _files_under(*_GRAPH_QUERY_SURFACE)
        if _imported_module_names(path) & set(_FORBIDDEN_FOR_GRAPH_QUERY)
    ]

    assert offenders == []


# --- The governed graph path never imports legacy graph code -----------

_GOVERNED_GRAPH_SURFACE = (
    DOMAIN_ROOT / "graph_builder",
    DOMAIN_ROOT / "project_knowledge_graph",
    DOMAIN_ROOT / "graph_query",
    APP_ROOT / "infrastructure" / "graph_builder",
    APP_ROOT / "infrastructure" / "project_knowledge_graph",
    APP_ROOT / "infrastructure" / "graph_query",
    APP_ROOT / "services" / "graph_builder_service.py",
    APP_ROOT / "services" / "graph_execution_service.py",
    APP_ROOT / "services" / "graph_query_service.py",
    APP_ROOT / "routers" / "graph_builder.py",
    APP_ROOT / "routers" / "project_knowledge_graph.py",
    APP_ROOT / "routers" / "graph_query.py",
)

_LEGACY_KNOWLEDGE_GRAPH_MODULES = (
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
)


def test_governed_graph_path_does_not_import_legacy_knowledge_graph_code() -> (
    None
):
    offenders = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _files_under(*_GOVERNED_GRAPH_SURFACE)
        if _imported_module_names(path)
        & set(_LEGACY_KNOWLEDGE_GRAPH_MODULES)
    ]

    assert offenders == []


# --- Structured Retrieval boundaries (Milestone 13) ---------------------

_STRUCTURED_RETRIEVAL_SURFACE = (
    DOMAIN_ROOT / "structured_retrieval",
    APP_ROOT / "services" / "structured_retrieval_service.py",
    APP_ROOT / "routers" / "structured_retrieval.py",
)

_FORBIDDEN_FOR_STRUCTURED_RETRIEVAL_DOMAIN = (
    "sqlalchemy",
    "app.domain.project_knowledge_graph.graph_store",
    "app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
)

# No LLM, vector search, embedding, or external AI SDK dependency may
# appear anywhere in this bounded context - Structured Retrieval is
# deterministic, structured-criteria retrieval only (Milestone 13's
# explicit non-goals).
_FORBIDDEN_AI_MODULE_PREFIXES = (
    "anthropic",
    "openai",
    "app.services.ai",
)


def test_structured_retrieval_domain_does_not_import_forbidden_modules() -> (
    None
):
    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "structured_retrieval"):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_STRUCTURED_RETRIEVAL_DOMAIN
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_structured_retrieval_surface_has_no_ai_or_vector_dependency() -> (
    None
):
    offenders: list[str] = []

    for path in _files_under(*_STRUCTURED_RETRIEVAL_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Context Builder boundaries (Milestone 14) --------------------------

_CONTEXT_BUILDER_SURFACE = (
    DOMAIN_ROOT / "context_builder",
    APP_ROOT / "services" / "context_builder_service.py",
    APP_ROOT / "routers" / "context_builder.py",
)

# Context Builder must never perform I/O, query the graph, or re-derive
# retrieval - it consumes an already-built KnowledgeCandidateCollection
# only. No SQLAlchemy, no write or read graph port, no legacy Knowledge
# Graph path, no Proposed Claims/Review Workflow, and - critically - no
# Graph Query and no Structured Retrieval *service or router* (its
# domain *models* are the one allowed, shared-vocabulary exception,
# enforced separately by ALLOWED_DOMAIN_DEPENDENCIES above).
_FORBIDDEN_FOR_CONTEXT_BUILDER = (
    "sqlalchemy",
    "app.domain.project_knowledge_graph.graph_store",
    "app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store",
    "app.domain.graph_query.graph_query_repository",
    "app.infrastructure.graph_query",
    "app.services.graph_query_service",
    "app.routers.graph_query",
    "app.services.structured_retrieval_service",
    "app.routers.structured_retrieval",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
)


def test_context_builder_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_CONTEXT_BUILDER_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_CONTEXT_BUILDER
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_context_builder_surface_has_no_ai_or_vector_dependency() -> None:
    offenders: list[str] = []

    for path in _files_under(*_CONTEXT_BUILDER_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Prompt Builder boundaries (Milestone 15) ---------------------------

_PROMPT_BUILDER_SURFACE = (
    DOMAIN_ROOT / "prompt_builder",
    APP_ROOT / "services" / "prompt_builder_service.py",
    APP_ROOT / "routers" / "prompt_builder.py",
)

# Prompt Builder must never perform I/O, query the graph, re-derive
# retrieval, or re-derive context assembly - it consumes an
# already-built ContextPackage only, and composes structured sections
# from it. No SQLAlchemy, no write or read graph port, no legacy
# Knowledge Graph path, no Proposed Claims/Review Workflow, no
# Structured Retrieval or Context Builder *service or router* (their
# domain models are the one allowed, shared-vocabulary exception,
# enforced separately by ALLOWED_DOMAIN_DEPENDENCIES above), and no
# provider SDK of any kind.
_FORBIDDEN_FOR_PROMPT_BUILDER = (
    "sqlalchemy",
    "app.domain.project_knowledge_graph.graph_store",
    "app.infrastructure.project_knowledge_graph.sqlalchemy_graph_store",
    "app.domain.graph_query.graph_query_repository",
    "app.infrastructure.graph_query",
    "app.services.graph_query_service",
    "app.routers.graph_query",
    "app.services.structured_retrieval_service",
    "app.routers.structured_retrieval",
    "app.services.context_builder_service",
    "app.routers.context_builder",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
)


def test_prompt_builder_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_PROMPT_BUILDER_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_PROMPT_BUILDER
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# No LLM, vector search, embedding, or external AI SDK/provider
# dependency may appear anywhere in this bounded context - Prompt
# Builder assembles a provider-independent PromptPackage only
# (Milestone 15's explicit non-goals: no OpenAI, Anthropic, Ollama,
# Azure OpenAI, LLM invocation, or provider adapters).
_FORBIDDEN_PROVIDER_MODULE_PREFIXES = _FORBIDDEN_AI_MODULE_PREFIXES + (
    "ollama",
    "azure",
)


def test_prompt_builder_surface_has_no_ai_or_provider_dependency() -> None:
    offenders: list[str] = []

    for path in _files_under(*_PROMPT_BUILDER_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_PROVIDER_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []
