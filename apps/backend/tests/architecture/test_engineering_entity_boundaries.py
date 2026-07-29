"""
Architecture tests for Engineering Entity Resolution (Milestone 29.1).

This is the layer where a document stops being text and starts being
*objects*, which makes three boundaries load-bearing:

1. **Its only input is engineering evidence.** No canonical text, no
   PDF, no document storage - not because it currently avoids them, but
   because it imports nothing that could reach them.
2. **It groups; it does not reason.** No relationship, no topology, no
   equipment classification, no LLM - and no column anywhere in which any
   of them could be recorded.
3. **It writes no graph.** A later milestone will generate nodes *from*
   entities; this one produces the hypothesis and stops.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

ENTITY_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_entities"
ENTITY_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "engineering_entities"
ENTITY_SERVICE = APP_ROOT / "services" / "engineering_entity_service.py"
ENTITY_ROUTER = APP_ROOT / "routers" / "engineering_entities.py"

RESOLVER_MODULE = ENTITY_DOMAIN_ROOT / "entity_resolver.py"
RULES_MODULE = ENTITY_DOMAIN_ROOT / "entity_resolution_rules.py"

PDF_LIBRARIES = (
    "fitz",
    "pymupdf",
    "pypdf",
    "PyPDF2",
    "pdfplumber",
    "pdfminer",
)

DOCUMENT_MODULES = (
    "app.domain.canonical_text",
    "app.domain.canonical_pdf",
    "app.infrastructure.canonical_text",
    "app.infrastructure.canonical_pdf",
    "app.services.canonical_text_service",
    "app.services.canonical_pdf_service",
    "app.services.document_pipeline_service",
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


def _entity_surface() -> list[Path]:
    return (
        _python_files(ENTITY_DOMAIN_ROOT)
        + _python_files(ENTITY_ADAPTER_ROOT)
        + [ENTITY_SERVICE, ENTITY_ROUTER]
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


# --- 1. Evidence is the only input ---------------------------------------------


def test_entity_resolution_cannot_import_a_pdf_library() -> None:
    assert _offenders(_entity_surface(), PDF_LIBRARIES) == []


def test_entity_resolution_cannot_reach_canonical_text_or_a_document(
) -> None:
    """
    The boundary the milestone brief names first.

    Resolution operates only on evidence. It cannot inspect canonical
    text and cannot reopen a document - and it imports nothing that
    could, which makes that a structural fact rather than a promise.
    """

    assert _offenders(_entity_surface(), DOCUMENT_MODULES) == []


def test_the_entity_domain_holds_no_infrastructure_dependency() -> None:
    forbidden = (
        "os",
        "pathlib",
        "shutil",
        "yaml",
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

    assert _offenders(_python_files(ENTITY_DOMAIN_ROOT), forbidden) == []


def test_the_entity_domain_depends_only_on_evidence() -> None:
    """Its whole dependency surface: the evidence model it groups, and
    its own modules."""

    permitted_standard_library = {
        "__future__",
        "abc",
        "dataclasses",
        "decimal",
        "enum",
        "hashlib",
        "typing",
    }
    offenders: list[str] = []

    for path in _python_files(ENTITY_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in permitted_standard_library:
                continue

            if module.startswith("app.domain.engineering_entities."):
                continue

            if module.startswith("app.domain.engineering_evidence."):
                continue

            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
            )

    assert offenders == []


def test_the_resolver_is_a_pure_function() -> None:
    """No clock, no randomness, no environment, no I/O - which is what
    makes "the same evidence always resolves the same way" assertable
    rather than hoped for."""

    forbidden = ("datetime", "time", "random", "uuid", "os", "secrets")

    assert _offenders([RESOLVER_MODULE, RULES_MODULE], forbidden) == []


def test_the_service_constructs_no_text_or_document_adapter() -> None:
    """Asserted on the composition root too: the router builds two
    repositories and nothing else, so there is no route from an HTTP
    request to a document through this endpoint."""

    assert _offenders([ENTITY_SERVICE, ENTITY_ROUTER], DOCUMENT_MODULES) == []


# --- 2. It groups; it does not reason ------------------------------------------


def test_entity_resolution_cannot_import_the_llm_runtime() -> None:
    """Grouping is by declared key. A model asked whether two
    designations 'look like' the same equipment would make the hypothesis
    unrepeatable and unreviewable."""

    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.services.ai",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
    )

    assert _offenders(_entity_surface(), forbidden) == []


def test_entity_resolution_cannot_write_the_knowledge_graph() -> None:
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
        "app.services.graph_query_service",
        "app.infrastructure.project_knowledge_graph",
    )

    assert _offenders(_entity_surface(), forbidden) == []


def test_entity_resolution_cannot_write_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_entity_surface(), forbidden) == []


def test_entity_resolution_cannot_import_the_engineering_engine() -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.engineering_intent",
        "app.domain.engineering_response",
        "app.domain.structured_retrieval",
    )

    assert _offenders(_entity_surface(), forbidden) == []


def test_entity_resolution_never_consults_the_ontology() -> None:
    """Deciding that ``T1`` names a transformer is a classification
    needing a reviewed rule and a governed vocabulary. An ontology lookup
    here would smuggle one in."""

    forbidden = ("app.domain.ontology", "app.services.ontology")

    assert _offenders(_entity_surface(), forbidden) == []


def test_the_entity_schema_has_nowhere_to_record_a_relationship() -> None:
    """
    Asserted on the persisted columns, because a column is how a
    judgement would actually survive.

    An entity says "these observations refer to one object". Saying what
    it does, what it belongs to, or what its properties are would be
    reasoning - and this milestone performs none.
    """

    from app.models.engineering_entities import (
        EngineeringEntityEvidenceRecord,
        EngineeringEntityRecord,
        EngineeringEntitySetRecord,
    )

    forbidden = {
        "feeds",
        "feeds_entity_id",
        "protects",
        "protects_entity_id",
        "belongs_to",
        "bay_id",
        "parent_entity_id",
        "parent_id",
        "child_entity_id",
        "relationship",
        "relationship_type",
        "equipment_type",
        "entity_class",
        "topology",
        "node_id",
        "edge_id",
        "rated_voltage",
        "properties",
    }
    columns = {
        column.name
        for model in (
            EngineeringEntitySetRecord,
            EngineeringEntityRecord,
            EngineeringEntityEvidenceRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


def test_the_entity_catalogue_names_no_equipment_class() -> None:
    """No transformer, breaker, CT, VT, relay or cable. Naming those
    classes would let the shape of the model imply knowledge the system
    does not have."""

    from app.domain.engineering_entities.entity_models import EntityType

    assert {member.value for member in EntityType} == {
        "equipment_designation",
        "engineering_quantity",
    }


def test_quantities_are_stored_exactly_and_never_as_floats() -> None:
    from sqlalchemy import Float, Numeric

    from app.models.engineering_entities import EngineeringEntityRecord

    value_columns = [
        column
        for column in EngineeringEntityRecord.__table__.columns
        if column.name.startswith("quantity_")
        and column.name.endswith("value")
    ]

    assert value_columns
    for column in value_columns:
        assert isinstance(column.type, Numeric)
        assert not isinstance(column.type, Float)


# --- 3. Boundaries downstream and upstream --------------------------------------


def test_the_repository_port_exposes_no_document_internals() -> None:
    """
    Asserted on the contract - the abstract method set.

    A future Knowledge Graph population milestone reads entities through
    this port. A method returning canonical text, a token or a document
    would invite it to re-derive what an engineering object is, in a
    second place, under no rule version.
    """

    from app.domain.engineering_entities.engineering_entity_repository import (  # noqa: E501
        EngineeringEntityRepository,
    )

    assert set(
        EngineeringEntityRepository.__abstractmethods__
    ) == {
        "save",
        "find_for_source",
        "find_latest_for_document",
    }


def test_the_entity_adapter_never_writes_evidence() -> None:
    """Entities are resolved *from* evidence, and resolving something
    must never modify what it was resolved from."""

    adapter = (
        ENTITY_ADAPTER_ROOT
        / "sqlalchemy_engineering_entity_repository.py"
    )
    forbidden = (
        "app.models.engineering_evidence",
        "app.models.canonical_text",
        "app.models.document",
        "app.infrastructure.engineering_evidence",
    )

    assert _offenders([adapter], forbidden) == []


def test_evidence_does_not_depend_on_entities() -> None:
    """The dependency runs one way: entities consume evidence, never the
    reverse."""

    forbidden = (
        "app.domain.engineering_entities",
        "app.services.engineering_entity_service",
        "app.infrastructure.engineering_entities",
        "app.models.engineering_entities",
    )
    evidence_surface = (
        _python_files(DOMAIN_ROOT / "engineering_evidence")
        + _python_files(APP_ROOT / "infrastructure" / "engineering_evidence")
        + [APP_ROOT / "services" / "engineering_evidence_service.py"]
    )

    assert _offenders(evidence_surface, forbidden) == []


def test_no_knowledge_graph_module_imports_the_entity_context() -> None:
    """
    The Knowledge Graph does **not** consume entities yet - populating it
    is a later milestone, and its current ad-hoc path remains recorded
    debt.

    Pinned here so that when it does, the change is deliberate: an import
    appearing without that milestone would mean graph population had
    quietly acquired a second source of truth.
    """

    forbidden = ("app.domain.engineering_entities",)
    graph_surface = [
        path
        for path in _python_files(APP_ROOT / "services")
        if path.name in ("knowledge_graph.py", "entity_extractor.py")
    ] + _python_files(APP_ROOT / "services" / "ai")

    assert _offenders(graph_surface, forbidden) == []


def test_the_resolution_rules_have_one_authoritative_catalogue() -> None:
    from app.domain.engineering_entities.entity_resolution_rules import (
        RESOLUTION_RULES,
        RULES_BY_ID,
    )

    assert len(RULES_BY_ID) == len(RESOLUTION_RULES)
    for rule in RESOLUTION_RULES:
        assert rule.rule_id
        assert rule.rule_version


def test_the_resolver_declares_no_grouping_key_of_its_own() -> None:
    """Grouping decisions live in the rule catalogue. A key built inline
    in the resolver would be a rule nobody could find, version or
    review - while every stored entity cites a rule version."""

    imported = _imported_module_names(RESOLVER_MODULE)

    assert (
        "app.domain.engineering_entities.entity_resolution_rules"
        in imported
    )
