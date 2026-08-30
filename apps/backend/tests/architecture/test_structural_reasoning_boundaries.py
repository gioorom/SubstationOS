"""
Architecture invariants for shared structural location reasoning
(EPIC 32.2).

The 32.1 boundaries in `test_engineering_reasoning_boundaries.py` still
hold and are not restated here. What this file adds is the set of
guarantees a **relationship** rule needs and a quantity rule never did.

The four that would be most expensive to lose:

1. **The derived vocabulary is disjoint from every governed one.** A
   derived relationship and a governed one must not be representable as
   the same thing, or within a few milestones nobody will be able to
   tell which they are reading.
2. **Graph reachability is not the authority.** The inference is
   licensed by a named, versioned rule that reads one edge kind by name
   - not by the existence of a path.
3. **Nothing is traversed, chained or closed transitively.** There is no
   traversal to bound, and a derived result is never an input.
4. **The forbidden inferences stay forbidden**, in the implementation
   and not only in the prose: no connectivity, no electrical direction,
   no equipment state, no location classification.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
REASONING_ROOT = APP_ROOT / "domain" / "engineering_reasoning"
RULE = REASONING_ROOT / "shared_structural_location_rule.py"
REASONING_SERVICE = (
    APP_ROOT / "services" / "engineering_reasoning_service.py"
)


def _modules(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)

    return found


def _executable_source(path: Path) -> str:
    """
    One module's executable body, with its documentation removed.

    Docstrings *must* be free to name what this code refuses to do -
    that is what makes the refusals reviewable, and this context's
    docstrings are where the reasoning boundary is actually argued. A
    test that searched raw text for ``connected``, ``promote`` or
    ``score`` would forbid explaining the boundary in the one place a
    reader looks for it.

    So these tests read the **code**: comments and docstrings out,
    executable statements in.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                   ast.Module)
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body.pop(0)

    stripped = ast.unparse(tree)

    return "\n".join(
        line
        for line in stripped.splitlines()
        if not line.strip().startswith("#")
    )


def _rule_source() -> str:
    """The shared-structural-location rule's executable body."""

    return _executable_source(RULE)


# --- 1. Purity: the rule reads context and nothing else -----------------


def test_the_rule_imports_no_infrastructure() -> None:
    forbidden = (
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "anthropic",
        "openai",
        "httpx",
        "requests",
        "app.models",
        "app.database",
        "app.infrastructure",
        "app.routers",
    )

    for imported in _imports(RULE):
        for banned in forbidden:
            assert not imported.startswith(banned), (
                f"the rule imports {imported}"
            )


def test_the_rule_imports_no_repository_or_session() -> None:
    for imported in _imports(RULE):
        assert "repository" not in imported
        assert "session" not in imported
        assert "_service" not in imported


def test_the_rule_reads_the_context_package_and_not_the_graph() -> None:
    """
    It imports the governed graph's **vocabulary** - it must name the
    edge kind it reads - and nothing that could fetch one.
    """

    imports = _imports(RULE)

    assert "app.domain.context_builder.context_builder_models" in imports
    assert (
        "app.domain.governed_knowledge_graph.graph_vocabulary" in imports
    )

    for imported in imports:
        assert "graph_repository" not in imported
        assert "governed_knowledge_reader" not in imported


def test_the_rule_reads_no_clock() -> None:
    """``evaluated_at`` is a parameter. A rule that read the clock would
    not be a pure function of governed knowledge."""

    source = _rule_source()

    assert "datetime.now" not in source
    assert "utcnow" not in source
    assert "time.time" not in source


def test_the_rule_invokes_no_retrieval() -> None:
    source = _rule_source()

    for forbidden in (
        "retrieve",
        "GovernedRetrievalQueryFactory",
        "governed_retrieval_service",
        "reader",
    ):
        assert forbidden not in source


# --- 2. Reasoning writes nothing ----------------------------------------


