"""
Architecture tests for the Canonical PDF Representation (Milestone 26.1).

This context sits at the most dangerous point in the pipeline: it is the
first thing in the system that reads what a document *says*. Two
boundaries have to hold, and neither can be left to discipline.

1. **It transcribes; it does not interpret.** No LLM, no Prompt Builder,
   no Engineering Engine, no embeddings, no OCR - and no write to the
   Engineering Index or the Knowledge Graph. What it stores is what the
   parser observed.
2. **It is the only place a PDF is decoded.** Every future extraction
   consumer reads the canonical representation through its port. An
   extractor that opened the original PDF would re-decode bytes already
   decoded once, under whatever library version happened to be installed
   that day, and would silently destroy the reproducibility this
   milestone exists to establish.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

CANONICAL_DOMAIN_ROOT = DOMAIN_ROOT / "canonical_pdf"
CANONICAL_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "canonical_pdf"
CANONICAL_SERVICE = APP_ROOT / "services" / "canonical_pdf_service.py"
CANONICAL_ROUTER = APP_ROOT / "routers" / "canonical_pdf.py"

PARSER_ADAPTER = CANONICAL_ADAPTER_ROOT / "pymupdf_parser.py"

# Milestone 26.2 retired every pre-canonical decoder. The four modules
# that used to appear here - ``pdf_text_extractor``, ``pdf_renderer``,
# ``document_analyzer`` and ``intelligence/renderer`` - are deleted, and
# ``test_the_retired_decoders_are_gone`` below asserts they stay deleted.
#
# The set is now empty, which is the point: exactly one adapter in this
# system may open a PDF.
LEGACY_PDF_READERS: frozenset = frozenset()

# The modules Milestone 26.2 removed. Named so that reintroducing one -
# by restoring a file or by writing a new module under the same name -
# fails a test rather than quietly re-opening a second decoding path.
RETIRED_PDF_READERS = (
    APP_ROOT / "services" / "pdf_text_extractor.py",
    APP_ROOT / "services" / "pdf_renderer.py",
    APP_ROOT / "services" / "document_analyzer.py",
    APP_ROOT / "services" / "intelligence" / "renderer.py",
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


def _canonical_surface() -> list[Path]:
    """Every module of this context - domain, adapter, service, router."""

    return (
        _python_files(CANONICAL_DOMAIN_ROOT)
        + _python_files(CANONICAL_ADAPTER_ROOT)
        + [CANONICAL_SERVICE, CANONICAL_ROUTER]
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


# --- 1. It transcribes; it does not interpret ---------------------------


def test_canonicalisation_cannot_import_the_llm_runtime() -> None:
    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.application.services.llm_provider_registry",
        "app.application.models.llm_invocation",
        "app.domain.llm_provider",
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_canonicalisation_cannot_import_prompt_builder() -> None:
    """The one a future "just summarise the document while we are here"
    change would reach for first."""

    forbidden = (
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
        "app.services.context_builder_service",
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_canonicalisation_cannot_import_the_engineering_engine() -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.engineering_intent",
        "app.services.engineering_intent_service",
        "app.domain.engineering_response",
        "app.services.engineering_response_service",
        "app.domain.retrieval_bridge",
        "app.domain.structured_retrieval",
        "app.services.structured_retrieval_service",
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_canonicalisation_cannot_write_the_engineering_index() -> None:
    """It may read document metadata through ``DocumentMetadataPort`` -
    which happens to live in the ``engineering_index`` package - but must
    never reach the Index's own write port, factory, service, model or
    adapter."""

    forbidden = (
        "app.domain.engineering_index.engineering_index_repository",
        "app.domain.engineering_index.engineering_index_factory",
        "app.domain.engineering_index.engineering_index_models",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository",  # noqa: E501
        "app.models.engineering_index",
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_canonicalisation_cannot_write_the_knowledge_graph() -> None:
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
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_canonicalisation_performs_no_ocr_and_no_embeddings() -> None:
    """Scanned PDFs are unsupported, and saying so is the honest answer.
    An OCR import here would turn "no text was found" into a guess about
    pixels."""

    forbidden = (
        "pytesseract",
        "easyocr",
        "paddleocr",
        "PIL",
        "cv2",
        "numpy",
        "torch",
        "transformers",
        "sentence_transformers",
        "faiss",
        "chromadb",
        "tiktoken",
    )

    assert _offenders(_canonical_surface(), forbidden) == []


def test_the_representation_has_nowhere_to_record_an_interpretation(
) -> None:
    """Asserted on the persisted schema as well as the value objects: a
    column is how an inference would actually survive."""

    from app.models.canonical_pdf import (
        CanonicalPdfBlockRecord,
        CanonicalPdfPageRecord,
        CanonicalPdfRepresentation,
        CanonicalPdfSpanRecord,
    )

    forbidden = {
        "section",
        "table",
        "heading",
        "paragraph",
        "entity",
        "summary",
        "topic",
        "label",
        "category",
    }
    columns = {
        column.name
        for model in (
            CanonicalPdfRepresentation,
            CanonicalPdfPageRecord,
            CanonicalPdfBlockRecord,
            CanonicalPdfSpanRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


# --- 2. One decoding boundary --------------------------------------------


def test_only_the_parser_adapter_decodes_a_pdf() -> None:
    """
    **Exactly one** module in this system may touch a PDF library, since
    Milestone 26.2.

    A second one would be a second decoding path, and two decoders
    disagreeing about a difficult drawing is the failure mode this
    boundary exists to prevent.
    """

    pdf_libraries = (
        "fitz",
        "pymupdf",
        "pypdf",
        "PyPDF2",
        "pdfplumber",
        "pdfminer",
    )
    decoders = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(module, pdf_libraries)
            for module in _imported_module_names(path)
        )
    }

    assert decoders == {
        PARSER_ADAPTER.relative_to(APP_ROOT.parent).as_posix()
    } | {
        legacy.relative_to(APP_ROOT.parent).as_posix()
        for legacy in LEGACY_PDF_READERS
    }


def test_the_retired_decoders_are_gone() -> None:
    """
    The four pre-canonical decoders Milestone 26.2 removed stay removed.

    Asserted on the filesystem rather than on imports, because the way
    this regresses is somebody restoring a file - and a restored decoder
    with no importers yet would pass every import-based check while
    sitting there waiting to be used.
    """

    surviving = [
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in RETIRED_PDF_READERS
        if path.exists()
    ]

    assert surviving == []


def test_nothing_imports_a_retired_decoder() -> None:
    """The other half of the same guarantee: no module anywhere still
    refers to one of them, so nothing is waiting to break when the import
    is finally attempted."""

    retired_modules = tuple(
        f"app.services.{legacy.relative_to(APP_ROOT / 'services').as_posix()[:-3].replace('/', '.')}"  # noqa: E501
        for legacy in RETIRED_PDF_READERS
    ) + ("app.services.intelligence",)
    importers = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(module, retired_modules)
            for module in _imported_module_names(path)
        )
    }

    assert importers == set()


def test_the_canonical_domain_never_touches_a_pdf_library() -> None:
    """The domain describes a representation; it has no idea what a PDF
    is. That is what makes replacing PyMuPDF a change to one adapter."""

    forbidden = ("fitz", "pymupdf", "pypdf", "pdfplumber", "pdfminer")

    assert _offenders(_python_files(CANONICAL_DOMAIN_ROOT), forbidden) == []


def test_the_canonical_domain_holds_no_infrastructure_dependency() -> None:
    forbidden = (
        "os",
        "pathlib",
        "shutil",
        "tempfile",
        "boto3",
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

    assert _offenders(_python_files(CANONICAL_DOMAIN_ROOT), forbidden) == []


def test_the_canonical_domain_never_opens_a_file() -> None:
    """Bytes arrive through Milestone 25.2's content port. Nothing here
    calls ``open`` or constructs a path - matched on the syntax tree, so
    prose describing the rule is not mistaken for breaking it."""

    file_access = {"open", "Path", "PurePath"}
    offenders: list[str] = []

    for path in _python_files(CANONICAL_DOMAIN_ROOT):
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


def test_the_parser_port_receives_bytes_rather_than_a_location() -> None:
    """A port taking a path could open a file, and the governed content
    port would become optional. Taking bytes makes bypassing it
    impossible rather than merely discouraged."""

    from app.domain.canonical_pdf.pdf_parser_port import PdfParserPort

    parameters = inspect.signature(PdfParserPort.parse).parameters

    assert parameters["content"].annotation == "bytes"
    assert "path" not in parameters
    assert "storage_reference" not in parameters
    assert "file_path" not in parameters


def test_the_parser_adapter_reaches_no_storage() -> None:
    """It receives bytes and decodes them. It cannot read a file, so it
    cannot be handed a document the content port never approved."""

    forbidden = (
        "os",
        "pathlib",
        "shutil",
        "boto3",
        "app.services.storage",
        "app.infrastructure.document_identity",
        "app.models",
        "app.database",
    )

    assert _offenders([PARSER_ADAPTER], forbidden) == []


# --- 3. Consumers read the representation, not the PDF --------------------


def test_the_representation_port_offers_no_route_to_the_original_pdf(
) -> None:
    """Asserted on the **contract** - the abstract method set - rather
    than on the module's prose. A ``path``, ``open`` or ``raw_content``
    here would hand every future extractor the original bytes and make
    this whole milestone optional."""

    from app.domain.canonical_pdf.canonical_representation_repository import (
        CanonicalRepresentationRepository,
    )

    assert set(
        CanonicalRepresentationRepository.__abstractmethods__
    ) == {
        "save",
        "find_for_content",
        "find_latest_for_document",
    }


def test_the_representation_repository_never_writes_a_document() -> None:
    """The uploaded PDF is authoritative. The adapter that stores
    representations has no reference to the document row, its path, or
    stored content of any kind."""

    adapter = (
        CANONICAL_ADAPTER_ROOT
        / "sqlalchemy_canonical_representation_repository.py"
    )
    forbidden = (
        "app.models.document",
        "app.services.storage",
        "app.infrastructure.document_identity",
        "pathlib",
        "os",
    )

    assert _offenders([adapter], forbidden) == []


def test_the_canonical_service_reads_content_only_through_the_port(
) -> None:
    """Milestone 25.2's content port stays the one governed way into
    stored bytes - the service cannot open a file even if it wanted
    to."""

    forbidden = ("pathlib", "os", "io", "shutil", "app.services.storage")

    assert _offenders([CANONICAL_SERVICE], forbidden) == []


def test_no_context_outside_canonicalisation_consumes_stored_pdf_bytes(
) -> None:
    """The content port exists for identity and canonicalisation. A
    future extractor appearing in this list would be reading the original
    PDF instead of the representation.

    ``document_pipeline_service`` (Milestone 26.2) appears because it
    *passes the ports through* to ingestion and canonicalisation. It
    never calls them - asserted separately in
    ``test_document_pipeline_boundaries.py`` - and everything downstream
    of it receives assembled text and nothing else."""

    permitted = {
        "app/domain/document_identity",
        "app/infrastructure/document_identity",
        "app/infrastructure/canonical_pdf",
        "app/services/document_identity_service.py",
        "app/services/document_format_backfill_service.py",
        "app/services/document_ingestion_service.py",
        "app/services/canonical_pdf_service.py",
        "app/services/document_pipeline_service.py",
        # Milestone 30.1.3: the governed download. It resolves a document
        # id to an opaque storage reference through the registry and hands
        # that reference straight back to the content port - it parses no
        # path, joins no root and accepts nothing from a caller but an
        # integer. Serving stored bytes is the fourth job that genuinely
        # needs them.
        "app/services/document_registry_service.py",
        "app/routers/documents.py",
        "app/routers/document_ingestion.py",
        "app/routers/canonical_pdf.py",
    }
    importers = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(
                module,
                (
                    "app.domain.document_identity.document_content_port",
                    "app.infrastructure.document_identity",
                ),
            )
            for module in _imported_module_names(path)
        )
    }

    unexpected = {
        importer
        for importer in importers
        if not any(
            importer == entry or importer.startswith(f"{entry}/")
            for entry in permitted
        )
    }

    assert unexpected == set()


# --- 4. Taxonomy agreement -----------------------------------------------


def test_the_shared_failure_codes_agree_with_ingestions() -> None:
    """The five causes both contexts can report carry identical values.
    Restated rather than imported - two vocabularies, one meaning - and
    asserted here so they cannot drift apart."""

    from app.domain.canonical_pdf.canonical_pdf_failures import (
        CanonicalizationFailureCode,
    )
    from app.domain.document_ingestion.ingestion_models import (
        IngestionFailureCode,
    )

    shared = {
        "DOCUMENT_NOT_FOUND",
        "UNSUPPORTED_FORMAT",
        "CONTENT_NOT_FOUND",
        "CONTENT_INACCESSIBLE",
        "EMPTY_CONTENT",
    }

    for name in shared:
        assert (
            CanonicalizationFailureCode[name].value
            == IngestionFailureCode[name].value
        )


def test_ingestion_does_not_depend_on_canonicalisation() -> None:
    """The dependency runs one way: canonicalisation consumes what
    ingestion concluded, never the reverse. Ingestion stays a context that
    reads no document contents."""

    forbidden = (
        "app.domain.canonical_pdf",
        "app.services.canonical_pdf_service",
        "app.infrastructure.canonical_pdf",
        "app.models.canonical_pdf",
    )
    ingestion_surface = (
        _python_files(DOMAIN_ROOT / "document_ingestion")
        + _python_files(APP_ROOT / "infrastructure" / "document_ingestion")
        + [APP_ROOT / "services" / "document_ingestion_service.py"]
    )

    assert _offenders(ingestion_surface, forbidden) == []
