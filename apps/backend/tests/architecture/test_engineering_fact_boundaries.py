"""
Architecture tests for Engineering Fact Construction (Milestone 29.2).

This is the layer where objects start to be *associated*, which is one
step from a graph edge - so three boundaries carry the weight:

1. **Its inputs are entities and their evidence.** No canonical text, no
   PDF, no document content - not because it currently avoids them, but
   because it imports nothing that could reach them.
2. **It associates; it does not interpret.** One closed predicate, one
   rule catalogue, no ontology, no LLM, no proximity score - and no
   column in which a role or a topology could be recorded.
3. **It writes no graph.** A later milestone will generate edges *from*
   governed facts; this one produces the association and stops.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

FACT_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_facts"
FACT_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "engineering_facts"
FACT_SERVICE = APP_ROOT / "services" / "engineering_fact_service.py"
FACT_ROUTER = APP_ROOT / "routers" / "engineering_facts.py"

CONSTRUCTOR_MODULE = FACT_DOMAIN_ROOT / "fact_constructor.py"
RULES_MODULE = FACT_DOMAIN_ROOT / "fact_construction_rules.py"
PREDICATES_MODULE = FACT_DOMAIN_ROOT / "fact_predicates.py"

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

SIMILARITY_LIBRARIES = (
    "difflib",
    "rapidfuzz",
    "fuzzywuzzy",
    "Levenshtein",
    "jellyfish",
    "numpy",
    "scipy",
    "sklearn",
    "torch",
    "transformers",
    "sentence_transformers",
    "faiss",
    "chromadb",
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


def _fact_surface() -> list[Path]:
    return (
        _python_files(FACT_DOMAIN_ROOT)
        + _python_files(FACT_ADAPTER_ROOT)
        + [FACT_SERVICE, FACT_ROUTER]
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


# --- 1. Entities and evidence are the only inputs -------------------------------


def test_the_fact_context_cannot_import_canonical_text() -> None:
    """Its subject matter is entities. A fact layer that could re-read
    the text would be re-deciding what was observed, in a second place,
    under no rule version."""

    assert _offenders(_fact_surface(), DOCUMENT_MODULES) == []


def test_the_fact_context_cannot_import_a_pdf_library() -> None:
    assert _offenders(_fact_surface(), PDF_LIBRARIES) == []


def test_the_fact_domain_holds_no_infrastructure_dependency() -> None:
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

    assert _offenders(_python_files(FACT_DOMAIN_ROOT), forbidden) == []


def test_the_fact_domain_depends_only_on_entities_and_evidence() -> None:
    """Its whole dependency surface: the entity model it associates, the
    evidence model its support references, and its own modules."""

    permitted_standard_library = {
        "__future__",
        "abc",
        "dataclasses",
        "enum",
        "hashlib",
        "typing",
    }
    offenders: list[str] = []

    for path in _python_files(FACT_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in permitted_standard_library:
                continue

            if module.startswith("app.domain.engineering_facts."):
                continue

            if module.startswith("app.domain.engineering_entities."):
                continue

            if module.startswith("app.domain.engineering_evidence."):
                continue

            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
            )

    assert offenders == []


def test_the_constructor_is_a_pure_function() -> None:
    forbidden = ("datetime", "time", "random", "uuid", "os", "secrets")

    assert _offenders(
        [CONSTRUCTOR_MODULE, RULES_MODULE, PREDICATES_MODULE], forbidden
    ) == []


def test_the_service_invokes_no_extractor_and_resolves_no_entities(
) -> None:
    """It orchestrates repositories. Running the extractor or the
    resolver here would put a second copy of those pipelines in the
    application layer."""

    forbidden = (
        "app.domain.engineering_evidence.evidence_extractor",
        "app.domain.engineering_entities.entity_resolver",
        "app.services.engineering_evidence_service",
        "app.services.engineering_entity_service",
    )

    assert _offenders([FACT_SERVICE, FACT_ROUTER], forbidden) == []


# --- 2. It associates; it does not interpret ------------------------------------


def test_the_fact_context_cannot_import_the_llm_runtime() -> None:
    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.services.ai",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
    )

    assert _offenders(_fact_surface(), forbidden) == []


def test_the_fact_context_cannot_import_prompt_builder() -> None:
    forbidden = (
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
        "app.services.context_builder_service",
    )

    assert _offenders(_fact_surface(), forbidden) == []


def test_the_fact_context_cannot_import_the_engineering_engine() -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.engineering_intent",
        "app.domain.engineering_response",
        "app.domain.structured_retrieval",
    )

    assert _offenders(_fact_surface(), forbidden) == []


def test_the_fact_context_cannot_import_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_fact_surface(), forbidden) == []


def test_the_fact_context_cannot_write_the_knowledge_graph() -> None:
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

    assert _offenders(_fact_surface(), forbidden) == []


def test_the_fact_context_cannot_import_ontology_classification() -> None:
    """Deciding that ``TR1`` is a transformer, or that ``630 kVA`` is its
    rated power, needs a reviewed rule and a governed vocabulary. An
    ontology lookup here would smuggle one in."""

    forbidden = (
        "app.domain.ontology",
        "app.services.ontology",
        "app.domain.electrical_ontology",
    )

    assert _offenders(_fact_surface(), forbidden) == []


def test_no_similarity_or_embedding_dependency_exists() -> None:
    """
    No fuzzy matcher, no distance metric, no vector library.

    Two entities are associated because a declared structural rule was
    satisfied, or they are not. A proximity score would be a number
    nobody calibrated deciding which equipment a rating belongs to.
    """

    assert _offenders(_fact_surface(), SIMILARITY_LIBRARIES) == []


def test_no_proximity_scoring_appears_in_the_rules() -> None:
    """Asserted on the syntax tree: no distance, score or threshold name
    is computed anywhere in the construction path."""

    suspicious = {
        "distance",
        "score",
        "threshold",
        "similarity",
        "nearest",
        "proximity",
        "closest",
    }
    offenders: list[str] = []

    for path in (CONSTRUCTOR_MODULE, RULES_MODULE, PREDICATES_MODULE):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            name = (
                node.id
                if isinstance(node, ast.Name)
                else node.attr
                if isinstance(node, ast.Attribute)
                else node.arg
                if isinstance(node, ast.arg)
                else ""
            )

            if any(word in name.lower() for word in suspicious):
                offenders.append(
                    f"{path.relative_to(APP_ROOT.parent)} uses '{name}'"
                )

    assert offenders == []


def test_the_predicate_vocabulary_is_closed_and_declared_once() -> None:
    """
    One module declares predicates, and it declares exactly one.

    A second predicate enum **inside this context** would let a fact
    assert something nobody reviewed - and every stored fact cites a
    predicate.

    Scoped to the fact context on purpose: older bounded contexts
    (canonicalization, proposed claims) have predicate concepts of their
    own that predate this milestone and mean something else. This test is
    about facts having exactly one vocabulary, not about the word being
    reserved repository-wide.
    """

    from app.domain.engineering_facts.fact_predicates import FactPredicate

    assert [member.name for member in FactPredicate] == [
        "HAS_ASSOCIATED_QUANTITY"
    ]

    declaring: list[str] = []

    for path in _fact_surface():
        if path == PREDICATES_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Predicate" in node.name:
                declaring.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert declaring == []


def test_all_executable_rules_live_in_one_catalogue() -> None:
    """A rule constructed outside the catalogue would be a rule nobody
    could find or version - while every stored fact cites a rule
    version."""

    from app.domain.engineering_facts.fact_construction_rules import (
        CONSTRUCTION_RULES,
        RULES_BY_ID,
    )

    assert len(RULES_BY_ID) == len(CONSTRUCTION_RULES)
    for rule in CONSTRUCTION_RULES:
        assert rule.rule_id
        assert rule.rule_version

    declaring: list[str] = []

    for path in _fact_surface():
        if path == RULES_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "FactConstructionRule"
            ):
                declaring.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert declaring == []


def test_the_fact_schema_has_nowhere_to_record_a_role_or_topology(
) -> None:
    """
    Asserted on the persisted columns, because a column is how a
    judgement would actually survive.

    ``HAS_ASSOCIATED_QUANTITY`` says two entities appeared together. A
    ``role`` or ``rated_value`` column would let a later change quietly
    turn that into a property claim.
    """

    from app.models.engineering_facts import (
        EngineeringFactRecord,
        EngineeringFactSetRecord,
        EngineeringFactSupportRecord,
        FactConstructionDiagnosticRecord,
    )

    forbidden = {
        "role_name",
        "property_name",
        "property",
        "rated_value",
        "rated_power",
        "equipment_type",
        "entity_class",
        "connected_to",
        "protects",
        "feeds",
        "belongs_to",
        "topology",
        "node_id",
        "edge_id",
        "confidence",
        "score",
    }
    columns = {
        column.name
        for model in (
            EngineeringFactSetRecord,
            EngineeringFactRecord,
            EngineeringFactSupportRecord,
            FactConstructionDiagnosticRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


def test_diagnostics_are_stored_apart_from_facts() -> None:
    """An ambiguous pairing must be structurally invisible to anyone
    querying facts - which is why it is its own table with no subject and
    no object column."""

    from app.models.engineering_facts import (
        FactConstructionDiagnosticRecord,
    )

    columns = {
        column.name
        for column in FactConstructionDiagnosticRecord.__table__.columns
    }

    assert FactConstructionDiagnosticRecord.__tablename__ != (
        "engineering_facts"
    )
    assert "subject_entity_key" not in columns
    assert "object_entity_key" not in columns
    assert "predicate" not in columns
    assert "status" not in columns


# --- 3. Boundaries upstream and downstream --------------------------------------------


def test_entity_resolution_cannot_import_the_fact_context() -> None:
    """Entity resolution must remain unaware of facts."""

    forbidden = (
        "app.domain.engineering_facts",
        "app.services.engineering_fact_service",
        "app.infrastructure.engineering_facts",
        "app.models.engineering_facts",
    )
    entity_surface = (
        _python_files(DOMAIN_ROOT / "engineering_entities")
        + _python_files(APP_ROOT / "infrastructure" / "engineering_entities")
        + [APP_ROOT / "services" / "engineering_entity_service.py"]
    )

    assert _offenders(entity_surface, forbidden) == []


def test_evidence_extraction_is_unaware_of_entities_and_facts() -> None:
    """Evidence must remain unaware of both layers above it."""

    forbidden = (
        "app.domain.engineering_entities",
        "app.domain.engineering_facts",
        "app.services.engineering_entity_service",
        "app.services.engineering_fact_service",
        "app.infrastructure.engineering_entities",
        "app.infrastructure.engineering_facts",
        "app.models.engineering_entities",
        "app.models.engineering_facts",
    )
    evidence_surface = (
        _python_files(DOMAIN_ROOT / "engineering_evidence")
        + _python_files(APP_ROOT / "infrastructure" / "engineering_evidence")
        + [APP_ROOT / "services" / "engineering_evidence_service.py"]
    )

    assert _offenders(evidence_surface, forbidden) == []


def test_the_repository_port_is_insert_only() -> None:
    """No ``update`` and no ``delete``: a new rule version produces a new
    fact set, and overwriting one would destroy the history that makes a
    historical fact explainable."""

    from app.domain.engineering_facts.engineering_fact_repository import (
        EngineeringFactRepository,
    )

    assert set(EngineeringFactRepository.__abstractmethods__) == {
        "save",
        "find_for_source",
        "find_latest_for_document",
    }


def test_entities_are_referenced_by_key_not_by_foreign_key() -> None:
    """
    Fact history must survive a newer entity set.

    A foreign key into ``engineering_entities`` would either block a
    re-resolution or cascade a historical fact set into nothing.
    """

    from app.models.engineering_facts import EngineeringFactRecord

    for column_name in ("subject_entity_key", "object_entity_key"):
        column = EngineeringFactRecord.__table__.columns[column_name]

        assert column.foreign_keys == set()


def test_the_fact_adapter_never_writes_entities_or_evidence() -> None:
    adapter = (
        FACT_ADAPTER_ROOT / "sqlalchemy_engineering_fact_repository.py"
    )
    forbidden = (
        "app.models.engineering_entities",
        "app.models.engineering_evidence",
        "app.models.document",
        "app.infrastructure.engineering_entities",
        "app.infrastructure.engineering_evidence",
    )

    assert _offenders([adapter], forbidden) == []


def test_no_knowledge_graph_module_imports_the_fact_context() -> None:
    """
    The Knowledge Graph does **not** consume facts yet - populating it is
    a later milestone.

    Pinned so that when it does, the change is deliberate: an import
    appearing without that milestone would mean graph population had
    quietly acquired a source nobody governed.
    """

    forbidden = ("app.domain.engineering_facts",)
    graph_surface = [
        path
        for path in _python_files(APP_ROOT / "services")
        if path.name in ("knowledge_graph.py", "entity_extractor.py")
    ] + _python_files(APP_ROOT / "services" / "ai")

    assert _offenders(graph_surface, forbidden) == []