def test_reasoning_cannot_write_any_authoritative_store() -> None:
    """No module in the reasoning context names a write operation on the
    governed graph, Human Review, semantics or facts."""

    forbidden = (
        "upsert_node",
        "upsert_edge",
        "promote",
        "retire",
        "reconcile",
        "record_review",
        "save_statement",
        "save_fact",
        "session.add",
        "commit(",
    )

    for module in _modules(REASONING_ROOT) + [REASONING_SERVICE]:
        source = _executable_source(module)

        for banned in forbidden:
            assert banned not in source, f"{module.name} names {banned}"


def test_the_reasoning_context_imports_no_write_capable_context() -> None:
    forbidden = (
        "app.domain.human_review",
        "app.domain.engineering_facts",
        "app.domain.engineering_semantics",
        "app.domain.proposed_claims",
        "app.services.knowledge_promotion_service",
    )

    for module in _modules(REASONING_ROOT):
        for imported in _imports(module):
            for banned in forbidden:
                assert not imported.startswith(banned), (
                    f"{module.name} imports {imported}"
                )


# --- 3. The derived vocabulary is disjoint from the governed ones -------


def test_the_derived_relationship_vocabulary_is_disjoint() -> None:
    """
    The structural form of AF-REASON-001, and the freeze this milestone
    most needs: a derived relationship must not be expressible as a
    governed one.
    """

    from app.domain.engineering_facts.fact_predicates import FactPredicate
    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        DerivedRelationshipKind,
    )
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
        GraphNodeKind,
    )

    derived = {kind.value for kind in DerivedRelationshipKind}

    assert derived
    assert not derived & {kind.value for kind in GraphEdgeKind}
    assert not derived & {kind.value for kind in SemanticStatementType}
    assert not derived & {kind.value for kind in FactPredicate}
    assert not derived & {kind.value for kind in GraphNodeKind}


def test_the_derived_vocabulary_lives_only_in_reasoning() -> None:
    """A governed context that declared it would be a governed context
    able to store an inference."""

    declaring = [
        module.name
        for module in _modules(APP_ROOT / "domain")
        if "DerivedRelationshipKind" in module.read_text(encoding="utf-8")
        and module.parent.name != "engineering_reasoning"
        and module.parent.name != "engineering_response"
    ]

    assert declaring == []


def test_the_governed_graph_vocabulary_is_unchanged_by_this_milestone(
) -> None:
    """EPIC 32.2 added no ontology. The graph carries exactly what EPIC
    32.P1 left it carrying."""

    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
        GraphNodeKind,
    )

    assert {kind.value for kind in GraphNodeKind} == {
        "engineering_asset",
        "engineering_quantity",
        "structural_location",
    }
    assert {kind.value for kind in GraphEdgeKind} == {
        "has_rated_power",
        "is_located_in",
    }


# --- 4. Graph reachability is not the authority -------------------------


def test_the_rule_names_the_edge_kind_it_reads() -> None:
    """
    The inference is licensed by *which* relationship it reads, not by
    the shape of the path. A rule that matched any edge kind would be
    concluding co-location from a shared rated power.
    """

    from app.domain.engineering_reasoning import (
        shared_structural_location_rule as rule,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
    )

    assert rule.LOCATION_RELATIONSHIP_KIND is GraphEdgeKind.IS_LOCATED_IN
    assert "LOCATION_RELATIONSHIP_KIND" in _rule_source()


def test_the_rule_is_named_and_versioned() -> None:
    from app.domain.engineering_reasoning import (
        shared_structural_location_rule as rule,
    )
    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        ReasoningRuleFamily,
    )

    identity = rule.SHARED_STRUCTURAL_LOCATION_RULE

    assert identity.rule_id == "shared_structural_location"
    assert identity.rule_version
    assert identity.family is ReasoningRuleFamily.STRUCTURAL_RELATIONSHIP


