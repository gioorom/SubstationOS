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
import re
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


# --- 4. The engine core is closed for modification (Milestone 23B.1) --------
#
# Milestone 23A's claim was that a second workflow could be added without
# touching the engine core. Milestone 23B.1 added one; these tests are the
# standing, executable form of that claim, so a future workflow cannot
# quietly erode it.

# The modules that select, plan, validate and execute. A workflow-specific
# name appearing in any of them is exactly the coupling the registry
# exists to prevent.
_ENGINE_CORE_DECISION_FILES = (
    ENGINE_SERVICE_ROOT / "engineering_engine_service.py",
    ENGINE_SERVICE_ROOT / "plan_executor.py",
    ENGINE_SERVICE_ROOT / "workflow_registry.py",
    ENGINE_SERVICE_ROOT / "step_handler_registry.py",
    ENGINE_DOMAIN_ROOT / "workflow_planner.py",
    ENGINE_DOMAIN_ROOT / "engineering_engine_validation.py",
)


def test_the_engine_core_imports_no_workflow_specific_module() -> None:
    """No core module imports a workflow definition, a concrete handler
    module, or any bounded context a single workflow happens to need
    (Structured Retrieval, Document Retrieval, Context Builder, Prompt
    Builder, the LLM runtime)."""

    forbidden = (
        "app.domain.engineering_engine.workflow_definitions",
        "app.services.engineering_engine.step_handlers",
        "app.services.engineering_engine.document_lookup_step_handlers",
        "app.domain.engineering_index",
        "app.domain.structured_retrieval",
        "app.domain.context_builder",
        "app.domain.prompt_builder",
        "app.services.document_retrieval_service",
        "app.services.structured_retrieval_service",
        "app.services.engineering_response_service",
        "app.application.services.llm_invocation_service",
    )
    offenders: list[str] = []

    for path in _ENGINE_CORE_DECISION_FILES:
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_no_engine_core_module_names_a_specific_workflow() -> None:
    """A plain source-text check, deliberately: the core must not mention
    ``knowledge_query``, ``document_lookup``, or any other workflow by
    name - not in a branch, not in a message, not in a comment that would
    go stale."""

    workflow_names = (
        "knowledge_query",
        "knowledge-query",
        "document_lookup",
        "document-lookup",
        "engineering_explanation",
        "engineering-explanation",
    )
    offenders: list[str] = []

    for path in _ENGINE_CORE_DECISION_FILES:
        source = path.read_text(encoding="utf-8")
        for name in workflow_names:
            if name in source:
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} mentions '{name}'"
                )

    assert offenders == []


def test_the_engine_core_depends_only_on_the_handler_contract() -> None:
    """The executor and the handler registry import ``step_handler`` (the
    protocol, the base class and the typed error) and never a concrete
    handler module - which is what lets a workflow's handlers be written
    without the core changing."""

    for path in (
        ENGINE_SERVICE_ROOT / "plan_executor.py",
        ENGINE_SERVICE_ROOT / "step_handler_registry.py",
    ):
        modules = _imported_module_names(path)

        assert "app.services.engineering_engine.step_handler" in modules
        assert "app.services.engineering_engine.step_handlers" not in modules


def test_the_composition_root_is_the_only_place_that_registers_workflows() -> (
    None
):
    """Every ``register`` of a workflow lives in ``composition.py``. If a
    second place could register one, "the registry is the only mapping"
    would stop being true."""

    registering: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT):
        if path.name in ("composition.py", "workflow_registry.py"):
            continue
        if "registry.register(" in path.read_text(encoding="utf-8"):
            registering.append(str(path.relative_to(APP_ROOT.parent)))

    assert registering == []


def test_the_document_lookup_workflow_cannot_reach_an_llm() -> None:
    """The first non-LLM workflow, enforced rather than asserted in prose:
    its handler module imports no provider SDK, no provider registry, no
    runtime configuration, and no invocation service."""

    forbidden = (
        "anthropic",
        "openai",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_provider_registry",
        "app.application.models.llm_invocation",
        "app.infrastructure.llm",
        "app.domain.prompt_builder",
        "app.domain.context_builder",
        "app.services.prompt_builder_service",
        "app.services.context_builder_service",
    )
    handlers = (
        ENGINE_SERVICE_ROOT / "document_lookup_step_handlers.py"
    )
    offenders = [
        module
        for module in _imported_module_names(handlers)
        if _violates(module, forbidden)
    ]

    assert offenders == []


