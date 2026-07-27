"""
Architecture tests for the Engineering Engine (Milestone 23A).

Two distinct guarantees are enforced here:

1. **Layering** - the engine *domain* holds only immutable planning and
   execution-result models; it imports no router, schema, FastAPI,
   persistence adapter, provider SDK, concrete runtime, or application
   service. The engine *application* layer may adapt to existing
   services, but still never touches a provider SDK directly.

2. **No core intent switching** - workflow selection is registry-driven.
   The engine core must not branch over ``EngineeringIntentType``
   values. This is tested by parsing the actual AST for comparisons
   against intent-type members, not by grepping for the word "if"
   (see ADR-0020).
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

ENGINE_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_engine"
ENGINE_SERVICE_ROOT = APP_ROOT / "services" / "engineering_engine"
ENGINE_ROUTER = APP_ROOT / "routers" / "engineering_engine.py"


def _python_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.py") if "__pycache__" not in p.parts
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


# --- 1. Engine domain layering -------------------------------------------

# The engine domain may depend only on stable domain contracts it
# genuinely needs (EngineeringIntentType, EngineeringResponse) plus the
# standard library. Everything below is forbidden outright.
_FORBIDDEN_FOR_ENGINE_DOMAIN = (
    "fastapi",
    "pydantic",
    "sqlalchemy",
    "anthropic",
    "openai",
    "httpx",
    "app.routers",
    "app.schemas",
    "app.models",
    "app.database",
    "app.infrastructure",
    "app.services",
    "app.application",
)


def test_engine_domain_does_not_import_forbidden_modules() -> None:
    offenders: list[str] = []

    for path in _python_files(ENGINE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, _FORBIDDEN_FOR_ENGINE_DOMAIN):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_engine_domain_depends_only_on_permitted_bounded_contexts() -> None:
    """The engine domain reaches into exactly two other domain contexts -
    ``engineering_intent`` (for the intent type it selects on) and
    ``engineering_response`` (for the result it carries) - and no
    others. In particular it never depends on Conversation, Working
    Memory, Engineering Session, Structured Retrieval, Context Builder,
    or Prompt Builder aggregates."""

    permitted = {"engineering_engine", "engineering_intent", "engineering_response"}
    offenders: list[str] = []

    for path in _python_files(ENGINE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if not module.startswith("app.domain."):
                continue
            parts = module.split(".")
            if len(parts) < 3:
                continue
            if parts[2] not in permitted:
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 2. Engine application layer -------------------------------------------

# The application layer may adapt to existing services, but must still
# never touch a provider SDK, an HTTP client, or a router/schema. It
# reaches the LLM only through the existing provider-neutral runtime
# contract.
_FORBIDDEN_FOR_ENGINE_APPLICATION = (
    "anthropic",
    "openai",
    "httpx",
    "requests",
    "app.routers",
    "app.schemas",
    "app.infrastructure.llm.anthropic",
)


def test_engine_application_layer_has_no_provider_dependency() -> None:
    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, _FORBIDDEN_FOR_ENGINE_APPLICATION):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_engine_reaches_the_llm_only_through_the_neutral_runtime() -> None:
    """The only LLM entry point anywhere in the engine is
    ``invoke_llm`` - the existing provider-neutral runtime contract."""

    runtime_importers: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        modules = _imported_module_names(path)
        for module in modules:
            if module.startswith("app.application.services.llm_"):
                runtime_importers.append(module)

    assert set(runtime_importers) <= {
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_provider_registry",
    }


# --- 3. No core intent switching ---------------------------------------------

# The "engine core": everything that coordinates execution, excluding
# the composition root (which legitimately names the one registered
# workflow) and the workflow definition module (which legitimately names
# the intent type it supports).
_ENGINE_CORE_FILES = (
    ENGINE_SERVICE_ROOT / "engineering_engine_service.py",
    ENGINE_SERVICE_ROOT / "plan_executor.py",
    ENGINE_SERVICE_ROOT / "step_handler_registry.py",
    ENGINE_SERVICE_ROOT / "execution_context.py",
    ENGINE_DOMAIN_ROOT / "workflow_planner.py",
    ENGINE_ROUTER,
)


def _intent_type_comparisons(path: Path) -> list[str]:
    """Every place the source compares something against an
    ``EngineeringIntentType`` member - the branching pattern this
    milestone forbids in the engine core."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []

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
                found.append(f"comparison at line {node.lineno}")
        elif isinstance(node, ast.Match):
            if _is_intent_member(node.subject):
                found.append(f"match statement at line {node.lineno}")

    return found


def test_engine_core_never_branches_over_intent_types() -> None:
    """
    Workflow selection is registry-driven: the engine core resolves a
    workflow through ``WorkflowRegistry`` and never contains
    ``if intent is KNOWLEDGE_QUERY ... elif intent is DOCUMENT_LOOKUP``.

    This is an AST check for comparisons/matches against
    ``EngineeringIntentType`` members - not a brittle search for the
    word "if".
    """

    offenders: list[str] = []

    for path in _ENGINE_CORE_FILES:
        for occurrence in _intent_type_comparisons(path):
            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)}: {occurrence}"
            )

    assert offenders == []


def test_the_intent_to_workflow_mapping_lives_in_the_registry() -> None:
    """The registry is the only engine module that stores an
    intent-type-keyed mapping."""

    registry_source = (
        ENGINE_SERVICE_ROOT / "workflow_registry.py"
    ).read_text(encoding="utf-8")

    assert "dict[EngineeringIntentType, WorkflowDefinition]" in registry_source
    assert "def select_workflow" in registry_source


def test_the_engine_core_service_does_not_import_concrete_workflows() -> None:
    """The core depends on the registry abstraction, not on concrete
    workflow definitions - which is what lets Milestone 23B add
    workflows without touching it."""

    modules = _imported_module_names(
        ENGINE_SERVICE_ROOT / "engineering_engine_service.py"
    )

    assert "app.domain.engineering_engine.workflow_definitions" not in modules
    assert (
        "app.services.engineering_engine.workflow_registry" in modules
    )
