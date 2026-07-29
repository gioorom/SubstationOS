"""
Architecture tests for Engineering Evidence Evaluation (Milestone 28.2).

Evaluation is the thing that decides whether a rule is good enough to
ship. Three properties keep that judgement trustworthy:

1. **It measures the current rules, not stored results.** It executes
   the extractor over a corpus; it does not read the evidence tables.
2. **It cannot touch what it measures.** No write to engineering
   evidence, no write to a corpus, no Knowledge Graph, no Engineering
   Index.
3. **It reaches no document.** No PDF library, no content port, no
   document storage - a corpus is self-contained in the repository, which
   is what lets an evaluation run in CI and mean the same thing next
   year.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

EVALUATION_DOMAIN_ROOT = DOMAIN_ROOT / "evidence_evaluation"
EVALUATION_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "evidence_evaluation"
EVALUATION_SERVICE = APP_ROOT / "services" / "evidence_evaluation_service.py"
EVALUATION_ROUTER = APP_ROOT / "routers" / "evidence_evaluation.py"

CORPUS_ROOT = EVALUATION_DOMAIN_ROOT / "corpora"

PDF_LIBRARIES = (
    "fitz",
    "pymupdf",
    "pypdf",
    "PyPDF2",
    "pdfplumber",
    "pdfminer",
)

DOCUMENT_STORAGE_MODULES = (
    "app.domain.document_identity.document_content_port",
    "app.domain.document_identity.document_storage_location",
    "app.infrastructure.document_identity",
    "app.services.storage",
    "app.infrastructure.canonical_pdf.pymupdf_parser",
    "app.domain.canonical_pdf.pdf_parser_port",
    "app.services.canonical_pdf_service",
    "app.services.document_pipeline_service",
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


def _evaluation_surface() -> list[Path]:
    return (
        _python_files(EVALUATION_DOMAIN_ROOT)
        + _python_files(EVALUATION_ADAPTER_ROOT)
        + [EVALUATION_SERVICE, EVALUATION_ROUTER]
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


# --- 1. It reaches no document -----------------------------------------------


def test_evaluation_cannot_import_a_pdf_library() -> None:
    assert _offenders(_evaluation_surface(), PDF_LIBRARIES) == []


def test_evaluation_cannot_access_document_storage() -> None:
    """A corpus is self-contained in the repository. An evaluation that
    needed a stored document would depend on database state, and would
    stop meaning the same thing the moment that state changed."""

    assert _offenders(_evaluation_surface(), DOCUMENT_STORAGE_MODULES) == []


def test_the_evaluation_domain_holds_no_infrastructure_dependency(
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

    assert _offenders(_python_files(EVALUATION_DOMAIN_ROOT), forbidden) == []


def test_the_evaluation_domain_depends_only_on_evidence_and_text() -> None:
    """Its whole dependency surface: the evidence model it compares
    against, the canonical text type it hands to the extractor, and its
    own modules."""

    permitted_standard_library = {
        "__future__",
        "abc",
        "dataclasses",
        "decimal",
        "enum",
        "typing",
    }
    offenders: list[str] = []

    for path in _python_files(EVALUATION_DOMAIN_ROOT):
        for module in _imported_module_names(path):
            if module in permitted_standard_library:
                continue

            if module.startswith("app.domain.evidence_evaluation."):
                continue

            if module.startswith("app.domain.engineering_evidence."):
                continue

            if module.startswith("app.domain.canonical_text."):
                continue

            offenders.append(
                f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
            )

    assert offenders == []


# --- 2. It cannot touch what it measures --------------------------------------


def test_evaluation_cannot_write_engineering_evidence() -> None:
    """A measurement must not be able to modify the thing it measures.

    The domain may import the evidence *model* and the *extractor* - it
    has to, to run them - but nothing anywhere in the context may reach
    the evidence repository, its adapter or its tables."""

    forbidden = (
        "app.domain.engineering_evidence.engineering_evidence_repository",
        "app.infrastructure.engineering_evidence",
        "app.models.engineering_evidence",
        "app.services.engineering_evidence_service",
    )

    assert _offenders(_evaluation_surface(), forbidden) == []


def test_evaluation_cannot_write_the_knowledge_graph() -> None:
    forbidden = (
        "app.services.knowledge_graph",
        "app.services.entity_extractor",
        "app.services.topology",
        "app.services.ai",
        "app.models.knowledge_graph",
        "app.domain.project_knowledge_graph",
        "app.domain.graph_builder",
        "app.domain.canonicalization",
        "app.domain.proposed_claims",
        "app.infrastructure.project_knowledge_graph",
    )

    assert _offenders(_evaluation_surface(), forbidden) == []


def test_evaluation_cannot_write_the_engineering_index() -> None:
    forbidden = (
        "app.domain.engineering_index",
        "app.services.engineering_index_service",
        "app.infrastructure.engineering_index",
        "app.models.engineering_index",
    )

    assert _offenders(_evaluation_surface(), forbidden) == []


def test_evaluation_cannot_import_the_llm_runtime() -> None:
    """Evaluation of a deterministic extractor is arithmetic over
    counts. A model asked to judge would make the measurement as
    unrepeatable as the thing it was meant to check."""

    forbidden = (
        "anthropic",
        "openai",
        "ollama",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.domain.prompt_builder",
        "app.services.prompt_builder_service",
        "app.domain.context_builder",
    )

    assert _offenders(_evaluation_surface(), forbidden) == []


def test_evaluation_cannot_import_the_engineering_engine() -> None:
    forbidden = (
        "app.domain.engineering_engine",
        "app.services.engineering_engine",
        "app.domain.engineering_intent",
        "app.domain.engineering_response",
        "app.domain.structured_retrieval",
    )

    assert _offenders(_evaluation_surface(), forbidden) == []


def test_the_corpus_port_offers_no_way_to_write_a_corpus() -> None:
    """
    Asserted on the contract - the abstract method set.

    A corpus is the definition of "correct" for every extraction rule.
    Changing it is an edit to a version-controlled file, reviewed like
    any other domain change; a runtime ``save`` would let anybody move
    the goalposts to make a rule pass.
    """

    from app.domain.evidence_evaluation.corpus_repository import (
        ReferenceCorpusRepository,
    )

    assert set(ReferenceCorpusRepository.__abstractmethods__) == {
        "list_corpora",
        "load",
        "materialize",
    }


def test_the_report_port_offers_no_way_to_overwrite_a_report() -> None:
    """No ``update`` and no ``delete``: overwriting a report would
    destroy the history regression detection is made of."""

    from app.domain.evidence_evaluation.evaluation_report_repository import (
        EvaluationReportRepository,
    )

    assert set(EvaluationReportRepository.__abstractmethods__) == {
        "save",
        "get",
        "list_for_corpus",
    }


def test_the_report_adapter_writes_only_evaluation_tables() -> None:
    adapter = (
        EVALUATION_ADAPTER_ROOT
        / "sqlalchemy_evaluation_report_repository.py"
    )
    forbidden = (
        "app.models.engineering_evidence",
        "app.models.canonical_text",
        "app.models.canonical_pdf",
        "app.models.document",
    )

    assert _offenders([adapter], forbidden) == []


# --- 3. It measures the current rules ------------------------------------------


def test_the_engine_executes_the_extractor_rather_than_reading_evidence(
) -> None:
    """
    An evaluation against stored evidence would measure what was stored
    on some past day, not what the current rules produce - which is the
    only question worth asking of a rule catalogue.
    """

    engine = EVALUATION_DOMAIN_ROOT / "evaluation_engine.py"
    imported = _imported_module_names(engine)

    assert (
        "app.domain.engineering_evidence.evidence_extractor" in imported
    )
    assert not any(
        _violates(
            module,
            (
                "app.domain.engineering_evidence"
                ".engineering_evidence_repository",
            ),
        )
        for module in imported
    )


def test_the_matcher_is_pure() -> None:
    """No clock, no randomness, no I/O - two evaluations of the same
    input must compare equal, and a timestamp would make that
    impossible."""

    forbidden = ("datetime", "time", "random", "uuid", "os", "secrets")
    matcher = EVALUATION_DOMAIN_ROOT / "evaluation_matcher.py"
    metrics = EVALUATION_DOMAIN_ROOT / "evaluation_metrics.py"
    detector = EVALUATION_DOMAIN_ROOT / "regression_detector.py"

    assert _offenders([matcher, metrics, detector], forbidden) == []


def test_no_report_model_carries_a_timestamp() -> None:
    """When a report was produced is a fact about the row. A timestamp on
    the value would make two identical evaluations compare unequal."""

    import dataclasses

    from app.domain.evidence_evaluation.evaluation_models import (
        DocumentEvaluation,
        EvaluationReport,
        EvidenceEvaluationResult,
    )

    for model in (
        EvaluationReport,
        DocumentEvaluation,
        EvidenceEvaluationResult,
    ):
        names = {field.name for field in dataclasses.fields(model)}

        assert names & {"created_at", "evaluated_at", "timestamp"} == set()


def test_metrics_use_exact_decimals_never_floats() -> None:
    """
    Two runs, two machines and two database round-trips must render the
    same numbers.

    Matched on the syntax tree - names actually used in code - so the
    docstring explaining *why* floats are avoided is not mistaken for a
    float being used.
    """

    module = EVALUATION_DOMAIN_ROOT / "evaluation_metrics.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert "float" not in names
    assert "Decimal" in names


# --- 4. The corpus is version-controlled data ----------------------------------


def test_the_reference_corpus_lives_in_the_repository() -> None:
    """Domain data beside the domain that defines it, exactly as the
    ontology's YAML is - and reviewable without a database."""

    corpora = sorted(CORPUS_ROOT.glob("*.yaml"))

    assert corpora
    assert all(path.suffix == ".yaml" for path in corpora)


def test_expectations_are_not_hardcoded_in_test_methods() -> None:
    """
    The reference corpus is loaded from file, never built inline in the
    tests that measure against it.

    Expectations that could be edited beside the assertion would let
    anybody make the extractor look good by moving the goalposts.
    """

    corpus_tests = (
        Path(__file__).resolve().parents[1]
        / "infrastructure"
        / "test_reference_corpus.py"
    )
    source = corpus_tests.read_text(encoding="utf-8")

    assert "YamlReferenceCorpusRepository" in source
    assert "ReferenceCorpus(" not in source
    assert "ExpectedObservation(" not in source