def test_no_handler_derives_its_behaviour_from_an_intent_or_workflow_type() -> (
    None
):
    """
    Handlers adapt to services; they must not branch over which workflow
    is running. A workflow that needs a step to behave differently says
    so declaratively in the composition root (as
    ENGINEERING_EXPLANATION does for its Prompt Builder objective) - it
    never reintroduces the intent switch the registry exists to remove.
    """

    handler_modules = (
        ENGINE_SERVICE_ROOT / "step_handlers.py",
        ENGINE_SERVICE_ROOT / "document_lookup_step_handlers.py",
    )
    offenders: list[str] = []

    for path in handler_modules:
        modules = _imported_module_names(path)
        if "app.domain.engineering_intent.engineering_intent_models" in modules:
            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports the intent type"
            )
        for occurrence in _intent_type_comparisons(path):
            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)}: {occurrence}"
            )

        source = path.read_text(encoding="utf-8")
        if "WorkflowType." in source:
            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} branches on WorkflowType"
            )

    assert offenders == []


def test_the_document_retrieval_surface_has_no_ai_dependency() -> None:
    """Document Retrieval is deterministic, index-driven retrieval: no
    provider SDK, no embeddings, no vector store anywhere in its domain,
    adapter or service."""

    forbidden = (
        "anthropic",
        "openai",
        "app.services.ai",
        "numpy",
        "faiss",
        "chromadb",
        "sentence_transformers",
    )
    surface = (
        DOMAIN_ROOT / "engineering_index",
        APP_ROOT / "infrastructure" / "engineering_index",
        APP_ROOT / "services" / "document_retrieval_service.py",
    )
    offenders: list[str] = []

    for target in surface:
        paths = (
            _python_files(target) if target.is_dir() else [target]
        )
        for path in paths:
            for module in _imported_module_names(path):
                if _violates(module, forbidden):
                    offenders.append(
                        f"{path.relative_to(APP_ROOT.parent)} imports "
                        f"'{module}'"
                    )

    assert offenders == []


# --- 5. Verification is a workflow, not engine logic (Milestone 24.1) --------


def test_no_verification_logic_lives_inside_the_engine() -> None:
    """
    The first *reasoning* workflow must not put reasoning in the
    coordinator. No engine module - core or handler - may name a verdict,
    a verification outcome, or the verification assessment type. Verdict
    reading belongs to Engineering Response; verdict *asking* belongs to
    Prompt Builder.
    """

    # Whole-word matching: the engine legitimately has its own
    # ``UNSUPPORTED``/``UNSUPPORTED_INTENT`` members, which merely contain
    # the substring "SUPPORTED" and mean something entirely different.
    forbidden_names = (
        "VerificationOutcome",
        "VerificationAssessment",
        "SUPPORTED",
        "NOT_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
        "CONFLICTING_EVIDENCE",
    )
    patterns = {
        name: re.compile(rf"{re.escape(name)}") for name in forbidden_names
    }
    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        source = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            if pattern.search(source):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} mentions '{name}'"
                )

    assert offenders == []


