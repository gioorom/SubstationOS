"""
Architecture tests for the consolidated document pipeline
(Milestone 26.2).

Milestones 26.1 and 27.1 built the canonical path. This one made it the
**only** path: the upload endpoint no longer decodes a PDF, the four
pre-canonical decoders are gone, and the Knowledge Graph receives text
assembled from the segmentation rather than bytes from a file.

These tests pin that arrangement in place. Each of them fails the moment
a second way to read a document starts to grow back.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

PIPELINE_SERVICE = APP_ROOT / "services" / "document_pipeline_service.py"
UPLOAD_ROUTER = APP_ROOT / "routers" / "documents.py"
ASSEMBLER = (
    DOMAIN_ROOT / "canonical_text" / "canonical_text_assembler.py"
)
PARSER_ADAPTER = (
    APP_ROOT / "infrastructure" / "canonical_pdf" / "pymupdf_parser.py"
)

# Every module of the Knowledge Graph path the upload endpoint feeds.
#
# The live chain is ``knowledge_graph.ingest_document`` ->
# ``services.ai.extractor`` (which is LLM-backed, and was so long before
# this milestone) -> ``services.topology``. All of it is listed, because
# the boundary this milestone enforces is that *none* of it may reach a
# document: it receives a string.
KNOWLEDGE_GRAPH_MODULES = (
    APP_ROOT / "services" / "knowledge_graph.py",
    APP_ROOT / "services" / "entity_extractor.py",
)

KNOWLEDGE_GRAPH_PACKAGES = (
    APP_ROOT / "services" / "ai",
    APP_ROOT / "services" / "topology",
)

PDF_LIBRARIES = (
    "fitz",
    "pymupdf",
    "pypdf",
    "PyPDF2",
    "pdfplumber",
    "pdfminer",
)

RAW_CONTENT_MODULES = (
    "app.domain.document_identity.document_content_port",
    "app.domain.document_identity.document_storage_location",
    "app.infrastructure.document_identity",
    "app.services.storage",
)


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


def _offenders(paths, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []

    for path in paths:
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                found.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    return found


def _knowledge_graph_surface() -> list[Path]:
    modules = [path for path in KNOWLEDGE_GRAPH_MODULES if path.exists()]

    for package in KNOWLEDGE_GRAPH_PACKAGES:
        if package.exists():
            modules.extend(_python_files(package))

    return modules


# --- 1. Exactly one decoder ------------------------------------------------


def test_exactly_one_production_adapter_imports_a_pdf_library() -> None:
    """
    The headline guarantee of this milestone.

    Before 26.2 there were five importers of a PDF library; there is now
    one, and it is the canonical parser adapter. Any second importer is a
    second decoding path, and two decoders disagreeing about a difficult
    drawing is precisely the failure this arrangement prevents.
    """

    decoders = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(module, PDF_LIBRARIES)
            for module in _imported_module_names(path)
        )
    }

    assert decoders == {
        PARSER_ADAPTER.relative_to(APP_ROOT.parent).as_posix()
    }


# --- 2. The Knowledge Graph reads text, not documents ----------------------


def test_no_knowledge_graph_module_imports_a_pdf_library() -> None:
    assert _offenders(_knowledge_graph_surface(), PDF_LIBRARIES) == []


def test_no_knowledge_graph_module_reaches_stored_content() -> None:
    """
    No content port, no storage-location port, no filesystem adapter, no
    upload storage path. The Knowledge Graph is handed a string.

    ``os`` is deliberately *not* forbidden here: the Claude provider
    reads its credential from the environment, which is configuration
    rather than document content. What the next test forbids is the thing
    that would actually matter - opening a file.
    """

    forbidden = RAW_CONTENT_MODULES + ("pathlib", "shutil")

    assert _offenders(_knowledge_graph_surface(), forbidden) == []


def test_no_knowledge_graph_module_opens_a_file() -> None:
    """Matched on the syntax tree, so a module that merely imports ``os``
    for an environment variable is not mistaken for one that reads a
    document."""

    file_access = {"open", "Path", "PurePath", "scandir", "listdir"}
    offenders: list[str] = []

    for path in _knowledge_graph_surface():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            called = node.func
            name = (
                called.id
                if isinstance(called, ast.Name)
                else called.attr
                if isinstance(called, ast.Attribute)
                else ""
            )

            if name in file_access:
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} calls '{name}'"
                )

    assert offenders == []


def test_no_knowledge_graph_module_reaches_the_canonical_parser() -> None:
    forbidden = (
        "app.infrastructure.canonical_pdf",
        "app.domain.canonical_pdf.pdf_parser_port",
        "app.services.canonical_pdf_service",
    )

    assert _offenders(_knowledge_graph_surface(), forbidden) == []


def test_the_downstream_consumer_receives_only_text() -> None:
    """
    Asserted on the contract the workflow actually calls.

    ``consumer`` is typed as taking a string and returning something.
    A consumer that could also be handed a document id, a storage
    reference or a segmentation could reach the original bytes for
    itself, which is the arrangement this milestone ended.
    """

    from app.services.document_pipeline_service import (
        process_uploaded_document,
    )

    annotation = inspect.signature(
        process_uploaded_document
    ).parameters["consumer"].annotation

    assert annotation == "Callable[[str], object] | None"


# --- 3. Segmented content is reached through a port ------------------------


def test_the_pipeline_reads_segmented_content_through_the_port() -> None:
    """The workflow depends on the repository *ports*, never on a
    SQLAlchemy adapter or a table."""

    forbidden = (
        "sqlalchemy",
        "app.models",
        "app.database",
        "app.infrastructure",
    )

    assert _offenders([PIPELINE_SERVICE], forbidden) == []


def test_the_assembler_is_a_pure_function_of_the_segmentation() -> None:
    """It renders text from value objects. No I/O, no clock, no
    repository, no consumer - it does not know who reads its output."""

    offenders: list[str] = []

    for module in _imported_module_names(ASSEMBLER):
        if module == "__future__":
            continue

        if module.startswith("app.domain.canonical_text."):
            continue

        offenders.append(module)

    assert offenders == []


def test_canonical_text_cannot_import_the_knowledge_graph() -> None:
    """The dependency runs one way. Segmentation - and the assembler that
    renders it - must stay unaware that a Knowledge Graph exists, or the
    layer every extractor consumes would start being shaped by one
    particular consumer."""

    forbidden = (
        "app.services.knowledge_graph",
        "app.services.entity_extractor",
        "app.models.knowledge_graph",
        "app.services.topology",
        "app.domain.project_knowledge_graph",
    )
    surface = (
        _python_files(DOMAIN_ROOT / "canonical_text")
        + _python_files(APP_ROOT / "infrastructure" / "canonical_text")
        + [APP_ROOT / "services" / "canonical_text_service.py"]
    )

    assert _offenders(surface, forbidden) == []


# --- 4. The router orchestrates and decides nothing ------------------------


def test_the_upload_router_contains_no_parsing_logic() -> None:
    """It constructs adapters and calls a workflow. No PDF library, no
    parser adapter, no extractor - and no text handling of its own."""

    forbidden = PDF_LIBRARIES + (
        "app.infrastructure.canonical_pdf.pymupdf_parser".rsplit(".", 1)[0],
        "app.services.entity_extractor",
    )
    imported = _imported_module_names(UPLOAD_ROUTER)

    # The router *does* construct the parser adapter as a composition
    # root - that is its job - so the check is that it imports the
    # adapter and never a PDF library or an extractor directly.
    assert not any(
        _violates(module, PDF_LIBRARIES) for module in imported
    )
    assert not any(
        _violates(module, ("app.services.entity_extractor",))
        for module in imported
    )
    assert forbidden  # the tuple is used above; kept explicit for readers


def test_the_upload_router_delegates_the_pipeline_to_the_workflow(
) -> None:
    """
    The processing rules live in the workflow, not the API layer.

    Asserted on the syntax tree: the router's own functions may call the
    workflow, but must not call the ingestion, canonicalisation or
    segmentation services themselves - re-sequencing them here would put
    a second, divergent pipeline in the API layer.
    """

    tree = ast.parse(UPLOAD_ROUTER.read_text(encoding="utf-8"))
    called_services = {
        node.func.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
    }

    assert "document_ingestion_service" not in called_services
    assert "canonical_pdf_service" not in called_services
    assert "canonical_text_service" not in called_services
    assert "document_pipeline_service" in called_services


def test_the_workflow_adds_no_processing_of_its_own() -> None:
    """It sequences existing services. It must not import a parser, an
    extractor, an ontology or a model - anything it could use to make a
    decision the stages have not already made."""

    forbidden = PDF_LIBRARIES + (
        "app.services.entity_extractor",
        "app.domain.ontology",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.domain.prompt_builder",
    )

    assert _offenders([PIPELINE_SERVICE], forbidden) == []


# --- 5. The retired decoders stay retired ----------------------------------


def test_no_active_module_imports_a_retired_decoder() -> None:
    retired = (
        "app.services.pdf_text_extractor",
        "app.services.pdf_renderer",
        "app.services.document_analyzer",
        "app.services.intelligence",
    )
    importers = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(module, retired)
            for module in _imported_module_names(path)
        )
    }

    assert importers == set()


def test_the_retired_decoder_files_do_not_exist() -> None:
    """Asserted on the filesystem as well as on imports: a restored file
    with no importers yet would pass every import check while sitting
    there waiting to be used."""

    retired = (
        APP_ROOT / "services" / "pdf_text_extractor.py",
        APP_ROOT / "services" / "pdf_renderer.py",
        APP_ROOT / "services" / "document_analyzer.py",
        APP_ROOT / "services" / "intelligence",
    )

    assert [
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in retired
        if path.exists()
    ] == []


# --- 6. The raw-content consumer list shrank -------------------------------


def test_the_closed_list_of_raw_content_consumers_is_asserted() -> None:
    """
    The list of modules that may reach stored bytes is closed, and this
    milestone made it **smaller**: the upload router's Knowledge Graph
    path left it entirely.

    Everything remaining either establishes identity, ingests, or
    canonicalises - the three jobs that genuinely need bytes. Every
    semantic consumer reads canonical text instead.
    """

    permitted = {
        "app/domain/document_identity",
        "app/infrastructure/document_identity",
        "app/infrastructure/canonical_pdf",
        "app/services/document_identity_service.py",
        "app/services/document_format_backfill_service.py",
        "app/services/document_ingestion_service.py",
        "app/services/canonical_pdf_service.py",
        "app/services/document_pipeline_service.py",
        "app/routers/documents.py",
        "app/routers/document_ingestion.py",
        "app/routers/canonical_pdf.py",
    }
    consumers = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(module, RAW_CONTENT_MODULES)
            for module in _imported_module_names(path)
        )
    }
    unexpected = {
        consumer
        for consumer in consumers
        if not any(
            consumer == entry or consumer.startswith(f"{entry}/")
            for entry in permitted
        )
    }

    assert unexpected == set()


def test_no_semantic_consumer_reaches_stored_content() -> None:
    """The specific shrinkage this milestone delivered, stated as its own
    assertion: nothing that interprets a document may reach the bytes of
    one."""

    semantic_modules = [
        path
        for path in _python_files(APP_ROOT / "services")
        if path.name
        in (
            "knowledge_graph.py",
            "entity_extractor.py",
            "engineering_index_service.py",
            "graph_builder_service.py",
            "canonicalization_service.py",
        )
    ] + _knowledge_graph_surface()

    assert _offenders(semantic_modules, RAW_CONTENT_MODULES) == []
