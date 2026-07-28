"""
Architecture tests for the Classification-to-Retrieval Bridge (Milestone
23B.3).

Three guarantees are enforced here, all of them things the bridge could
plausibly grow into and must not:

1. **It cannot reach a model.** No provider SDK, no LLM Runtime, no
   Prompt Builder - the mapping is deterministic by construction, not by
   good intentions.
2. **It cannot reach the engine.** The bridge knows nothing of workflows,
   plans, steps or handlers; it produces criteria and stops. The engine
   in turn knows nothing of the bridge, so neither can start driving the
   other.
3. **It executes nothing.** No repository, no session, no adapter - it
   maps a classified request to criteria and never runs a query.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

BRIDGE_DOMAIN_ROOT = DOMAIN_ROOT / "retrieval_bridge"
BRIDGE_SERVICE = (
    APP_ROOT / "services" / "engineering_request_preparation_service.py"
)
BRIDGE_ROUTER = APP_ROOT / "routers" / "engineering_request_preparation.py"
ENGINE_SERVICE_ROOT = APP_ROOT / "services" / "engineering_engine"
ENGINE_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_engine"


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def _violates(module: str, forbidden: tuple[str, ...]) -> bool:
    return any(
        module == entry or module.startswith(f"{entry}.")
        for entry in forbidden
    )


# --- 1. The bridge cannot reach a model --------------------------------------

# Everything that would make the mapping non-deterministic, plus the
# whole prompt/runtime surface. Milestone 23B.3's central claim is that
# this mapping is reproducible; an import from any of these would make
# that claim unverifiable.
_FORBIDDEN_FOR_BRIDGE = (
    "anthropic",
    "openai",
    "ollama",
    "azure",
    "httpx",
    "requests",
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
    "sqlalchemy",
    "fastapi",
    "app.services.ai",
    "app.domain.prompt_builder",
    "app.domain.context_builder",
    "app.services.prompt_builder_service",
    "app.services.context_builder_service",
    "app.infrastructure",
    "app.models",
    "app.database",
    "app.routers",
    "app.schemas",
    "app.application",
)


def test_the_bridge_domain_cannot_reach_a_provider_prompt_or_runtime() -> None:
    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, _FORBIDDEN_FOR_BRIDGE):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_bridge_service_reaches_no_provider_or_prompt_builder() -> None:
    """The application seam may orchestrate, but it still composes only
    classification and mapping - never a prompt, a runtime, or a
    provider."""

    forbidden = (
        "anthropic",
        "openai",
        "app.services.ai",
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.infrastructure.llm",
    )
    offenders = [
        module
        for module in _imported_module_names(BRIDGE_SERVICE)
        if _violates(module, forbidden)
    ]

    assert offenders == []


# --- 2. The bridge cannot reach the engine, and vice versa -------------------


def test_the_bridge_domain_never_imports_engine_internals() -> None:
    """The bridge produces retrieval criteria. It knows nothing of
    workflows, plans, steps, handlers or registries - so it cannot start
    making workflow decisions that belong to the registry."""

    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
    )
    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_bridge_never_imports_a_workflow_handler_module() -> None:
    forbidden = (
        "app.services.engineering_engine.step_handlers",
        "app.services.engineering_engine.document_lookup_step_handlers",
        "app.services.engineering_engine.step_handler",
        "app.domain.engineering_engine.workflow_definitions",
    )
    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT) + [BRIDGE_SERVICE]:
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_engine_never_imports_the_bridge() -> None:
    """The dependency runs one way only. An engine that could call the
    bridge would be an engine that parses natural language."""

    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        for module in _imported_module_names(path):
            if _violates(
                module,
                (
                    "app.domain.retrieval_bridge",
                    "app.services.engineering_request_preparation_service",
                ),
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_engine_never_imports_the_classifier_service_or_normalizer() -> (
    None
):
    """The engine receives an already-classified intent type as data. It
    must not be able to classify or normalize request text itself, which
    is what "the engine does not parse natural language" means
    concretely."""

    forbidden = (
        "app.services.engineering_intent_service",
        "app.domain.engineering_intent.engineering_intent_classifier",
        "app.domain.engineering_intent.engineering_intent_normalization",
        "app.domain.engineering_intent.engineering_intent_rules",
    )
    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 3. The bridge executes nothing ------------------------------------------


def test_the_bridge_executes_no_retrieval() -> None:
    """It maps criteria; running them is Structured Retrieval's job,
    reached only through the engine's own step handler."""

    forbidden = (
        "app.services.structured_retrieval_service",
        "app.services.document_retrieval_service",
        "app.domain.graph_query",
        "app.domain.structured_retrieval.structured_retrieval_factory",
        "app.domain.engineering_index.engineering_index_repository",
    )
    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT) + [BRIDGE_SERVICE]:
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_bridge_domain_holds_no_router_or_schema_dependency() -> None:
    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, ("app.routers", "app.schemas")):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 4. The mapping table is data, not a branch chain ------------------------


def test_the_intent_to_retrieval_mapping_lives_in_an_immutable_table() -> None:
    """The milestone's own requirement: an enumerable, reviewable,
    versionable registry rather than a central if/else chain."""

    source = (
        BRIDGE_DOMAIN_ROOT / "retrieval_bridge_policy.py"
    ).read_text(encoding="utf-8")

    assert (
        "RETRIEVAL_POLICY_BY_INTENT: dict[\n    EngineeringIntentType, "
        "IntentRetrievalPolicy\n]" in source
    )
    assert "BRIDGE_POLICY_VERSION" in source


def test_the_bridge_never_branches_over_intent_types() -> None:
    """Intent-specific behaviour is table data, exactly as the engine's
    own workflow selection is registry data - checked at AST level, not by
    grepping for the word "if"."""

    offenders: list[str] = []

    for path in _python_files(BRIDGE_DOMAIN_ROOT):
        if path.name == "retrieval_bridge_policy.py":
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        def _is_intent_member(node: ast.AST) -> bool:
            return (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "EngineeringIntentType"
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                if any(_is_intent_member(operand) for operand in operands):
                    offenders.append(
                        f"{path.relative_to(APP_ROOT.parent)}: comparison at "
                        f"line {node.lineno}"
                    )
            elif isinstance(node, ast.Match) and _is_intent_member(
                node.subject
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)}: match at line "
                    f"{node.lineno}"
                )

    assert offenders == []