def test_the_engine_never_imports_the_verification_reader() -> None:
    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        for module in _imported_module_names(path):
            if _violates(
                module,
                (
                    "app.domain.engineering_response."
                    "engineering_response_verification",
                    "app.domain.prompt_builder.composition_policy",
                ),
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_prompt_builder_owns_every_verification_instruction() -> None:
    """No prompt template outside Prompt Builder: the verdict vocabulary
    and every verification instruction are declared in its composition
    policy, and nothing else in the codebase declares prompt text for
    them."""

    policy = (
        DOMAIN_ROOT / "prompt_builder" / "composition_policy.py"
    ).read_text(encoding="utf-8")

    assert "VERIFICATION_INSTRUCTIONS" in policy
    assert "VERIFICATION_VERDICT_TOKENS" in policy

    declaring: list[str] = []
    for root in (
        ENGINE_SERVICE_ROOT,
        ENGINE_DOMAIN_ROOT,
        DOMAIN_ROOT / "retrieval_bridge",
        DOMAIN_ROOT / "structured_retrieval",
        DOMAIN_ROOT / "context_builder",
    ):
        for path in _python_files(root):
            if "VERIFICATION_INSTRUCTIONS" in path.read_text(
                encoding="utf-8"
            ):
                declaring.append(str(path.relative_to(APP_ROOT.parent)))

    assert declaring == []


def test_the_verdict_vocabulary_has_exactly_one_definition() -> None:
    """Engineering Response imports Prompt Builder's tokens rather than
    restating them, so the question asked and the answer read cannot
    drift."""

    defining = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _python_files(DOMAIN_ROOT)
        if "VERIFICATION_VERDICT_TOKENS: tuple" in path.read_text(
            encoding="utf-8"
        )
    ]

    assert defining == [
        str(
            (DOMAIN_ROOT / "prompt_builder" / "composition_policy.py").
            relative_to(APP_ROOT.parent)
        )
    ]


def test_the_runtime_stays_provider_neutral_for_verification() -> None:
    """Verification introduced no provider-specific behaviour: the engine
    still reaches the LLM only through the provider-neutral runtime, and no
    verification module names a provider."""

    surface = (
        _python_files(ENGINE_SERVICE_ROOT)
        + _python_files(ENGINE_DOMAIN_ROOT)
        + _python_files(DOMAIN_ROOT / "engineering_response")
        + _python_files(DOMAIN_ROOT / "prompt_builder")
    )
    forbidden = ("anthropic", "openai", "ollama", "azure", "app.infrastructure.llm")
    offenders: list[str] = []

    for path in surface:
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_engineering_response_reads_only_the_declared_verdict_line() -> None:
    """The narrow-protocol guarantee, as source structure: the verification
    reader matches against Prompt Builder's token table and does no keyword
    search over the body."""

    source = (
        DOMAIN_ROOT
        / "engineering_response"
        / "engineering_response_verification.py"
    ).read_text(encoding="utf-8")

    assert "VERIFICATION_VERDICT_TOKENS" in source
    # An exact table lookup on the first line, not a search of the body
    # for a token that happens to appear somewhere in it.
    assert "_OUTCOME_BY_TOKEN.get(" in source
    assert "_first_text_line" in source


# --- 6. Comparison is a workflow, not engine reasoning (Milestone 24.2) ------


def test_no_comparison_reasoning_lives_inside_the_engine() -> None:
    """
    The engine coordinates two retrievals; it decides nothing about what
    differs between them. No engine module may name a comparison outcome,
    the assessment type, or any finding category - deciding those is
    Prompt Builder's (what to ask) and Engineering Response's (what was
    answered).
    """

    # The **vocabulary**, not the English language: type names and the
    # uppercase outcome/finding literals. A docstring explaining why the
    # two sides are kept apart may of course use the word "difference" -
    # what it must not do is restate the terms the answer is judged in.
    forbidden_names = (
        "ComparisonOutcome",
        "ComparisonAssessment",
        "COMPARABLE",
        "ADDED",
        "REMOVED",
        "MODIFIED",
        "UNCHANGED",
    )
    patterns = {
        name: re.compile(rf"\b{re.escape(name)}\b") for name in forbidden_names
    }
    offenders: list[str] = []

    for path in _python_files(ENGINE_SERVICE_ROOT) + _python_files(
        ENGINE_DOMAIN_ROOT
    ):
        source = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            if pattern.search(source):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} mentions '{name}'"
                )

    assert offenders == []


