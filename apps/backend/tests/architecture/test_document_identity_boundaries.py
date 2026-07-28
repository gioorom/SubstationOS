"""
Architecture tests for Document Identity (Milestone 25.2).

This context reads bytes, which makes it the one place in the system
where two boundaries could quietly erode:

1. **It must not read a document, only identify one.** A leading
   signature and a streamed digest, and nothing that could grow into
   parsing, OCR, text extraction, embeddings or an LLM call.
2. **The domain must not reach storage itself.** All bytes arrive through
   ``DocumentContentPort``; no domain module may import a filesystem, a
   cloud-storage client or an ORM.

It also enforces the rule that makes the whole milestone coherent: there
is **one** format rule source, so upload and ingestion cannot disagree
about what a document is.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

IDENTITY_DOMAIN_ROOT = DOMAIN_ROOT / "document_identity"
IDENTITY_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "document_identity"
IDENTITY_SERVICE = APP_ROOT / "services" / "document_identity_service.py"
BACKFILL_SERVICE = (
    APP_ROOT / "services" / "document_format_backfill_service.py"
)
SIGNATURES_MODULE = IDENTITY_DOMAIN_ROOT / "format_signatures.py"


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


def _identity_surface() -> list[Path]:
    return (
        _python_files(IDENTITY_DOMAIN_ROOT)
        + _python_files(IDENTITY_ADAPTER_ROOT)
        + [IDENTITY_SERVICE, BACKFILL_SERVICE]
    )


# --- 1. It identifies documents; it does not read them ------------------

_EXTRACTION_MODULES = (
    "fitz",
    "pymupdf",
    "pdfplumber",
    "PyPDF2",
    "pypdf",
    "PIL",
    "pytesseract",
    "ezdxf",
    "openpyxl",
    "docx",
    "app.services.pdf_text_extractor",
    "app.services.pdf_renderer",
    "app.services.document_analyzer",
    "app.services.entity_extractor",
)

_AI_MODULES = (
    "anthropic",
    "openai",
    "ollama",
    "numpy",
    "torch",
    "transformers",
    "sentence_transformers",
    "faiss",
    "chromadb",
    "tiktoken",
    "app.infrastructure.llm",
    "app.application.services.llm_invocation_service",
    "app.application.services.llm_runtime",
    "app.domain.prompt_builder",
    "app.services.prompt_builder_service",
    "app.domain.context_builder",
    "app.services.context_builder_service",
)


def test_document_identity_cannot_parse_a_document() -> None:
    """A checksum and a 32-byte signature identify a file. A PDF reader
    here would make this context an extractor, which is a different
    milestone and a different set of review obligations."""

    offenders: list[str] = []

    for path in _identity_surface():
        for module in _imported_module_names(path):
            if _violates(module, _EXTRACTION_MODULES):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_document_identity_cannot_reach_a_model() -> None:
    offenders: list[str] = []

    for path in _identity_surface():
        for module in _imported_module_names(path):
            if _violates(module, _AI_MODULES):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


def test_document_identity_writes_no_knowledge() -> None:
    """Neither the Engineering Index nor the Knowledge Graph. Knowing
    which bytes a document is made of is not knowing anything about the
    substation."""

    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
        "app.domain.project_knowledge_graph",
        "app.services.knowledge_graph",
        "app.services.graph_builder_service",
        "app.models.knowledge_graph",
        "app.infrastructure.project_knowledge_graph",
    )
    offenders: list[str] = []

    for path in _identity_surface():
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


# --- 2. The domain reaches storage only through its ports ---------------


def test_the_identity_domain_holds_no_infrastructure_dependency() -> None:
    forbidden = (
        "os",
        "pathlib",
        "shutil",
        "glob",
        "tempfile",
        "boto3",
        "botocore",
        "azure",
        "google",
        "smart_open",
        "fsspec",
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

    for path in _python_files(IDENTITY_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if _violates(module, forbidden):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
                )

    assert offenders == []


_FILE_ACCESS_CALLS = frozenset({"open", "Path", "PurePath"})


def test_the_domain_never_opens_a_file() -> None:
    """Not "it currently does not" - it cannot: nothing in the domain
    calls ``open`` or constructs a path. Every byte arrives through the
    port. Matched on the syntax tree, so prose describing the rule is not
    mistaken for breaking it."""

    offenders: list[str] = []

    for path in _python_files(IDENTITY_DOMAIN_ROOT):
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

            if name in _FILE_ACCESS_CALLS:
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} calls '{name}'"
                )

    assert offenders == []


def test_content_access_is_read_only() -> None:
    """Asserted on the **contract** - the abstract method set - rather
    than on the module's prose. A ``write``, ``save``, ``delete`` or
    ``move`` here would hand every caller of the port a capability this
    milestone never granted."""

    from app.domain.document_identity.document_content_port import (
        DocumentContentPort,
    )

    assert set(DocumentContentPort.__abstractmethods__) == {
        "describe",
        "read_prefix",
        "iter_chunks",
    }


def test_the_storage_location_port_only_reads() -> None:
    from app.domain.document_identity.document_storage_location import (
        DocumentStorageLocationPort,
    )

    assert set(DocumentStorageLocationPort.__abstractmethods__) == {
        "find_storage_reference"
    }


def test_the_only_write_this_milestone_introduces_is_the_format_record(
) -> None:
    """One narrowly-shaped write, for the backfill command a human runs
    deliberately. Nothing else in this milestone modifies a document."""

    from app.domain.document_identity.document_format_registry import (
        DocumentFormatRegistryPort,
    )

    assert set(DocumentFormatRegistryPort.__abstractmethods__) == {
        "list_by_stored_format",
        "record_format",
    }


def test_no_other_context_gained_storage_access() -> None:
    """
    The content port is used by document identity, by ingestion (which
    hands it to the identity service), by the documents router and by the
    backfill command. A caller outside this list would mean storage
    access spreading, which Milestone 25.2 explicitly did not grant.

    Milestone 26.1 added canonicalisation, which reads a PDF's bytes to
    parse them - and does so *through this port* rather than opening the
    file, which is the whole point of the port existing.

    Milestone 26.2 then made this list **shrink**: the upload router no
    longer resolves content for the Knowledge Graph, and the document
    pipeline workflow that replaced it passes the ports through to
    ingestion and canonicalisation without reading anything itself. Every
    entry below is a module that genuinely needs stored bytes; every
    future extractor reads the canonical text instead.
    """

    permitted = {
        "app/domain/document_identity",
        "app/infrastructure/document_identity",
        "app/services/document_identity_service.py",
        "app/services/document_format_backfill_service.py",
        "app/services/document_ingestion_service.py",
        "app/services/canonical_pdf_service.py",
        # Passes the ports through to ingestion and canonicalisation; it
        # never calls them itself (asserted in
        # tests/architecture/test_document_pipeline_boundaries.py).
        "app/services/document_pipeline_service.py",
        "app/routers/documents.py",
        "app/routers/document_ingestion.py",
        "app/routers/canonical_pdf.py",
    }
    importers: set[str] = set()

    for path in _python_files(APP_ROOT):
        for module in _imported_module_names(path):
            if _violates(
                module,
                (
                    "app.domain.document_identity.document_content_port",
                    "app.infrastructure.document_identity",
                ),
            ):
                relative = path.relative_to(APP_ROOT.parent).as_posix()
                importers.add(relative)

    unexpected = {
        importer
        for importer in importers
        if not any(
            importer == entry or importer.startswith(f"{entry}/")
            for entry in permitted
        )
    }

    assert unexpected == set()


# --- 3. One format rule source ------------------------------------------


_RULE_TABLE_NAMES = frozenset(
    {
        "CONTENT_SIGNATURES",
        "AMBIGUOUS_SIGNATURES",
        "MIME_TYPES",
        "FILENAME_EXTENSIONS",
    }
)


def _assigned_names(path: Path) -> set[str]:
    """Module-level assignments only - matched on the syntax tree rather
    than on the text, so a module that merely *reads* a table (or names
    one in a docstring) is not mistaken for one that declares it."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(
            node.target, ast.Name
        ):
            names.add(node.target.id)

    return names


