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
    # Engineering Response (Milestone 18) consumes Prompt Builder's own
    # output type (PromptPackage) as its shared, stable input vocabulary
    # - the same pattern one level further downstream - and Context
    # Builder's ContextPackage directly (for coverage/retrieval-summary
    # fields PromptPackage does not itself expose as structured data).
    # It also reads structured_retrieval's own vocabulary transitively,
    # the same "shared, stable type reused across contexts" chain
    # prompt_builder already established. It never imports graph_query
    # or graph_builder directly. Critically, it never imports
    # app.application.** (LLMResponseEnvelope, an application-layer
    # type) either - see the dedicated boundary test below, which is
    # this milestone's own new architectural guarantee.
    "engineering_response": frozenset(
        {"project", "context_builder", "prompt_builder", "structured_retrieval"}
    ),
    # Engineering Session (Milestone 19) consumes Engineering Response's
    # own output type (EngineeringResponse) as its shared, stable
    # vocabulary - it owns a tuple of them directly. It depends on
    # nothing else: no Context Builder, Prompt Builder, Structured
    # Retrieval, Graph Query, or Graph Builder import of its own - it
    # never constructs a new KnowledgeCandidate/ContextPackage/
    # PromptPackage, only holds references to EngineeringResponse
    # objects a caller already built. "Project identity" is carried as
    # a plain `project_id: int`, the same convention every context in
    # this pipeline already uses - no import of `app.domain.project`
    # is needed or present.
    "engineering_session": frozenset({"engineering_response"}),
    # Conversation (Milestone 20) depends on exactly two other domain
    # contexts: engineering_session (to reference its owning session by
    # EngineeringSessionId - never embedding the session itself) and
    # engineering_response (a ConversationTurn references
    # EngineeringResponse objects directly, never copies them - allowed
    # because Conversation may depend on the Engineering Response
    # domain contract directly, unlike Engineering Response's own
    # relationship to the application-layer LLMResponseEnvelope). No
    # Prompt Builder, Context Builder, Structured Retrieval, Graph
    # Query, or Graph Builder import of its own.
    "conversation": frozenset({"engineering_session", "engineering_response"}),
    # Working Memory (Milestone 21) depends on exactly the same two
    # domain contexts Conversation does, plus Conversation itself:
    # engineering_session (to validate its EngineeringSessionId echo),
    # engineering_response (entries reference EngineeringResponse
    # objects directly, never copied), and conversation (its own
    # primary input - Turns/Messages are read structurally, never
    # reinterpreted). No Prompt Builder, Context Builder, Structured
    # Retrieval, Graph Query, or Graph Builder import of its own.
    "working_memory": frozenset(
        {"conversation", "engineering_session", "engineering_response"}
    ),
    # Engineering Request Classification (Milestone 22, package named
    # `engineering_intent` for roadmap continuity) depends on NO other
    # domain bounded context at all - the smallest dependency surface
    # in the entire pipeline. Its classification input carries plain
    # identifiers and already-extracted structural Working Memory
    # signals (two booleans/counts), never a Conversation, WorkingMemory,
    # or EngineeringResponse object, so it needs no import of any of
    # them (see ADR-0019).
    "engineering_intent": frozenset(),
    # The Engineering Engine (Milestone 23A) is an application
    # coordination capability whose *domain* portion holds only
    # immutable planning and execution-result models. It reaches into
    # exactly two other contexts: engineering_intent (the intent type it
    # selects a workflow for) and engineering_response (the result it
    # carries). It deliberately depends on no Conversation, Working
    # Memory, Engineering Session, Structured Retrieval, Context
    # Builder, or Prompt Builder aggregate - see ADR-0020 and the
    # dedicated tests/architecture/test_engineering_engine_boundaries.py.
    "engineering_engine": frozenset(
        {"engineering_intent", "engineering_response"}
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


# --- Engineering Response boundaries (Milestone 18) ---------------------

# Unlike every other file in this section, app/services/engineering_response_service.py
# is deliberately EXCLUDED from the domain-purity surface below - it is
# the one seam allowed to import app.application.** (to translate
# LLMResponseEnvelope into the domain's own restatement); see
# ADR-0015. Only app/domain/engineering_response/** and the router are
# held to "never touches a provider SDK, runtime, or application-layer
# type" here.
_ENGINEERING_RESPONSE_DOMAIN_SURFACE = (
    DOMAIN_ROOT / "engineering_response",
    APP_ROOT / "routers" / "engineering_response.py",
)

# Engineering Response must never perform I/O, query the graph,
# re-derive retrieval/context/prompt assembly, or invoke a provider
# itself - it consumes an already-built ContextPackage, PromptPackage,
# and (via its own domain-owned restatement) LLMResponseEnvelope only.
# No SQLAlchemy, no write or read graph port, no legacy Knowledge Graph
# path, no Proposed Claims/Review Workflow, no Structured
# Retrieval/Context Builder/Prompt Builder *service or router* (their
# domain models are the one allowed, shared-vocabulary exception,
# enforced separately by ALLOWED_DOMAIN_DEPENDENCIES above), and -
# critically, this milestone's own new guarantee - no
# app.application.** of any kind (LLMResponseEnvelope and every other
# application-layer type), no provider SDK, and no LLM Invocation
# Runtime module.
_FORBIDDEN_FOR_ENGINEERING_RESPONSE = (
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
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.application",
    "app.infrastructure.llm",
    "app.services.llm_runtime",
    "app.services.engineering_response_service",
)


def test_engineering_response_domain_does_not_import_forbidden_modules() -> (
    None
):
    offenders: list[str] = []

    for path in _files_under(*_ENGINEERING_RESPONSE_DOMAIN_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_ENGINEERING_RESPONSE
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# No LLM provider SDK, vector search, embedding, or external AI SDK may
# appear anywhere in this bounded context - Engineering Response
# performs no AI usage of its own; it normalizes an already-produced
# LLMResponseEnvelope only (Milestone 18's own explicit non-goal: no
# provider adapters, no new invocation of any kind).
_FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES = (
    "anthropic",
    "openai",
    "app.services.ai",
    "ollama",
    "azure",
)


def test_engineering_response_surface_has_no_ai_or_provider_dependency() -> (
    None
):
    offenders: list[str] = []

    for path in _files_under(*_ENGINEERING_RESPONSE_DOMAIN_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_engineering_response_domain_never_imports_the_application_layer() -> (
    None
):
    """The dedicated, explicit form of this milestone's own architectural
    guarantee: app/domain/engineering_response/** never imports
    app.application.** (LLMResponseEnvelope or any other
    application-layer type) - the translation happens exactly once, in
    app/services/engineering_response_service.py, never in the domain
    itself (see ADR-0015)."""

    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "engineering_response"):
        imported = _imported_module_names(path)

        for module in imported:
            if module == "app.application" or module.startswith(
                "app.application."
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Engineering Session boundaries (Milestone 19) ----------------------

_ENGINEERING_SESSION_SURFACE = (
    DOMAIN_ROOT / "engineering_session",
    APP_ROOT / "services" / "engineering_session_service.py",
    APP_ROOT / "routers" / "engineering_session.py",
)

# Engineering Session must never perform I/O, query the graph, invoke a
# provider, or re-derive retrieval/context/prompt assembly - it owns
# already-built EngineeringResponse objects only. No SQLAlchemy, no
# graph ports, no legacy Knowledge Graph path, no Proposed Claims/
# Review Workflow, no Structured Retrieval/Context Builder/Prompt
# Builder/Engineering Response *service or router* (their domain models
# are the one allowed, shared-vocabulary exception, enforced separately
# by ALLOWED_DOMAIN_DEPENDENCIES above), no app.application.** of any
# kind, no provider SDK, and no LLM Invocation Runtime module - unlike
# Engineering Response, Engineering Session has no application-layer
# input at all to translate, so it needs no exception for its own
# service module either.
_FORBIDDEN_FOR_ENGINEERING_SESSION = (
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
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.services.engineering_response_service",
    "app.routers.engineering_response",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.application",
    "app.infrastructure.llm",
    "app.services.llm_runtime",
)


def test_engineering_session_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_ENGINEERING_SESSION_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_ENGINEERING_SESSION
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_engineering_session_surface_has_no_ai_or_provider_dependency() -> (
    None
):
    offenders: list[str] = []

    for path in _files_under(*_ENGINEERING_SESSION_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_engineering_session_domain_never_imports_the_application_layer() -> (
    None
):
    """Engineering Session has no application-layer input at all (unlike
    Engineering Response, which translates LLMResponseEnvelope) - so
    app/domain/engineering_session/** never imports app.application.**,
    with no exception anywhere, not even in its own service module."""

    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "engineering_session"):
        imported = _imported_module_names(path)

        for module in imported:
            if module == "app.application" or module.startswith(
                "app.application."
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Conversation boundaries (Milestone 20) ------------------------------

_CONVERSATION_SURFACE = (
    DOMAIN_ROOT / "conversation",
    APP_ROOT / "services" / "conversation_service.py",
    APP_ROOT / "routers" / "conversation.py",
)

# Conversation must never perform I/O, query the graph, invoke a
# provider, or re-derive retrieval/context/prompt assembly - it
# references EngineeringSession/EngineeringResponse only. No SQLAlchemy,
# no graph ports, no legacy Knowledge Graph path, no Proposed Claims/
# Review Workflow, no Structured Retrieval/Context Builder/Prompt
# Builder *service or router* (their domain models are not even part of
# Conversation's own allowed dependency set - see
# ALLOWED_DOMAIN_DEPENDENCIES above), no app.application.** of any
# kind, no provider SDK, and no LLM Invocation Runtime module -
# Conversation has no application-layer input at all, so (like
# Engineering Session) it needs no exception anywhere, not even in its
# own service module.
_FORBIDDEN_FOR_CONVERSATION = (
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
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.services.engineering_response_service",
    "app.routers.engineering_response",
    "app.services.engineering_session_service",
    "app.routers.engineering_session",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.application",
    "app.infrastructure.llm",
    "app.services.llm_runtime",
)


def test_conversation_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_CONVERSATION_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_CONVERSATION
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_conversation_surface_has_no_ai_or_provider_dependency() -> None:
    offenders: list[str] = []

    for path in _files_under(*_CONVERSATION_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_conversation_domain_never_imports_the_application_layer() -> None:
    """Conversation has no application-layer input at all - so
    app/domain/conversation/** never imports app.application.**, with
    no exception anywhere, not even in its own service module (the same
    guarantee Engineering Session's own equivalent test establishes)."""

    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "conversation"):
        imported = _imported_module_names(path)

        for module in imported:
            if module == "app.application" or module.startswith(
                "app.application."
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Working Memory boundaries (Milestone 21) ----------------------------

_WORKING_MEMORY_SURFACE = (
    DOMAIN_ROOT / "working_memory",
    APP_ROOT / "services" / "working_memory_service.py",
    APP_ROOT / "routers" / "working_memory.py",
)

# Working Memory must never perform I/O, query the graph, invoke a
# provider, or re-derive retrieval/context/prompt assembly - it reads
# Conversation/EngineeringSession/EngineeringResponse structurally only.
# No SQLAlchemy, no graph ports, no legacy Knowledge Graph path, no
# Proposed Claims/Review Workflow, no Structured Retrieval/Context
# Builder/Prompt Builder *service or router*, no app.application.** of
# any kind, no provider SDK, and no LLM Invocation Runtime module -
# Working Memory has no application-layer input at all, so (like
# Engineering Session and Conversation) it needs no exception anywhere,
# not even in its own service module.
_FORBIDDEN_FOR_WORKING_MEMORY = (
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
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.services.engineering_response_service",
    "app.routers.engineering_response",
    "app.services.engineering_session_service",
    "app.routers.engineering_session",
    "app.services.conversation_service",
    "app.routers.conversation",
    "app.models.knowledge_graph",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.application",
    "app.infrastructure.llm",
    "app.services.llm_runtime",
)


def test_working_memory_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_WORKING_MEMORY_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_WORKING_MEMORY
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_working_memory_surface_has_no_ai_or_provider_dependency() -> None:
    offenders: list[str] = []

    for path in _files_under(*_WORKING_MEMORY_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_working_memory_domain_never_imports_the_application_layer() -> None:
    """Working Memory has no application-layer input at all - so
    app/domain/working_memory/** never imports app.application.**, with
    no exception anywhere, not even in its own service module (the same
    guarantee Engineering Session's and Conversation's own equivalent
    tests establish)."""

    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "working_memory"):
        imported = _imported_module_names(path)

        for module in imported:
            if module == "app.application" or module.startswith(
                "app.application."
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


# --- Engineering Request Classification boundaries (Milestone 22) --------

_ENGINEERING_INTENT_SURFACE = (
    DOMAIN_ROOT / "engineering_intent",
    APP_ROOT / "services" / "engineering_intent_service.py",
    APP_ROOT / "routers" / "engineering_intent.py",
)

# Engineering Request Classification is a pure, deterministic rule
# engine. It must never perform I/O, query the graph, invoke a
# provider, or reach any other bounded context - its classification
# input carries plain identifiers and already-extracted structural
# signals only. Beyond the usual forbidden list, this milestone
# explicitly forbids Prompt Builder, Context Builder, Structured
# Retrieval, Graph Query, the LLM Runtime, provider SDKs, and the
# application layer - and, uniquely, also forbids the *domain* modules
# of Conversation/Working Memory/Engineering Response/Engineering
# Session, since this context depends on no other bounded context at
# all.
_FORBIDDEN_FOR_ENGINEERING_INTENT = (
    "sqlalchemy",
    "app.domain.project_knowledge_graph",
    "app.domain.graph_query",
    "app.domain.graph_builder",
    "app.domain.structured_retrieval",
    "app.domain.context_builder",
    "app.domain.prompt_builder",
    "app.domain.canonicalization",
    "app.domain.engineering_index",
    "app.domain.proposed_claims",
    "app.domain.review_workflow",
    "app.infrastructure",
    "app.models",
    "app.application",
    "app.services.graph_query_service",
    "app.routers.graph_query",
    "app.services.structured_retrieval_service",
    "app.routers.structured_retrieval",
    "app.services.context_builder_service",
    "app.routers.context_builder",
    "app.services.prompt_builder_service",
    "app.routers.prompt_builder",
    "app.services.engineering_response_service",
    "app.routers.engineering_response",
    "app.services.engineering_session_service",
    "app.routers.engineering_session",
    "app.services.conversation_service",
    "app.routers.conversation",
    "app.services.working_memory_service",
    "app.routers.working_memory",
    "app.services.knowledge_graph",
    "app.routers.knowledge_graph",
    "app.schemas.knowledge_graph",
)


def test_engineering_intent_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _files_under(*_ENGINEERING_INTENT_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in _FORBIDDEN_FOR_ENGINEERING_INTENT
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_engineering_intent_surface_has_no_ai_or_provider_dependency() -> None:
    """The codified form of ADR-0019's central claim: this is a
    deterministic rule engine, not an LLM classifier. No provider SDK,
    no embeddings library, no vector store, no external NLP service."""

    offenders: list[str] = []

    forbidden_prefixes = _FORBIDDEN_ENGINEERING_RESPONSE_AI_MODULE_PREFIXES + (
        "numpy",
        "scipy",
        "sklearn",
        "torch",
        "transformers",
        "sentence_transformers",
        "spacy",
        "nltk",
        "gensim",
        "faiss",
        "chromadb",
        "pinecone",
        "tiktoken",
    )

    for path in _files_under(*_ENGINEERING_INTENT_SURFACE):
        imported = _imported_module_names(path)

        for module in imported:
            if any(
                module == forbidden or module.startswith(f"{forbidden}.")
                for forbidden in forbidden_prefixes
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []


def test_engineering_intent_domain_imports_no_other_bounded_context() -> None:
    """This context's own strongest architectural guarantee: it depends
    on no other `app/domain/**` bounded context at all - the smallest
    dependency surface in the pipeline (see ADR-0019)."""

    offenders: list[str] = []

    for path in _python_files(DOMAIN_ROOT / "engineering_intent"):
        for module in _imported_module_names(path):
            other = _domain_context_of(module)
            if other is not None and other != "engineering_intent":
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports "
                    f"'{module}'"
                )

    assert offenders == []