def test_the_engine_never_imports_the_comparison_reader_or_policy() -> None:
    """The engine reaches neither the module that reads a comparison
    outcome nor the policy that declares the vocabulary."""

    forbidden = (
        "app.domain.engineering_response.engineering_response_comparison",
        "app.domain.prompt_builder.composition_policy",
        "app.domain.prompt_builder.comparison_prompt_composition",
        "app.domain.retrieval_bridge",
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


def test_comparison_prompt_instructions_exist_only_in_prompt_builder() -> None:
    """No prompt template outside Prompt Builder - including in the
    comparison handlers, which carry no prompt text of their own."""

    policy = (
        DOMAIN_ROOT / "prompt_builder" / "composition_policy.py"
    ).read_text(encoding="utf-8")

    assert "COMPARISON_INSTRUCTIONS" in policy
    assert "COMPARISON_OUTCOME_TOKENS" in policy

    declaring: list[str] = []
    for root in (
        ENGINE_SERVICE_ROOT,
        ENGINE_DOMAIN_ROOT,
        DOMAIN_ROOT / "retrieval_bridge",
        DOMAIN_ROOT / "context_builder",
        DOMAIN_ROOT / "structured_retrieval",
    ):
        for path in _python_files(root):
            if "COMPARISON_INSTRUCTIONS" in path.read_text(encoding="utf-8"):
                declaring.append(str(path.relative_to(APP_ROOT.parent)))

    assert declaring == []


def test_the_comparison_outcome_vocabulary_has_one_definition() -> None:
    defining = [
        str(path.relative_to(APP_ROOT.parent))
        for path in _python_files(DOMAIN_ROOT)
        if "COMPARISON_OUTCOME_TOKENS: tuple" in path.read_text(
            encoding="utf-8"
        )
    ]

    assert defining == [
        str(
            (DOMAIN_ROOT / "prompt_builder" / "composition_policy.py").
            relative_to(APP_ROOT.parent)
        )
    ]


def test_provider_adapters_are_unaware_of_comparison_semantics() -> None:
    """
    The runtime and its adapters map sections to messages. They must not
    know what a comparison is - a provider adapter that special-cased the
    two sides would be a provider-specific engineering behaviour, which is
    exactly what the provider-neutral runtime exists to prevent.

    The mapper's section-role table names ``LEFT_KNOWLEDGE`` and
    ``RIGHT_KNOWLEDGE`` because they are *sections*, which is why the
    check below targets comparison **semantics** rather than the section
    names themselves.
    """

    forbidden_names = (
        "ComparisonContextPackage",
        "ComparisonOutcome",
        "ComparisonAssessment",
        "COMPARISON_INSTRUCTIONS",
        "COMPARISON_OUTCOME_TOKENS",
        "COMPARABLE",
    )
    patterns = {
        name: re.compile(rf"\b{re.escape(name)}\b") for name in forbidden_names
    }
    surface = _python_files(APP_ROOT / "infrastructure" / "llm") + [
        APP_ROOT / "application" / "services" / "llm_runtime.py",
        APP_ROOT
        / "application"
        / "services"
        / "prompt_package_to_llm_request_mapper.py",
    ]
    offenders: list[str] = []

    for path in surface:
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        for name, pattern in patterns.items():
            if pattern.search(source):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} mentions '{name}'"
                )

    assert offenders == []


def test_the_comparison_preparation_policy_is_explicit_and_reviewable() -> None:
    """The two-operand rule is table data with a stated count, not a
    number buried in a branch."""

    policy = (
        DOMAIN_ROOT / "retrieval_bridge" / "retrieval_bridge_policy.py"
    ).read_text(encoding="utf-8")

    assert "REQUIRED_COMPARISON_OPERAND_COUNT = 2" in policy
    assert "COMPARISON_OPERAND_POLICY = IntentRetrievalPolicy(" in policy
    assert "BRIDGE_POLICY_VERSION" in policy


def test_comparison_handlers_carry_no_prompt_text_or_verdict_logic() -> None:
    source = (
        ENGINE_SERVICE_ROOT / "comparison_step_handlers.py"
    ).read_text(encoding="utf-8")

    for name in ("COMPARABLE", "ADDED", "REMOVED", "UNCHANGED"):
        assert not re.search(rf"\b{name}\b", source)
