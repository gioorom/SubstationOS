"""
Architecture tests for Engineering Semantic Interpretation
(Milestone 30.1).

This is where the pipeline finally assigns engineering meaning, which
makes one boundary decisive: **only Engineering Facts cross into this
layer.** Everything it could otherwise reach - canonical text, evidence,
entities, the extractor - would let it re-derive what a document contains
in a second place, under no rule version.

Two further properties hold it in shape: every engineering judgement
lives in one catalogue, and nothing here writes a graph.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

SEMANTIC_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_semantics"
SEMANTIC_ADAPTER_ROOT = (
    APP_ROOT / "infrastructure" / "engineering_semantics"
)
SEMANTIC_SERVICE = (
    APP_ROOT / "services" / "engineering_semantic_service.py"
)
SEMANTIC_ROUTER = APP_ROOT / "routers" / "engineering_semantics.py"

INTERPRETER_MODULE = SEMANTIC_DOMAIN_ROOT / "semantic_interpreter.py"
RULES_MODULE = SEMANTIC_DOMAIN_ROOT / "semantic_rules.py"
TYPES_MODULE = SEMANTIC_DOMAIN_ROOT / "semantic_statement_types.py"

PDF_LIBRARIES = (
    "fitz",
    "pymupdf",
    "pypdf",
    "PyPDF2",
    "pdfplumber",
    "pdfminer",
)

# Everything below Engineering Facts. The semantic layer may reach none
# of it: facts are the only thing that crosses the boundary.
UPSTREAM_MODULES = (
    "app.domain.canonical_text",
    "app.domain.canonical_pdf",
    "app.infrastructure.canonical_text",
    "app.infrastructure.canonical_pdf",
    "app.services.canonical_text_service",
    "app.services.canonical_pdf_service",
    "app.services.document_pipeline_service",
    "app.domain.engineering_evidence",
    "app.infrastructure.engineering_evidence",
    "app.services.engineering_evidence_service",
    "app.domain.engineering_entities",
    "app.infrastructure.engineering_entities",
    "app.services.engineering_entity_service",
    "app.domain.document_identity",
    "app.infrastructure.document_identity",
    "app.services.storage",
)

ML_LIBRARIES = (
    "numpy",
    "scipy",
    "sklearn",
    "torch",
    "transformers",
    "sentence_transformers",
    "faiss",
    "chromadb",
    "difflib",
    "rapidfuzz",
    "fuzzywuzzy",
    "Levenshtein",
    "random",
    "statistics",
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


def _semantic_surface() -> list[Path]:
    return (
        _python_files(SEMANTIC_DOMAIN_ROOT)
        + _python_files(SEMANTIC_ADAPTER_ROOT)
        + [SEMANTIC_SERVICE, SEMANTIC_ROUTER]
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


# --- 1. Only Engineering Facts cross the boundary --------------------------------


def test_the_semantic_layer_cannot_import_canonical_text_or_pdf() -> None:
    forbidden = (
        "app.domain.canonical_text",
        "app.domain.canonical_pdf",
        "app.infrastructure.canonical_text",
        "app.infrastructure.canonical_pdf",
        "app.services.canonical_text_service",
        "app.services.canonical_pdf_service",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_import_a_pdf_library() -> None:
    assert _offenders(_semantic_surface(), PDF_LIBRARIES) == []


def test_the_semantic_layer_cannot_import_evidence_or_extraction(
) -> None:
    """
    Including the evidence *vocabulary*.

    The rule needs to know a quantity is a power, and reads that from the
    evidence type Milestone 29.2 recorded **on the fact's support** - as
    a declared string, never by importing the enum. A test in
    ``test_semantic_interpreter`` asserts the string still matches
    ``EvidenceType.POWER_VALUE``, so the two cannot drift while the
    dependency stays absent.
    """

    forbidden = (
        "app.domain.engineering_evidence",
        "app.infrastructure.engineering_evidence",
        "app.services.engineering_evidence_service",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_reach_entity_resolution() -> None:
    """A statement names entities by key. Reading an entity would let
    this layer see a quantity's value - and it deliberately cannot, which
    is why two competing powers produce no statement."""

    forbidden = (
        "app.domain.engineering_entities",
        "app.infrastructure.engineering_entities",
        "app.services.engineering_entity_service",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_domain_depends_only_on_facts() -> None:
    """Its whole dependency surface: the fact model it interprets, and
    its own modules."""

    permitted_standard_library = {
        "__future__",
        "abc",
        "dataclasses",
        "enum",
        "hashlib",
        "typing",
    }
    offenders: list[str] = []

    for path in _python_files(SEMANTIC_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in permitted_standard_library:
                continue

            if module.startswith("app.domain.engineering_semantics."):
                continue

            if module.startswith("app.domain.engineering_facts."):
                continue

            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
            )

    assert offenders == []


def test_the_semantic_domain_holds_no_infrastructure_dependency(
) -> None:
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

    assert _offenders(_python_files(SEMANTIC_DOMAIN_ROOT), forbidden) == []


def test_the_service_reconstructs_nothing_upstream() -> None:
    """It loads a fact set. Running the extractor, the resolver or the
    constructor here would put a second copy of those pipelines in the
    application layer."""

    forbidden = UPSTREAM_MODULES + (
        "app.domain.engineering_facts.fact_constructor",
        "app.services.engineering_fact_service",
    )

    assert _offenders([SEMANTIC_SERVICE, SEMANTIC_ROUTER], forbidden) == []


# --- 2. It interprets by declared rule, not by inference ---------------------------


def test_the_semantic_layer_cannot_import_the_llm_runtime() -> None:
    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.services.ai",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_import_prompt_builder() -> None:
    forbidden = (
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
        "app.services.context_builder_service",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_import_the_engineering_engine(
) -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.engineering_intent",
        "app.domain.engineering_response",
        "app.domain.structured_retrieval",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_import_ontology_classification(
) -> None:
    """The meaning it assigns comes from its own catalogue. An ontology
    lookup would import an engineering judgement from outside the
    versioned rules every statement cites."""

    forbidden = (
        "app.domain.ontology",
        "app.services.ontology",
        "app.domain.electrical_ontology",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_no_machine_learning_or_probabilistic_dependency_exists(
) -> None:
    """No model, no embedding, no distance metric, no sampling. Meaning
    is assigned by a declared rule or not at all."""

    assert _offenders(_semantic_surface(), ML_LIBRARIES) == []


def test_the_semantic_layer_cannot_write_the_knowledge_graph() -> None:
    """Semantic Interpretation assigns meaning; the Knowledge Graph
    stores interpreted knowledge; reasoning consumes it. Three
    responsibilities, three milestones."""

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

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_semantic_layer_cannot_write_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_semantic_surface(), forbidden) == []


def test_the_interpreter_is_a_pure_function() -> None:
    forbidden = ("datetime", "time", "random", "uuid", "os", "secrets")

    assert _offenders(
        [INTERPRETER_MODULE, RULES_MODULE, TYPES_MODULE], forbidden
    ) == []


# --- 3. One catalogue, one closed vocabulary ----------------------------------------


def test_the_statement_vocabulary_is_closed_and_declared_once() -> None:
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )

    assert [member.name for member in SemanticStatementType] == [
        "HAS_RATED_POWER",
        "IS_LOCATED_IN",
    ]

    declaring: list[str] = []

    for path in _semantic_surface():
        if path == TYPES_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                "StatementType" in node.name
            ):
                declaring.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert declaring == []


def test_no_executable_engineering_rule_exists_outside_the_catalogue(
) -> None:
    """A rule constructed anywhere else would be an engineering judgement
    nobody could find or version - while every stored statement cites a
    rule version."""

    from app.domain.engineering_semantics.semantic_rules import (
        RULES_BY_ID,
        SEMANTIC_RULES,
    )

    assert len(RULES_BY_ID) == len(SEMANTIC_RULES)
    for rule in SEMANTIC_RULES:
        assert rule.rule_id
        assert rule.rule_version

    declaring: list[str] = []

    for path in _semantic_surface():
        if path == RULES_MODULE:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "SemanticRule"
            ):
                declaring.append(
                    path.relative_to(APP_ROOT.parent).as_posix()
                )

    assert declaring == []


def test_the_statement_schema_records_no_value_or_classification(
) -> None:
    """
    Asserted on the persisted columns.

    A statement says what an association *means*. The figure lives on the
    quantity entity; an equipment class is a judgement nothing here
    makes. A ``value`` column would be a second source of truth for a
    rated value - the worst possible thing to have two of.
    """

    from app.models.engineering_semantics import (
        EngineeringSemanticSetRecord,
        EngineeringSemanticStatementRecord,
        SemanticInterpretationDiagnosticRecord,
        SemanticStatementSupportRecord,
    )

    forbidden = {
        "value",
        "unit",
        "rated_value",
        "quantity_value",
        "equipment_type",
        "entity_class",
        "confidence",
        "score",
        "probability",
        "connected_to",
        "topology",
        "node_id",
        "edge_id",
    }
    columns = {
        column.name
        for model in (
            EngineeringSemanticSetRecord,
            EngineeringSemanticStatementRecord,
            SemanticStatementSupportRecord,
            SemanticInterpretationDiagnosticRecord,
        )
        for column in model.__table__.columns
    }

    assert columns & forbidden == set()


def test_diagnostics_are_stored_apart_from_statements() -> None:
    """An undecided meaning must be structurally invisible to anyone
    querying interpreted knowledge."""

    from app.models.engineering_semantics import (
        SemanticInterpretationDiagnosticRecord,
    )

    columns = {
        column.name
        for column in (
            SemanticInterpretationDiagnosticRecord.__table__.columns
        )
    }

    assert SemanticInterpretationDiagnosticRecord.__tablename__ != (
        "engineering_semantic_statements"
    )
    assert "object_entity_key" not in columns
    assert "statement_type" not in columns
    assert "status" not in columns


# --- 4. Boundaries upstream and downstream -------------------------------------------


def test_fact_construction_cannot_import_the_semantic_layer() -> None:
    """The dependency runs one way: semantics consume facts, never the
    reverse."""

    forbidden = (
        "app.domain.engineering_semantics",
        "app.services.engineering_semantic_service",
        "app.infrastructure.engineering_semantics",
        "app.models.engineering_semantics",
    )
    fact_surface = (
        _python_files(DOMAIN_ROOT / "engineering_facts")
        + _python_files(APP_ROOT / "infrastructure" / "engineering_facts")
        + [APP_ROOT / "services" / "engineering_fact_service.py"]
    )

    assert _offenders(fact_surface, forbidden) == []


def test_the_lower_layers_remain_unaware_of_semantics() -> None:
    forbidden = ("app.domain.engineering_semantics",)
    lower = (
        _python_files(DOMAIN_ROOT / "engineering_evidence")
        + _python_files(DOMAIN_ROOT / "engineering_entities")
        + _python_files(DOMAIN_ROOT / "canonical_text")
        + _python_files(DOMAIN_ROOT / "canonical_pdf")
    )

    assert _offenders(lower, forbidden) == []


def test_the_repository_port_is_insert_only() -> None:
    from app.domain.engineering_semantics.engineering_semantic_repository import (  # noqa: E501
        EngineeringSemanticRepository,
    )

    assert set(
        EngineeringSemanticRepository.__abstractmethods__
    ) == {
        "save",
        "find_for_source",
        "find_latest_for_document",
    }


def test_entities_and_facts_are_referenced_by_key_not_foreign_key(
) -> None:
    """A re-resolution or re-construction upstream produces new sets; a
    foreign key would either block that or cascade a historical
    interpretation into nothing."""

    from app.models.engineering_semantics import (
        EngineeringSemanticStatementRecord,
        SemanticStatementSupportRecord,
    )

    for column_name in ("subject_entity_key", "object_entity_key"):
        column = EngineeringSemanticStatementRecord.__table__.columns[
            column_name
        ]

        assert column.foreign_keys == set()

    assert (
        SemanticStatementSupportRecord.__table__.columns[
            "fact_key"
        ].foreign_keys
        == set()
    )


def test_the_semantic_adapter_writes_only_semantic_tables() -> None:
    adapter = (
        SEMANTIC_ADAPTER_ROOT
        / "sqlalchemy_engineering_semantic_repository.py"
    )
    forbidden = (
        "app.models.engineering_facts",
        "app.models.engineering_entities",
        "app.models.engineering_evidence",
        "app.models.document",
        "app.infrastructure.engineering_facts",
    )

    assert _offenders([adapter], forbidden) == []


def test_no_knowledge_graph_module_imports_the_semantic_layer() -> None:
    """
    The Knowledge Graph does **not** consume statements yet - populating
    it is the next milestone.

    Pinned so that when it does, the change is deliberate: an import
    appearing without that milestone would mean graph population had
    acquired a source nobody governed.
    """

    forbidden = ("app.domain.engineering_semantics",)
    graph_surface = [
        path
        for path in _python_files(APP_ROOT / "services")
        if path.name in ("knowledge_graph.py", "entity_extractor.py")
    ] + _python_files(APP_ROOT / "services" / "ai")

    assert _offenders(graph_surface, forbidden) == []