def test_every_reasoning_family_has_its_own_outcome_vocabulary() -> None:
    """`CONSISTENT` must not become the word for "yes"."""

    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        ReasoningOutcome,
        StructuralReasoningOutcome,
    )

    quantity = {outcome.value for outcome in ReasoningOutcome}
    structural = {outcome.value for outcome in StructuralReasoningOutcome}

    assert "consistent" in quantity
    assert "consistent" not in structural
    assert "established" in structural
    assert "established" not in quantity


# --- 5. No traversal, no chaining, no closure ---------------------------


def test_no_generic_graph_traversal_exists_in_reasoning() -> None:
    forbidden = (
        "breadth_first",
        "depth_first",
        "bfs",
        "dfs",
        "shortest_path",
        "traverse",
        "walk(",
        "visited",
        "frontier",
        "networkx",
        "transitive",
        "closure",
    )

    for module in _modules(REASONING_ROOT):
        lowered = _executable_source(module).lower()

        for banned in forbidden:
            assert banned not in lowered, f"{module.name} names {banned}"


def test_the_rule_declares_no_depth_or_limit_parameter() -> None:
    """There is no depth because there is no traversal - one governed
    relationship per side, and the shape is fixed."""

    from app.domain.engineering_reasoning import (
        shared_structural_location_rule as rule,
    )

    signature = inspect.signature(rule.evaluate)

    assert set(signature.parameters) == {
        "package",
        "query",
        "evaluated_at",
    }

    source = _rule_source()

    for forbidden in ("depth", "max_hops", "recursion", "while "):
        assert forbidden not in source


def test_a_reasoning_result_is_never_an_input_to_reasoning() -> None:
    """No chaining: the evaluator's inputs are a context and a query."""

    from app.domain.engineering_reasoning import (
        shared_structural_location_rule as rule,
    )

    annotations = {
        name: str(parameter.annotation)
        for name, parameter in inspect.signature(
            rule.evaluate
        ).parameters.items()
    }

    assert "ReasoningResult" not in " ".join(annotations.values())


def test_the_query_exposes_no_traversal_control() -> None:
    from app.domain.engineering_reasoning.reasoning_models import (
        SharedStructuralLocationQuery,
    )

    fields = set(SharedStructuralLocationQuery.__dataclass_fields__)

    assert fields == {
        "left_asset_node_id",
        "right_asset_node_id",
        "left_designation",
        "right_designation",
        "project_id",
    }


# --- 6. The forbidden inferences stay forbidden -------------------------


def test_the_rule_infers_no_connectivity() -> None:
    source = _rule_source().lower()

    for forbidden in (
        "connected",
        "connectivity",
        "circuit",
        "busbar",
        "feeds",
        "supplies",
        "protects",
    ):
        assert forbidden not in source


def test_the_rule_infers_no_electrical_direction() -> None:
    source = _rule_source().lower()

    for forbidden in ("upstream", "downstream", "source_side", "load_side"):
        assert forbidden not in source


def test_the_rule_infers_no_equipment_state() -> None:
    source = _rule_source().lower()

    for forbidden in (
        "energis",
        "energiz",
        "in_service",
        "out_of_service",
        "breaker_open",
        "breaker_closed",
    ):
        assert forbidden not in source


def test_the_rule_classifies_no_location() -> None:
    """``+E01`` is a designated location. Whether it is a bay, a room or
    a panel is a classification no governed vocabulary makes."""

    source = _rule_source().lower()

    for forbidden in ("bay", "room", "panel", "building", "cubicle"):
        assert forbidden not in source


def test_no_derived_outcome_asserts_a_negative() -> None:
    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        StructuralReasoningOutcome,
    )

    values = {outcome.value for outcome in StructuralReasoningOutcome}

    for forbidden in (
        "not_shared",
        "not_established",
        "disjoint",
        "separate",
        "different_location",
    ):
        assert forbidden not in values


# --- 7. Identity, ordering and symmetry ---------------------------------


