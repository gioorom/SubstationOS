"""
Architecture tests for Document Ingestion (Milestone 25.1).

This context is defined as much by what it does *not* do as by what it
does, and every one of those exclusions is something it could plausibly
grow into:

1. **It cannot reach a model.** No LLM Runtime, no Prompt Builder, no
   provider SDK, no embeddings - "this milestone implements no AI
   extraction" is enforced rather than intended.
2. **It cannot write knowledge.** Neither the Engineering Index nor the
   Project Knowledge Graph. Preparing a document to be extracted from and
   actually extracting from it are different milestones, and a context
   that could write either would have quietly become the second.
3. **It does not know about answering.** No Engineering Engine, no
   workflow, no retrieval.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

INGESTION_DOMAIN_ROOT = DOMAIN_ROOT / "document_ingestion"
INGESTION_SERVICE = APP_ROOT / "services" / "document_ingestion_service.py"
INGESTION_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "document_ingestion"
INGESTION_ROUTER = APP_ROOT / "routers" / "document_ingestion.py"


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


def _ingestion_surface() -> list[Path]:
    """Every module of this context - domain, adapter, service, router."""

    return (
        _python_files(INGESTION_DOMAIN_ROOT)
        + _python_files(INGESTION_ADAPTER_ROOT)
        + [INGESTION_SERVICE, INGESTION_ROUTER]
    )


# --- 1. Ingestion cannot reach a model ---------------------------------------

_AI_MODULES = (
    "anthropic",
    "openai",
    "ollama",
    "azure",
    "numpy",
    "torch",
    "transformers",
    "sentence_transformers",
    "faiss",
    "chromadb",
    "tiktoken",
    "app.services.ai",
    "app.infrastructure.llm",
    "app.application.services.llm_invocation_service",
    "app.application.services.llm_runtime",
    "app.application.services.llm_provider_registry",
    "app.application.models.llm_invocation",
    "app.domain.prompt_builder",
    "app.services.prompt_builder_service",
    "app.domain.context_builder",
    "app.services.context_builder_service",
)


def test_ingestion_cannot_import_the_llm_runtime_or_a_provider() -> None:
    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(module, _AI_MODULES):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_ingestion_cannot_import_prompt_builder() -> None:
    """Named separately from the general AI check because it is the one a
    future 'just summarise the document while we are here' change would
    reach for first."""

    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(
                module,
                (
                    "app.domain.prompt_builder",
                    "app.services.prompt_builder_service",
                ),
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 2. Ingestion cannot write knowledge -------------------------------------


def test_ingestion_cannot_write_the_engineering_index() -> None:
    """It may read the document repository through
    ``DocumentMetadataPort`` - which happens to live in the
    ``engineering_index`` package - but must never reach the Index's own
    write port, service, model or adapter."""

    forbidden = (
        "app.domain.engineering_index.engineering_index_repository",
        "app.domain.engineering_index.engineering_index_factory",
        "app.domain.engineering_index.engineering_index_models",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository",  # noqa: E501
        "app.models.engineering_index",
    )
    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_ingestion_cannot_write_the_knowledge_graph() -> None:
    forbidden = (
        "app.domain.project_knowledge_graph",
        "app.domain.graph_builder",
        "app.domain.graph_query",
        "app.domain.canonicalization",
        "app.domain.proposed_claims",
        "app.domain.review_workflow",
        "app.services.knowledge_graph",
        "app.services.graph_builder_service",
        "app.services.graph_execution_service",
        "app.services.graph_query_service",
        "app.services.canonicalization_service",
        "app.services.proposed_claim_service",
        "app.models.knowledge_graph",
        "app.models.project_knowledge_graph",
        "app.models.graph_builder",
        "app.infrastructure.project_knowledge_graph",
        "app.infrastructure.graph_query",
    )
    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_ingestion_port_offers_no_way_to_write_knowledge() -> None:
    """The repository port is deliberately narrow: it stores jobs and
    reads them back. Asserted on the **contract** - the abstract method
    set - rather than on the file's prose, which of course discusses the
    exclusions it exists to explain. A method beyond this set would make
    those exclusions a matter of discipline rather than of contract."""

    from app.domain.document_ingestion.ingestion_repository import (
        IngestionJobRepository,
    )

    assert set(IngestionJobRepository.__abstractmethods__) == {
        "save",
        "update",
        "get_by_id",
        "list_by_document",
        "find_active_for_document",
        "list_by_project",
    }


# --- 3. Ingestion does not know about answering ------------------------------


def test_ingestion_cannot_import_the_engineering_engine() -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.retrieval_bridge",
        "app.domain.structured_retrieval",
        "app.services.structured_retrieval_service",
        "app.services.document_retrieval_service",
        "app.domain.engineering_response",
        "app.services.engineering_response_service",
        "app.domain.engineering_intent",
        "app.services.engineering_intent_service",
    )
    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_engine_never_imports_ingestion() -> None:
    """The dependency runs one way only - and today it runs neither way,
    which is the honest state: ingestion prepares documents, the engine
    answers questions, and nothing yet connects them."""

    offenders: list[str] = []

    for path in _python_files(
        APP_ROOT / "services" / "engineering_engine"
    ) + _python_files(DOMAIN_ROOT / "engineering_engine"):
        for module in _imported_module_names(path):
            if _violates(
                module,
                (
                    "app.domain.document_ingestion",
                    "app.services.document_ingestion_service",
                ),
            ):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 4. Domain layering ------------------------------------------------------


def test_the_ingestion_domain_holds_no_infrastructure_dependency() -> None:
    forbidden = (
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "httpx",
        "requests",
        "app.models",
        "app.database",
        "app.infrastructure",
        "app.routers",
        "app.schemas",
        "app.services",
        "app.application",
    )
    offenders: list[str] = []

    for path in _python_files(INGESTION_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_the_ingestion_domain_reads_no_document_contents() -> None:
    """It orchestrates; it does not parse. No PDF reader, no text
    extractor, no storage access anywhere in the context."""

    forbidden = (
        "fitz",
        "pymupdf",
        "PIL",
        "pytesseract",
        "app.services.pdf_text_extractor",
        "app.services.pdf_renderer",
        "app.services.storage",
        "app.services.document_analyzer",
        "app.services.entity_extractor",
    )
    offenders: list[str] = []

    for path in _ingestion_surface():
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# Side-effect-free standard-library modules the pipeline may use. An
# allowlist rather than a "no standard library" rule, because the point
# is that the pipeline cannot *reach anything* - a file, a socket, a
# clock, a random number - not that it cannot build a dataclass.
_PURE_STANDARD_LIBRARY = frozenset(
    {"__future__", "dataclasses", "enum", "abc", "typing"}
)


def test_the_pipeline_performs_no_io() -> None:
    """The pipeline is a pure function: the service reads through the port
    and hands the result over. A pipeline that could read would make its
    own determinism unverifiable."""

    offenders = [
        module
        for module in _imported_module_names(
            INGESTION_DOMAIN_ROOT / "ingestion_pipeline.py"
        )
        if not module.startswith("app.domain.")
        and module not in _PURE_STANDARD_LIBRARY
    ]

    assert offenders == []


# --- 5. The lifecycle is a table, not a branch chain -------------------------


def test_the_lifecycle_is_declared_as_an_explicit_transition_table() -> None:
    source = (
        INGESTION_DOMAIN_ROOT / "ingestion_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert (
        "VALID_TRANSITIONS: dict[IngestionState, frozenset[IngestionState]]"
        in source
    )
    assert "def is_transition_valid" in source


def test_a_job_cannot_have_its_state_reassigned() -> None:
    """The job is frozen, so there is no way to change a state except by
    building a new value - and ``transition_to`` is the only thing that
    does, validating the move as it goes."""

    import dataclasses

    from app.domain.document_ingestion.ingestion_models import IngestionJob

    assert dataclasses.fields(IngestionJob)
    assert IngestionJob.__dataclass_params__.frozen is True


def test_the_transition_helpers_live_only_in_the_factory() -> None:
    """A second module advancing a job would be a second place the
    lifecycle table could be bypassed."""

    declaring: list[str] = []

    for path in _ingestion_surface():
        if "def transition_to(" in path.read_text(encoding="utf-8"):
            declaring.append(str(path.relative_to(APP_ROOT.parent)))

    assert declaring == [
        str(
            (INGESTION_DOMAIN_ROOT / "ingestion_factory.py").relative_to(
                APP_ROOT.parent
            )
        )
    ]
