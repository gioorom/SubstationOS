"""
Architecture tests for Engineering Evidence Extraction (Milestone 28.1).

This context is the first in the system that reads a document *for
meaning*, which makes three boundaries load-bearing:

1. **Its only input is canonical text.** No PDF library, no content port,
   no filesystem - not because it currently avoids them, but because it
   imports nothing that could reach them.
2. **It observes and concludes nothing.** No LLM, no Prompt Builder, no
   Engineering Engine, no Engineering Index write, no Knowledge Graph
   write, and no column anywhere in which an entity or a relationship
   could be recorded.
3. **Its rules are findable.** One pattern catalogue, one unit
   catalogue, one rule catalogue - so a matching decision can never be
   made by a private regex somebody added to a service.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

EVIDENCE_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_evidence"
EVIDENCE_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "engineering_evidence"
EVIDENCE_SERVICE = APP_ROOT / "services" / "engineering_evidence_service.py"
EVIDENCE_ROUTER = APP_ROOT / "routers" / "engineering_evidence.py"

PATTERNS_MODULE = EVIDENCE_DOMAIN_ROOT / "evidence_patterns.py"
UNITS_MODULE = EVIDENCE_DOMAIN_ROOT / "evidence_units.py"
RULES_MODULE = EVIDENCE_DOMAIN_ROOT / "evidence_rules.py"
EXTRACTOR_MODULE = EVIDENCE_DOMAIN_ROOT / "evidence_extractor.py"

PDF_LIBRARIES = ("fitz", "pymupdf", "pypdf", "PyPDF2", "pdfplumber", "pdfminer")

RAW_CONTENT_MODULES = (
    "app.domain.document_identity.document_content_port",
    "app.domain.document_identity.document_storage_location",
    "app.infrastructure.document_identity",
    "app.services.storage",
    "app.infrastructure.canonical_pdf",
    "app.domain.canonical_pdf.pdf_parser_port",
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


def _evidence_surface() -> list[Path]:
    """Every module of this context - domain, adapter, service, router."""

    return (
        _python_files(EVIDENCE_DOMAIN_ROOT)
        + _python_files(EVIDENCE_ADAPTER_ROOT)
        + [EVIDENCE_SERVICE, EVIDENCE_ROUTER]
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


# --- 1. Canonical text is the only input -----------------------------------


def test_evidence_extraction_cannot_import_a_pdf_library() -> None:
    """The document was decoded once, three milestones ago. A PDF library
    here would be a second decoding path, and this context would start
    disagreeing with the canonical representation about what a document
    says."""

    assert _offenders(_evidence_surface(), PDF_LIBRARIES) == []


def test_evidence_extraction_cannot_access_stored_content() -> None:
    """No content port, no storage-location port, no filesystem adapter,
    no upload storage path, no canonical PDF parser."""

    assert _offenders(_evidence_surface(), RAW_CONTENT_MODULES) == []


def test_the_evidence_domain_holds_no_infrastructure_dependency() -> None:
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

    assert _offenders(_python_files(EVIDENCE_DOMAIN_ROOT), forbidden) == []


def test_the_evidence_domain_depends_only_on_canonical_text() -> None:
    """The domain imports the canonical text models, its own modules and
    a short list of pure standard-library names. That is the whole
    dependency surface of this layer."""

    permitted_standard_library = {
        "__future__",
        "abc",
        "dataclasses",
        "decimal",
        "enum",
        "hashlib",
        "re",
        "typing",
    }
    offenders: list[str] = []

    for path in _python_files(EVIDENCE_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in permitted_standard_library:
                continue

            if module.startswith("app.domain.engineering_evidence."):
                continue

            if module.startswith("app.domain.canonical_text."):
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


def test_the_extractor_is_a_pure_function() -> None:
    """No clock, no randomness, no environment, no I/O - which is what
    makes "the same canonical text always yields the same evidence"
    assertable rather than hoped for."""

    forbidden = ("datetime", "time", "random", "uuid", "os", "secrets")

    assert _offenders([EXTRACTOR_MODULE], forbidden) == []


def test_the_service_constructs_no_parser_and_no_content_adapter() -> None:
    """Asserted on the composition root too: the router builds two
    repositories and nothing else, so there is no route from an HTTP
    request to a document through this endpoint."""

    forbidden = RAW_CONTENT_MODULES + (
        "app.services.canonical_pdf_service",
        "app.services.document_pipeline_service",
    )

    assert _offenders([EVIDENCE_SERVICE, EVIDENCE_ROUTER], forbidden) == []


# --- 2. It observes and concludes nothing ----------------------------------


def test_evidence_extraction_cannot_import_the_llm_runtime() -> None:
    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.services.ai",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.application.services.llm_provider_registry",
        "app.application.models.llm_invocation",
        "app.domain.llm_provider",
    )

    assert _offenders(_evidence_surface(), forbidden) == []


def test_evidence_extraction_cannot_import_prompt_builder() -> None:
    forbidden = (
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
        "app.services.context_builder_service",
    )

    assert _offenders(_evidence_surface(), forbidden) == []


def test_evidence_extraction_cannot_import_the_engineering_engine() -> None:
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

    assert _offenders(_evidence_surface(), forbidden) == []


def test_evidence_extraction_cannot_write_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_evidence_surface(), forbidden) == []


def test_evidence_extraction_cannot_write_the_knowledge_graph() -> None:
    forbidden = (
        "app.services.knowledge_graph",
        "app.services.entity_extractor",
        "app.services.topology",
        "app.models.knowledge_graph",
        "app.domain.project_knowledge_graph",
        "app.domain.graph_builder",
        "app.domain.canonicalization",
        "app.domain.proposed_claims",
        "app.services.graph_builder_service",
        "app.infrastructure.project_knowledge_graph",
    )

    assert _offenders(_evidence_surface(), forbidden) == []


def test_the_evidence_schema_has_nowhere_to_record_an_entity() -> None:
    """
    Asserted on the persisted columns, because a column is how a
    judgement would actually survive.

    Evidence is an observation about a document. Attaching it to an
    entity, or to another observation, is a conclusion - and this
    milestone makes none.
    """

    from app.models.engineering_evidence import (
        EngineeringEvidenceRecord,
        EngineeringEvidenceSetRecord,
        EngineeringEvidenceSpanRecord,
    )

    forbidden = {
        "entity_id",
        "entity_type",
        "equipment_id",
        "equipment_type",
        "belongs_to",
        "related_evidence_id",
        "relationship",
        "relationship_type",
        "node_id",
        "edge_id",
        "parent_id",
        "attribute_id",
        "property_of",
    }
    columns = {
        column.name
        for model in (
            EngineeringEvidenceSetRecord,
            EngineeringEvidenceRecord,
            EngineeringEvidenceSpanRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


def test_quantities_are_stored_exactly_and_never_as_floats() -> None:
    """A rated voltage that read back as 20.000000000000004 kV would be a
    defect nobody could explain to an engineer."""

    from sqlalchemy import Float, Numeric

    from app.models.engineering_evidence import EngineeringEvidenceRecord

    value_columns = [
        column
        for column in EngineeringEvidenceRecord.__table__.columns
        if column.name.startswith("quantity_")
        and column.name.endswith("value")
    ]

    assert value_columns
    for column in value_columns:
        assert isinstance(column.type, Numeric)
        assert not isinstance(column.type, Float)


# --- 3. The rules are findable ---------------------------------------------


def test_only_the_pattern_module_compiles_a_regular_expression() -> None:
    """
    One pattern catalogue.

    A private ``re.compile`` in a service would be a matching rule nobody
    could find, version or review - and every stored evidence item cites
    a rule version, which would then be a lie.
    """

    offenders: list[str] = []

    for path in _evidence_surface():
        if path == PATTERNS_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "compile"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "re"
            ):
                offenders.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert offenders == []


def test_only_the_unit_module_declares_units() -> None:
    """
    One unit catalogue. A second table of unit spellings would let two
    parts of this context disagree about what ``kV`` means.

    Asserted on **construction of a ``UnitDefinition``** rather than on
    names containing "UNIT": ``NUMBER_WITH_UNIT`` is a pattern named for
    what it matches, and a name-based check would confuse the two.
    """

    declaring: list[str] = []

    for path in _evidence_surface():
        if path == UNITS_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "UnitDefinition"
            ):
                declaring.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert declaring == []


def test_only_the_rule_module_declares_rules() -> None:
    from app.domain.engineering_evidence.evidence_rules import (
        EXTRACTION_RULES,
        RULES_BY_ID,
    )

    assert len(RULES_BY_ID) == len(EXTRACTION_RULES)
    for rule in EXTRACTION_RULES:
        assert rule.rule_id
        assert rule.rule_version


def test_no_unit_spelling_appears_outside_the_unit_catalogue() -> None:
    """``kVA`` written as a literal in a second module would be a unit
    policy growing back somewhere else."""

    offenders: list[str] = []
    spellings = ("kVA", "MVA", "mm²")

    for path in _evidence_surface():
        if path == UNITS_MODULE:
            continue

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

        # Docstrings legitimately mention units; only executable string
        # literals are a second policy.
        literals -= {
            ast.get_docstring(node) or ""
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef)
            )
        }

        if any(
            spelling == literal
            for literal in literals
            for spelling in spellings
        ):
            offenders.append(path.relative_to(APP_ROOT.parent).as_posix())

    assert offenders == []


def test_the_extractor_declares_no_pattern_of_its_own() -> None:
    """It orchestrates rules. A raw regex string here would be a matching
    decision made outside the catalogue."""

    source = EXTRACTOR_MODULE.read_text(encoding="utf-8")

    assert "re.compile" not in source
    assert not re.search(r'r"\^', source)


# --- 4. The evidence repository is the downstream boundary ------------------


def test_the_repository_port_exposes_no_canonical_text_internals(
) -> None:
    """
    Asserted on the contract - the abstract method set.

    A future entity-resolution milestone reads evidence through this
    port. A method returning a page, a paragraph, a line or a token would
    invite it to re-derive observations in a second place, under no rule
    version, and two answers about the same document would exist.
    """

    from app.domain.engineering_evidence.engineering_evidence_repository import (  # noqa: E501
        EngineeringEvidenceRepository,
    )

    assert set(
        EngineeringEvidenceRepository.__abstractmethods__
    ) == {
        "save",
        "find_by_identity",
        "find_latest_for_document",
    }


def test_the_evidence_adapter_never_writes_canonical_text() -> None:
    """Evidence is derived *from* canonical text, and deriving something
    must never modify what it was derived from."""

    adapter = (
        EVIDENCE_ADAPTER_ROOT
        / "sqlalchemy_engineering_evidence_repository.py"
    )
    forbidden = (
        "app.models.canonical_text",
        "app.models.canonical_pdf",
        "app.models.document",
        "app.infrastructure.canonical_text",
    )

    assert _offenders([adapter], forbidden) == []


def test_canonical_text_does_not_depend_on_evidence() -> None:
    """The dependency runs one way: evidence consumes canonical text,
    never the reverse."""

    forbidden = (
        "app.domain.engineering_evidence",
        "app.services.engineering_evidence_service",
        "app.infrastructure.engineering_evidence",
        "app.models.engineering_evidence",
    )
    canonical_surface = (
        _python_files(DOMAIN_ROOT / "canonical_text")
        + _python_files(APP_ROOT / "infrastructure" / "canonical_text")
        + [APP_ROOT / "services" / "canonical_text_service.py"]
    )

    assert _offenders(canonical_surface, forbidden) == []


def test_no_knowledge_graph_module_imports_the_evidence_context() -> None:
    """
    The Knowledge Graph does **not** consume evidence yet - migrating it
    is a later milestone, and its current ad-hoc path remains recorded
    debt.

    Pinned here so that when it does, the change is deliberate: an import
    appearing without that milestone would mean graph population had
    quietly acquired a second source of truth.
    """

    forbidden = ("app.domain.engineering_evidence",)
    graph_surface = [
        path
        for path in _python_files(APP_ROOT / "services")
        if path.name in ("knowledge_graph.py", "entity_extractor.py")
    ] + _python_files(APP_ROOT / "services" / "ai")

    assert _offenders(graph_surface, forbidden) == []
