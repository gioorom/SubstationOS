"""
Architecture tests for the Human Review context.

Structural, on the AST or the filesystem, never on prose. These are the
tests that keep **engineering truth separate from engineering judgement**
after everybody who remembers why has left:

- the engineering pipeline must never learn that reviews exist;
- Human Review must never reach into an engineering implementation;
- no review may write an engineering table;
- no current decision may be stored as mutable state;
- the history must stay append-only.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

HUMAN_REVIEW_DOMAIN = APP_ROOT / "domain" / "human_review"
HUMAN_REVIEW_INFRASTRUCTURE = APP_ROOT / "infrastructure" / "human_review"

#: Every bounded context that models the deterministic pipeline.
ENGINEERING_DOMAINS = (
    "canonical_pdf",
    "canonical_text",
    "engineering_evidence",
    "engineering_entities",
    "engineering_facts",
    "engineering_semantics",
    "ontology",
)

ENGINEERING_MODELS = (
    "canonical_pdf.py",
    "canonical_text.py",
    "engineering_evidence.py",
    "engineering_entities.py",
    "engineering_facts.py",
    "engineering_semantics.py",
)


def _modules(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


# --- The two contexts do not know each other -----------------------------


def test_no_engineering_domain_module_imports_human_review() -> None:
    """
    **The pipeline must not know it is reviewed.**

    An entity, a fact and a semantic statement are functions of the
    document's bytes and the versioned rules that read them. The moment
    the pipeline could consult a review, its output would depend on
    somebody's opinion and would stop being deterministic - and "why does
    the system believe this?" would acquire an answer involving a
    judgement.
    """

    offenders: list[str] = []

    for context in ENGINEERING_DOMAINS:
        for module in _modules(APP_ROOT / "domain" / context):
            for imported in _imports(module):
                if imported.startswith("app.domain.human_review"):
                    offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_human_review_domain_imports_no_engineering_module() -> None:
    """
    The other direction, and the subtler one.

    ``review_applicability`` decides whether a judgement still applies -
    which sounds like it needs the semantic set, and does not: it takes a
    ``CurrentPipelineState``, a thin description of identity that the
    application service fills in. That indirection is what this test
    protects, and it is what keeps the review domain testable without a
    pipeline.
    """

    offenders: list[str] = []

    forbidden = (
        "app.domain.canonical_pdf",
        "app.domain.canonical_text",
        "app.domain.engineering_evidence",
        "app.domain.engineering_entities",
        "app.domain.engineering_facts",
        "app.domain.engineering_semantics",
        "app.domain.ontology",
    )

    for module in _modules(HUMAN_REVIEW_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_human_review_domain_imports_no_infrastructure() -> None:
    """The dependency rule, applied to the newest context."""

    forbidden = (
        "sqlalchemy",
        "fastapi",
        "starlette",
        "app.models",
        "app.infrastructure",
        "app.routers",
        "app.schemas",
        "app.services",
        "app.database",
    )

    offenders: list[str] = []

    for module in _modules(HUMAN_REVIEW_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_only_named_modules_join_the_two_contexts() -> None:
    """
    Every module that reads both semantics and reviews, named explicitly.

    The rule this protects is that there is **one** account of what
    "still applies" means. `human_review_service` computes it; everything
    else that needs it asks that service rather than re-deriving it from
    a semantic set - and `knowledge_promotion_service` does exactly that
    (EPIC 31), which is why it is on the list rather than an exception to
    it.

    A module appearing here without a deliberate edit to this test is a
    second, quietly diverging definition.
    """

    joiners: list[str] = []

    for module in _modules(APP_ROOT / "services") + _modules(
        APP_ROOT / "routers"
    ):
        imports = _imports(module)

        touches_review = any(
            item.startswith("app.domain.human_review")
            or item.startswith("app.infrastructure.human_review")
            for item in imports
        )
        touches_semantics = any(
            "engineering_semantics" in item for item in imports
        )

        if touches_review and touches_semantics:
            joiners.append(module.name)

    assert sorted(joiners) == [
        # The review API.
        "governed_knowledge_graph.py",
        "human_review.py",
        "human_review_service.py",
        # Promotion reads a statement's current review through
        # `human_review_service.current_review`; it does not re-implement
        # applicability, and an architecture test in the graph suite
        # asserts the graph domain imports neither context.
        "knowledge_promotion_service.py",
    ]


# --- No review mutates an engineering artefact ---------------------------


def test_no_review_module_writes_an_engineering_table() -> None:
    """
    The review context reads the semantic set to resolve a key and to
    compare identity. It writes ``engineering_reviews`` and nothing else.
    """

    engineering_records = (
        "EngineeringSemanticSetRecord",
        "EngineeringSemanticStatementRecord",
        "EngineeringFactRecord",
        "EngineeringEntityRecord",
        "EngineeringEvidenceRecord",
    )

    reviewing_modules = (
        _modules(HUMAN_REVIEW_DOMAIN)
        + _modules(HUMAN_REVIEW_INFRASTRUCTURE)
        + [
            APP_ROOT / "services" / "human_review_service.py",
            APP_ROOT / "routers" / "human_review.py",
        ]
    )

    offenders: list[str] = []

    for module in reviewing_modules:
        source = module.read_text(encoding="utf-8")

        for record in engineering_records:
            if record in source:
                offenders.append(f"{module.name} references {record}")

    assert offenders == []


def test_the_review_service_calls_no_pipeline_stage() -> None:
    """
    Reading the pipeline is allowed; running it is not. A review that
    could trigger a re-interpretation would make judgement a cause of
    engineering output.
    """

    source = (
        APP_ROOT / "services" / "human_review_service.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "interpret_document_facts",
        "construct_",
        "resolve_engineering",
        "extract_engineering",
        "canonicalize",
        ".save(",
    ):
        assert forbidden not in source, forbidden


def test_the_review_repository_touches_only_its_own_table() -> None:
    source = (
        HUMAN_REVIEW_INFRASTRUCTURE
        / "sqlalchemy_review_repository.py"
    ).read_text(encoding="utf-8")

    assert "ReviewRecord" in source

    for forbidden in ("Semantic", "Fact", "Entity", "Evidence", "Document"):
        assert f"{forbidden}Record" not in source


# --- Append-only ---------------------------------------------------------


def test_the_review_port_declares_no_mutating_operation() -> None:
    """
    A judgement an application can edit afterwards is not a record of
    what anybody decided. The guarantee is the interface's, so it
    survives somebody adding a method to an implementation.
    """

    source = (HUMAN_REVIEW_DOMAIN / "review_repository.py").read_text(
        encoding="utf-8"
    )

    assert "def append" in source

    for forbidden in (
        "def update",
        "def delete",
        "def remove",
        "def save",
        "def supersede",
        "def amend",
    ):
        assert forbidden not in source


def test_the_review_repository_issues_no_update_or_delete() -> None:
    source = (
        HUMAN_REVIEW_INFRASTRUCTURE
        / "sqlalchemy_review_repository.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("update(", "delete(", ".merge(", "session.merge"):
        assert forbidden not in source


def test_a_review_is_an_immutable_value() -> None:
    """Frozen, like every other domain value in this codebase."""

    source = (HUMAN_REVIEW_DOMAIN / "review_models.py").read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]

    assert classes

    for node in classes:
        rendered = " ".join(
            ast.unparse(decorator) for decorator in node.decorator_list
        )

        assert "frozen=True" in rendered, node.name


# --- The current decision is never stored --------------------------------


def test_the_review_table_has_no_mutable_status_column() -> None:
    """
    A stored ``current``/``superseded``/``status`` column would be a
    second account of what the ordered history already says, and the day
    it disagreed there would be no way to tell which was true.
    """

    path = APP_ROOT / "models" / "human_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    columns = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    for forbidden in (
        "status",
        "is_current",
        "current",
        "superseded",
        "superseded_at",
        "superseded_by",
        "applicability",
        "requires_revalidation",
    ):
        assert forbidden not in columns, forbidden


def test_the_migration_creates_no_status_column() -> None:
    migration = (
        APP_ROOT.parent
        / "migrations"
        / "versions"
        / "c92f4d1a7b60_add_engineering_reviews.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        '"status"',
        '"is_current"',
        '"superseded"',
        '"superseded_at"',
        '"applicability"',
    ):
        assert forbidden not in migration, forbidden


def test_the_review_table_carries_no_engineering_payload() -> None:
    path = APP_ROOT / "models" / "human_review.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    columns = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    for forbidden in (
        "statement_type",
        "subject_entity_key",
        "object_entity_key",
        "supporting_fact_keys",
        "value",
        "unit",
        "observed_text",
    ):
        assert forbidden not in columns, forbidden


def test_the_review_table_has_no_foreign_key_at_all() -> None:
    """
    Not to the semantic tables - a re-run replaces a set, and a
    constraint would either block the pipeline or cascade a historical
    judgement into nothing. Not to ``users`` - the record must outlive
    the account.
    """

    source = (APP_ROOT / "models" / "human_review.py").read_text(
        encoding="utf-8"
    )

    assert "ForeignKey" not in source


# --- The vocabulary stays closed -----------------------------------------


def test_the_decision_vocabulary_is_not_extensible_at_a_call_site() -> None:
    """
    Three decisions, from an enum. A free-text decision would make "how
    many statements are rejected?" unanswerable.
    """

    source = (HUMAN_REVIEW_DOMAIN / "review_vocabulary.py").read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    decision = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "ReviewDecision"
    )

    members = [
        target.id
        for statement in decision.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    ]

    assert sorted(members) == [
        "APPROVED",
        "NEEDS_INVESTIGATION",
        "REJECTED",
    ]


def test_the_review_policy_is_a_pure_function() -> None:
    """No request, no repository, no clock - enums and a comment in."""

    path = HUMAN_REVIEW_DOMAIN / "review_policy.py"

    assert _imports(path) <= {
        "__future__",
        "app.domain.human_review.review_exceptions",
        "app.domain.human_review.review_models",
        "app.domain.human_review.review_vocabulary",
    }