def test_result_identity_excludes_operational_material() -> None:
    from app.domain.engineering_reasoning import reasoning_identity

    source = reasoning_identity.__doc__ or ""

    assert "wall-clock" in source

    signature = inspect.signature(reasoning_identity.reasoning_result_id)

    assert "duration" not in signature.parameters
    assert "evaluated_at" not in signature.parameters


def test_the_identity_question_is_canonical_and_order_free() -> None:
    from app.domain.engineering_reasoning.reasoning_models import (
        SharedStructuralLocationQuery,
    )

    forward = SharedStructuralLocationQuery(
        left_asset_node_id="node-a",
        right_asset_node_id="node-b",
        left_designation="A",
        right_designation="B",
    )
    reverse = SharedStructuralLocationQuery(
        left_asset_node_id="node-b",
        right_asset_node_id="node-a",
        left_designation="B",
        right_designation="A",
    )

    assert forward.identity_question == reverse.identity_question
    assert forward.question != reverse.question


def test_no_confidence_or_score_in_structural_reasoning() -> None:
    forbidden = ("confidence", "score", "probability", "likelihood", "weight")

    for module in _modules(REASONING_ROOT):
        lowered = _executable_source(module).lower()

        for banned in forbidden:
            assert banned not in lowered, f"{module.name} names {banned}"


# --- 8. No persistence --------------------------------------------------


def test_no_reasoning_result_is_persisted() -> None:
    """No table, no repository, no migration. A conclusion is a runtime
    artefact for as long as the result is in memory."""

    forbidden = ("reasoning_results", "derived_edges", "inference_cache")

    for module in _modules(APP_ROOT):
        source = module.read_text(encoding="utf-8")

        for banned in forbidden:
            assert banned not in source, f"{module.name} names {banned}"

    models = _modules(APP_ROOT / "models")

    for module in models:
        source = module.read_text(encoding="utf-8")

        assert "ReasoningResult" not in source
        assert "DerivedRelationshipKind" not in source


def test_reasoning_has_no_repository_port() -> None:
    assert not [
        module
        for module in _modules(REASONING_ROOT)
        if "repository" in module.name.lower()
    ]


# --- 9. The comparison workflow stays out of it -------------------------


def test_the_comparison_workflow_runs_no_structural_reasoning() -> None:
    """
    Deliberately disabled, and it is not an oversight.

    Structural location identity is **document-scoped** (EPIC 32.P1): the
    same ``+E01`` written on two sides of a comparison is two governed
    locations. A comparison workflow that reasoned across its sides would
    have exactly two options, and both are wrong - conclude nothing (and
    look broken), or match on the label (and perform the cross-document
    entity resolution this platform refuses).

    The two sides are also kept deliberately apart end to end, so there
    is no single governed context for a relationship rule to read.
    """

    from app.domain.engineering_engine.engineering_engine_models import (
        WorkflowStepType,
    )
    from app.domain.engineering_engine.workflow_definitions import (
        ENGINEERING_COMPARISON_WORKFLOW,
    )

    steps = {
        step.step_type
        for step in ENGINEERING_COMPARISON_WORKFLOW.steps
    }

    assert WorkflowStepType.EXECUTE_ENGINEERING_REASONING not in steps


def test_only_the_two_reasoning_workflows_reason() -> None:
    """One reasoning step, two workflows that run it, and a test that
    says which - so a third acquires the capability deliberately."""

    from app.domain.engineering_engine.engineering_engine_models import (
        WorkflowStepType,
    )
    from app.services.engineering_engine.composition import (
        build_workflow_registry,
    )

    registry = build_workflow_registry()
    reasoning = sorted(
        registry.resolve(intent).workflow_id.value
        for intent in registry.registered_intent_types()
        if any(
            step.step_type is WorkflowStepType.EXECUTE_ENGINEERING_REASONING
            for step in registry.resolve(intent).steps
        )
    )

    assert reasoning == [
        "engineering-verification",
        "structural-relationship",
    ]
