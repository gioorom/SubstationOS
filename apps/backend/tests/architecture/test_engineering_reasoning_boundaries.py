"""
Architecture fitness functions for Deterministic Engineering Reasoning
(EPIC 32.1) - AF-REASON-001, AF-REASON-002 and AF-REASON-003.

These are the invariants that keep a *derived conclusion* from ever
becoming a *governed fact*. They are structural on purpose: each one is
proved by reading the code (AST, imports, dataclass fields) rather than
by exercising a happy path, so a future change that quietly crosses the
line fails here even if every behavioural test still passes.

    AF-REASON-001  Fact != Inference.
                   A conclusion is a separate type in a separate field,
                   is never written into governed knowledge, and never
                   claims governance it does not have.

    AF-REASON-002  Every conclusion is traceable.
                   A conclusion names the governed facts it came from,
                   the rule that derived it, and the version of that
                   rule.

    AF-REASON-003  No auto-promotion.
                   Reasoning cannot write the graph, cannot create a
                   Human Review, and cannot promote anything. It holds
                   nothing capable of doing so.

A fourth guarantee is enforced alongside them: reasoning is
**deterministic**. No provider, no embedding, no clock, no randomness.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields, is_dataclass
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

REASONING_DOMAIN_ROOT = DOMAIN_ROOT / "engineering_reasoning"
REASONING_SERVICE = APP_ROOT / "services" / "engineering_reasoning_service.py"
REASONING_STEP_HANDLERS = (
    APP_ROOT / "services" / "engineering_engine" / "reasoning_step_handlers.py"
)

#: Everything reasoning may not reach. Each entry is here for a reason,
#: not for tidiness.
FORBIDDEN_MODULES: tuple[str, ...] = (
    # Infrastructure and persistence: reasoning reads the context it was
    # handed and nothing else. A session or repository would let it widen
    # the project scope, the document scope, or the caller's
    # authorization with nothing downstream noticing.
    "app.infrastructure",
    "app.models",
    "app.database",
    "app.repositories",
    "sqlalchemy",
    "alembic",
    # HTTP and schemas: the domain is not reachable from the wire.
    "fastapi",
    "pydantic",
    "starlette",
    "app.routers",
    "app.schemas",
    # AI of every shape. Deterministic means deterministic.
    "anthropic",
    "openai",
    "langchain",
    "transformers",
    "sentence_transformers",
    "torch",
    "numpy",
    "sklearn",
    "app.application.llm",
    "app.infrastructure.llm",
    # Non-determinism.
    "random",
    "secrets",
    "uuid",
    # AF-REASON-003: the write side of governed knowledge. Reasoning
    # cannot promote, cannot review, and cannot author the graph -
    # because it cannot import the things that do.
    "app.domain.human_review",
    "app.domain.knowledge_promotion",
    "app.services.knowledge_promotion_service",
    "app.services.human_review_service",
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


def _reasoning_surface() -> list[Path]:
    return [
        *_python_files(REASONING_DOMAIN_ROOT),
        REASONING_SERVICE,
        REASONING_STEP_HANDLERS,
    ]


# --- AF-REASON-003: reasoning cannot write anything ----------------------


def test_af_reason_003_reasoning_imports_nothing_that_can_write() -> None:
    """
    The whole reasoning surface - domain, service and engine step handler
    - imports no repository, session, promotion service, Human Review
    module or graph writer.

    This is AF-REASON-003 proved by absence rather than by policy: a
    reasoning step that holds nothing capable of writing cannot
    auto-promote a conclusion into governed knowledge, whatever a future
    caller asks it to do.
    """

    violations = [
        f"{path.relative_to(APP_ROOT.parent)} imports '{module}'"
        for path in _reasoning_surface()
        for module in sorted(_imported_module_names(path))
        if _violates(module, FORBIDDEN_MODULES)
    ]

    assert violations == []


def test_af_reason_003_reasoning_imports_no_graph_repository() -> None:
    """
    Reasoning reads no governed repository of any kind.

    It may name the governed *vocabulary* - a node kind and an edge kind
    are part of the question it is asked - but never a port that can read
    or write the graph itself. The distinction is the boundary: a rule
    that could query the graph could answer a question the assembled
    context never authorized.
    """

    offending = [
        f"{path.name} imports '{module}'"
        for path in _reasoning_surface()
        for module in sorted(_imported_module_names(path))
        if module.startswith("app.domain.governed_knowledge_graph.")
        and not module.endswith("graph_vocabulary")
    ]

    assert offending == []


def test_af_reason_003_the_reasoning_step_handler_holds_no_dependency() -> (
    None
):
    """
    ``ExecuteEngineeringReasoningStepHandler`` declares no ``__init__``
    of its own, so it is constructed with nothing: no session factory, no
    repository, no provider.

    Every other handler that touches persistence takes its dependency
    through a constructor. This one cannot be given one without an edit
    that this test fails.
    """

    from app.services.engineering_engine.reasoning_step_handlers import (
        ExecuteEngineeringReasoningStepHandler,
    )

    assert "__init__" not in vars(ExecuteEngineeringReasoningStepHandler)


def test_af_reason_003_the_reasoning_service_opens_no_session() -> None:
    """The application service performs no I/O: its only input is the
    ``ContextPackage`` it is handed."""

    source = REASONING_SERVICE.read_text(encoding="utf-8")

    for forbidden_call in ("SessionLocal", "get_db", "Depends", "async with"):
        assert forbidden_call not in source


# --- AF-REASON-001: a conclusion is not a fact ---------------------------


def test_af_reason_001_a_result_is_a_type_of_its_own() -> None:
    """
    ``ReasoningResult`` is its own frozen type in its own bounded
    context. It is not a governed node, not a governed edge, not a
    context item and not an evidence reference - so no code path can
    hand a conclusion to something expecting governed knowledge and have
    it type-check.
    """

    from app.domain.context_builder.context_builder_models import ContextItem
    from app.domain.engineering_reasoning.reasoning_models import (
        ReasoningResult,
    )

    assert is_dataclass(ReasoningResult)
    assert ReasoningResult.__dataclass_params__.frozen

    assert not issubclass(ReasoningResult, ContextItem)

    field_names = {field.name for field in fields(ReasoningResult)}
    # A conclusion carries no governance of its own: no review, no
    # approval, no reviewer, no statement key. It only *points at* the
    # governed facts that carry those.
    assert field_names.isdisjoint(
        {
            "review_id",
            "reviewer_display_name",
            "statement_key",
            "approved",
            "approval_decision",
            "promoted",
        }
    )


def test_af_reason_001_a_conclusion_never_claims_to_be_governed() -> None:
    """The response's derived-reasoning read model answers ``False`` to
    the one question that matters, permanently and by construction."""

    from app.domain.engineering_response.engineering_response_models import (
        DerivedReasoningAssessment,
    )

    assert (
        DerivedReasoningAssessment.is_governed_knowledge.fget(object())
        is False
    )


def test_af_reason_001_the_response_keeps_reasoning_out_of_evidence() -> None:
    """
    ``EngineeringResponse.derived_reasoning`` is a field of its own,
    separate from ``references``.

    A conclusion listed among the evidence references would read, to
    every downstream consumer, as one more governed fact supporting the
    answer. It is not one: it is a statement *about* those facts.
    """

    from app.domain.engineering_response.engineering_response_models import (
        EngineeringResponse,
    )

    field_names = {field.name for field in fields(EngineeringResponse)}
    assert "derived_reasoning" in field_names
    assert "references" in field_names


# --- AF-REASON-002: every conclusion is traceable ------------------------


def test_af_reason_002_a_result_names_its_rule_and_version() -> None:
    """A conclusion always says what derived it and at which version, so
    a change in what the platform concludes is a version change somebody
    can point at."""

    from app.domain.engineering_reasoning.reasoning_models import (
        ReasoningResult,
        ReasoningRuleIdentity,
    )

    result_fields = {field.name for field in fields(ReasoningResult)}
    assert {"rule", "reasoning_policy_version", "diagnostics"} <= result_fields

    rule_fields = {field.name for field in fields(ReasoningRuleIdentity)}
    assert {"rule_id", "rule_version", "family"} <= rule_fields


def test_af_reason_002_every_contributor_carries_governed_provenance() -> None:
    """
    Each contributing fact names its governed node, its governed edge,
    its Semantic Statement, the Human Review that approved it and the
    document behind it.

    That chain is what lets a reader verify a conclusion without
    trusting the reasoner.
    """

    from app.domain.engineering_reasoning.reasoning_models import (
        ReasoningContributor,
    )

    field_names = {field.name for field in fields(ReasoningContributor)}
    assert {
        "node_id",
        "edge_id",
        "statement_key",
        "review_id",
        "reviewer_display_name",
        "support_fingerprint",
        "document_id",
        "content_checksum",
        "semantic_rule_id",
        "semantic_rule_version",
    } <= field_names


def test_af_reason_002_provenance_survives_into_the_response() -> None:
    """The response's own support type carries the same chain, so
    traceability is not lost at the API boundary."""

    from app.domain.engineering_response.engineering_response_models import (
        DerivedReasoningSupport,
    )

    field_names = {field.name for field in fields(DerivedReasoningSupport)}
    assert {
        "node_id",
        "edge_id",
        "statement_key",
        "review_id",
        "reviewer_display_name",
        "document_id",
    } <= field_names


# --- Determinism ---------------------------------------------------------


def test_reasoning_reads_no_clock() -> None:
    """
    The engineering content of a conclusion is a pure function of the
    context and the query. ``evaluated_at`` is passed in by the caller;
    the domain never calls ``datetime.now`` or ``utcnow``.

    The one thing that *is* measured - ``duration_seconds``, in the
    application service - is operational, varies run to run, and is
    excluded from the result's identity for exactly that reason.
    """

    for path in _python_files(REASONING_DOMAIN_ROOT):
        source = path.read_text(encoding="utf-8")
        assert "datetime.now" not in source, path
        assert "utcnow" not in source, path
        assert "time.time" not in source, path


def test_the_result_identity_is_a_pure_function_of_governed_material() -> None:
    """
    ``reasoning_result_id`` takes only the rule, the question, the
    project and the contributing governed identities - no timestamp, no
    duration, no counter.

    Two runs over the same governed knowledge therefore produce the same
    identifier, which is what makes a conclusion citable at all.
    """

    from app.domain.engineering_reasoning.reasoning_identity import (
        reasoning_result_id,
    )

    parameters = set(inspect.signature(reasoning_result_id).parameters)
    assert parameters == {
        "rule_id",
        "rule_version",
        "question",
        "project_id",
        "contributing_identities",
    }

    material = dict(
        rule_id="governed_quantity_consistency",
        rule_version="1.0",
        question="rated power of TR1",
        project_id=1,
        contributing_identities=("node-1|edge-1", "node-2|edge-2"),
    )
    first = reasoning_result_id(**material)
    assert reasoning_result_id(**material) == first

    # Order of the contributing identities must not change the identity:
    # the same governed facts are the same governed facts.
    reordered = dict(
        material, contributing_identities=("node-2|edge-2", "node-1|edge-1")
    )
    assert reasoning_result_id(**reordered) == first

    # A rule version change *must* change it.
    assert reasoning_result_id(**dict(material, rule_version="2.0")) != first


def test_the_outcome_vocabulary_is_four_valued_and_closed() -> None:
    """
    Four outcomes, never a boolean and never a score.

    "the governed values agree", "they disagree", "the graph does not
    say" and "the question named more than one piece of equipment" are
    four different engineering findings. Collapsing the last three into
    "not consistent" is how a real installation gets signed off on a gap
    nobody looked for.
    """

    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        ReasoningOutcome,
    )

    assert {member.value for member in ReasoningOutcome} == {
        "consistent",
        "inconsistent",
        "insufficient_knowledge",
        "ambiguous",
    }


def test_no_confidence_or_score_anywhere_in_reasoning() -> None:
    """
    No probability, no confidence, no relevance score, no ranking.

    A deterministic rule either concluded something from governed
    knowledge or it did not. A number expressing how sure it is would be
    an invitation to threshold it, and a thresholded conclusion is a
    guess wearing a decimal point.
    """

    banned = ("confidence", "probability", "score", "likelihood", "ranking")

    # Identifiers, not prose: the docstrings in this context say the word
    # "score" repeatedly, always to forbid it. What must not exist is a
    # *thing* named that - a field, a variable, a function, an attribute.
    offending: list[str] = []

    for path in _reasoning_surface():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifier = node.id
            elif isinstance(node, ast.Attribute):
                identifier = node.attr
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                identifier = node.name
            elif isinstance(node, ast.ClassDef):
                identifier = node.name
            elif isinstance(node, ast.arg):
                identifier = node.arg
            elif isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name
            ):
                identifier = node.target.id
            else:
                continue

            lowered = identifier.lower()
            offending.extend(
                f"{path.name}: '{identifier}'"
                for word in banned
                if word in lowered
            )

    assert offending == []
