"""
Architecture tests for Canonical Text Segmentation (Milestone 27.1).

Segmentation is the layer every future extractor will consume, which
makes two boundaries load-bearing:

1. **Its only input is the Canonical Representation.** It cannot reach
   PDF storage, a PDF library, or the content port - not because it
   currently does not, but because it imports nothing that could. That is
   what guarantees the original PDF is decoded exactly once in this
   system.
2. **It records structure and assigns no meaning.** No LLM, no Prompt
   Builder, no Engineering Engine, no ontology lookup, and no write to
   the Engineering Index or the Knowledge Graph.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

TEXT_DOMAIN_ROOT = DOMAIN_ROOT / "canonical_text"
TEXT_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "canonical_text"
TEXT_SERVICE = APP_ROOT / "services" / "canonical_text_service.py"
TEXT_ROUTER = APP_ROOT / "routers" / "canonical_text.py"

SEGMENTER = TEXT_DOMAIN_ROOT / "canonical_text_segmenter.py"
NORMALIZER = TEXT_DOMAIN_ROOT / "canonical_text_normalization.py"


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


def _text_surface() -> list[Path]:
    """Every module of this context - domain, adapter, service, router."""

    return (
        _python_files(TEXT_DOMAIN_ROOT)
        + _python_files(TEXT_ADAPTER_ROOT)
        + [TEXT_SERVICE, TEXT_ROUTER]
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


# --- 1. The Canonical Representation is the only input --------------------


def test_segmentation_cannot_access_pdf_storage() -> None:
    """No content port, no storage-location port, no storage service, no
    filesystem. The bytes were read exactly once, three milestones ago."""

    forbidden = (
        "os",
        "pathlib",
        "shutil",
        "tempfile",
        "boto3",
        "app.services.storage",
        "app.domain.document_identity.document_content_port",
        "app.domain.document_identity.document_storage_location",
        "app.infrastructure.document_identity",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_cannot_decode_a_pdf() -> None:
    """Not even indirectly. A PDF library here would mean the original
    file is being decoded a second time, under whatever version happens
    to be installed - which is exactly the reproducibility failure
    Milestone 26.1 exists to prevent."""

    forbidden = (
        "fitz",
        "pymupdf",
        "pypdf",
        "PyPDF2",
        "pdfplumber",
        "pdfminer",
        "app.infrastructure.canonical_pdf.pymupdf_parser",
        "app.domain.canonical_pdf.pdf_parser_port",
        # Retired by Milestone 26.2 and asserted gone in
        # test_canonical_pdf_boundaries; kept here so that restoring one
        # cannot quietly become segmentation's dependency.
        "app.services.pdf_text_extractor",
        "app.services.pdf_renderer",
        "app.services.document_analyzer",
        "app.services.intelligence",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_the_segmentation_domain_depends_only_on_the_representation(
) -> None:
    """The domain imports the canonical PDF *models* and its own modules,
    and nothing else. That is the whole dependency surface of this
    layer."""

    offenders: list[str] = []

    for path in _python_files(TEXT_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in ("__future__", "abc", "dataclasses", "enum",
                          "unicodedata", "typing"):
                continue

            if module.startswith("app.domain.canonical_text."):
                continue

            if module.startswith("app.domain.canonical_pdf."):
                continue

            # The shared identity primitive (EPIC 32.E2.4). It knows
            # canonicalisation, hashing and artifact kinds - and nothing
            # about engineering. Every deterministic stage composes its
            # own identity with it, which is what replaced each layer
            # copying the layer above it.
            if module.startswith("app.domain.artifact_identity."):
                continue

            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
            )

    assert offenders == []


def test_the_segmenter_is_a_pure_function_of_the_representation() -> None:
    """No clock, no randomness, no environment, no I/O - which is what
    makes "the same representation always segments the same way"
    assertable rather than merely hoped for."""

    forbidden = (
        "datetime",
        "time",
        "random",
        "uuid",
        "os",
        "pathlib",
        "secrets",
    )

    assert _offenders([SEGMENTER, NORMALIZER], forbidden) == []


def test_the_segmentation_domain_holds_no_infrastructure_dependency(
) -> None:
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

    assert _offenders(_python_files(TEXT_DOMAIN_ROOT), forbidden) == []


def test_the_service_constructs_no_parser_and_no_content_adapter() -> None:
    """Asserted on the composition root too: the router builds two
    repositories and nothing else, so there is no route from an HTTP
    request to the original PDF through this endpoint."""

    forbidden = (
        "app.infrastructure.canonical_pdf.pymupdf_parser",
        "app.infrastructure.document_identity",
        "app.services.canonical_pdf_service",
    )

    assert _offenders([TEXT_SERVICE, TEXT_ROUTER], forbidden) == []


# --- 2. It records structure and assigns no meaning -----------------------


def test_segmentation_cannot_import_the_llm_runtime() -> None:
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

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_cannot_import_prompt_builder() -> None:
    forbidden = (
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
        "app.services.context_builder_service",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_cannot_import_the_engineering_engine() -> None:
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

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_cannot_write_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_cannot_write_the_knowledge_graph() -> None:
    forbidden = (
        "app.domain.project_knowledge_graph",
        "app.domain.graph_builder",
        "app.domain.graph_query",
        "app.domain.canonicalization",
        "app.domain.proposed_claims",
        "app.domain.review_workflow",
        "app.services.knowledge_graph",
        "app.services.graph_builder_service",
        "app.services.canonicalization_service",
        "app.models.knowledge_graph",
        "app.models.project_knowledge_graph",
        "app.infrastructure.project_knowledge_graph",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_segmentation_never_consults_the_ontology() -> None:
    """An ontology lookup during normalisation would turn ``CB`` into
    ``circuit breaker`` - an interpretation wearing a normaliser's
    clothes, and one no reviewer would ever see."""

    forbidden = (
        "app.domain.ontology",
        "app.services.ontology",
        "app.domain.electrical_ontology",
    )

    assert _offenders(_text_surface(), forbidden) == []


def test_the_persisted_segmentation_has_nowhere_to_record_meaning(
) -> None:
    """Asserted on the schema, because a column is how an inference would
    actually survive."""

    from app.models.canonical_text import (
        CanonicalTextDocumentRecord,
        CanonicalTextLineRecord,
        CanonicalTextParagraphRecord,
        CanonicalTextSectionRecord,
        CanonicalTextTokenRecord,
    )

    forbidden = {
        "title",
        "heading",
        "level",
        "kind",
        "label",
        "caption",
        "entity",
        "entity_type",
        "equipment",
        "cable",
        "relationship",
        "is_table",
        "is_list",
        "summary",
        "topic",
    }
    columns = {
        column.name
        for model in (
            CanonicalTextDocumentRecord,
            CanonicalTextSectionRecord,
            CanonicalTextParagraphRecord,
            CanonicalTextLineRecord,
            CanonicalTextTokenRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


# --- 3. Downstream consumes the segmentation ------------------------------


def test_the_repository_port_exposes_no_pdf_structure() -> None:
    """Asserted on the contract - the abstract method set. A method
    returning a page, a block or a bounding box would invite an extractor
    to re-derive structure this layer already settled, and two answers
    about the same document would start to exist."""

    from app.domain.canonical_text.canonical_text_repository import (
        CanonicalTextRepository,
    )

    assert set(CanonicalTextRepository.__abstractmethods__) == {
        "save",
        "find_by_identity",
        "find_latest_for_document",
    }


def test_the_text_repository_never_writes_the_representation() -> None:
    """A segmentation is derived *from* a representation, and deriving
    something must never modify what it was derived from."""

    adapter = TEXT_ADAPTER_ROOT / "sqlalchemy_canonical_text_repository.py"
    forbidden = (
        "app.models.canonical_pdf",
        "app.models.document",
        "app.infrastructure.canonical_pdf",
    )

    assert _offenders([adapter], forbidden) == []


def test_the_canonical_pdf_models_stay_within_their_two_consumers(
) -> None:
    """
    The PDF-shaped value objects are consumed by their own context and by
    segmentation, which exists to translate them into the structure
    everything downstream reads. A future extractor appearing in this
    list would be reading PDF structure directly instead of the
    segmentation - the exact coupling this milestone removes.
    """

    permitted = {
        "app/domain/canonical_pdf",
        "app/domain/canonical_text",
        "app/infrastructure/canonical_pdf",
        "app/services/canonical_pdf_service.py",
        "app/services/canonical_text_service.py",
        "app/schemas/canonical_pdf.py",
        "app/routers/canonical_pdf.py",
        # Its own persistence model, which needs the block-kind enum for
        # a column. Part of the canonical_pdf context, not a consumer of
        # it.
        "app/models/canonical_pdf.py",
        # The reference corpus loader (Milestone 28.2). It *assembles* a
        # representation from known text so the corpus can be segmented
        # by the real segmenter - the opposite direction from an
        # extractor consuming PDF structure. A corpus that hand-built its
        # own tokens would keep passing on the day segmentation changed.
        # It imports no PDF library, asserted in
        # test_evidence_evaluation_boundaries.
        "app/infrastructure/evidence_evaluation/yaml_reference_corpus_repository.py",  # noqa: E501
    }
    importers = {
        path.relative_to(APP_ROOT.parent).as_posix()
        for path in _python_files(APP_ROOT)
        if any(
            _violates(
                module,
                (
                    "app.domain.canonical_pdf.canonical_pdf_models",
                    "app.domain.canonical_pdf.canonical_pdf_factory",
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


def test_canonicalisation_does_not_depend_on_segmentation() -> None:
    """The dependency runs one way: segmentation consumes what
    canonicalisation produced, never the reverse."""

    forbidden = (
        "app.domain.canonical_text",
        "app.services.canonical_text_service",
        "app.infrastructure.canonical_text",
        "app.models.canonical_text",
    )
    canonical_surface = (
        _python_files(DOMAIN_ROOT / "canonical_pdf")
        + _python_files(APP_ROOT / "infrastructure" / "canonical_pdf")
        + [APP_ROOT / "services" / "canonical_pdf_service.py"]
    )

    assert _offenders(canonical_surface, forbidden) == []


# --- 4. Taxonomy agreement -------------------------------------------------


def test_the_shared_failure_code_agrees_with_canonicalisations() -> None:
    """Restated rather than imported - two contexts, two vocabularies -
    and asserted here so they cannot drift apart."""

    from app.domain.canonical_pdf.canonical_pdf_failures import (
        CanonicalizationFailureCode,
    )
    from app.domain.canonical_text.canonical_text_failures import (
        SegmentationFailureCode,
    )

    assert (
        SegmentationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE.value
        == CanonicalizationFailureCode
        .REPRESENTATION_PERSISTENCE_FAILURE.value
    )