def _byte_literals(path: Path) -> set[bytes]:
    return {
        node.value
        for node in ast.walk(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        )
        if isinstance(node, ast.Constant) and isinstance(node.value, bytes)
    }


def test_only_one_module_declares_the_format_rules() -> None:
    """Upload and ingestion classify through the same classifier, which
    reads only ``format_signatures``. A second table anywhere would let
    the two disagree about what a document is."""

    declaring: list[str] = []

    for path in _python_files(APP_ROOT):
        if path == SIGNATURES_MODULE:
            continue

        if _assigned_names(path) & _RULE_TABLE_NAMES:
            declaring.append(path.relative_to(APP_ROOT.parent).as_posix())

    assert declaring == []


def test_nothing_outside_the_classifier_declares_a_signature() -> None:
    """A signature byte string reappearing in a second module would be a
    format rule growing back somewhere else. Asserted on the byte
    literals in the syntax tree, so documentation quoting ``%PDF-`` in
    prose is not mistaken for a rule."""

    from app.domain.document_identity.format_signatures import (
        CONTENT_SIGNATURES,
    )

    signatures = {prefix for prefix, _ in CONTENT_SIGNATURES}
    offenders: list[str] = []

    for path in _python_files(APP_ROOT):
        if path == SIGNATURES_MODULE:
            continue

        if _byte_literals(path) & signatures:
            offenders.append(path.relative_to(APP_ROOT.parent).as_posix())

    assert offenders == []


def test_the_classifier_reads_only_the_declared_tables() -> None:
    modules = _imported_module_names(
        IDENTITY_DOMAIN_ROOT / "format_classifier.py"
    )

    assert all(
        module.startswith("app.domain.document_identity.")
        or module == "__future__"
        for module in modules
    )


def test_the_signature_prefix_is_too_short_to_be_a_document_read() -> None:
    """32 bytes: enough for the longest signature, never a meaningful
    amount of a drawing."""

    from app.domain.document_identity.format_signatures import (
        CONTENT_SIGNATURES,
        SIGNATURE_PREFIX_LENGTH,
    )

    assert SIGNATURE_PREFIX_LENGTH <= 64
    assert all(
        len(prefix) <= SIGNATURE_PREFIX_LENGTH
        for prefix, _ in CONTENT_SIGNATURES
    )


def test_the_domain_format_vocabulary_matches_the_persisted_one() -> None:
    """The domain restates the persistence enum rather than importing it
    (the Dependency Rule). This is what stops the two drifting apart."""

    from app.domain.document_identity.document_format import ClassifiedFormat
    from app.models.document import DocumentFormat

    assert {member.value for member in ClassifiedFormat} == {
        member.value for member in DocumentFormat
    }
