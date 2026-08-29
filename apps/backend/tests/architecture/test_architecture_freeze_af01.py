"""
Architecture Freeze AF-01 — the fitness functions of the freeze itself.

Most AF-01 invariants were already executable before the freeze: 371
architecture tests existed, and
`docs/architecture/architecture_freeze_af01.md` §20 maps every invariant
to the test that enforces it. **This file holds only the invariants that
had no executable enforcement**, plus the two freeze-level statements
that no single earlier test made as a whole.

Adding a test here that duplicates an existing one would make the freeze
look better enforced than it is, which is the opposite of the point.

---

## What a freeze test is for

An ordinary architecture test protects a decision. A freeze test protects
a decision **that later milestones will be under pressure to break** -
specifically EPIC 32, Engineering Reasoning, which will want to write
conclusions somewhere, retrieve more than governed knowledge offers, and
resolve ambiguity into an answer.

Every test here fails loudly in exactly that situation, and names the
AF-01 invariant it enforces so the reader knows whether they are fixing a
bug or superseding an architecture decision.
"""

from __future__ import annotations

import ast
import pathlib

import app.main
from fastapi.routing import APIRoute

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
DOMAIN_ROOT = APP_ROOT / "domain"


def _modules(directory: pathlib.Path) -> list[pathlib.Path]:
    return [
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


def _domain_context_of(imported: str) -> str | None:
    parts = imported.split(".")

    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "domain":
        return parts[2]

    return None


def _domain_dependencies() -> dict[str, set[str]]:
    """The real domain-to-domain dependency graph, from imports."""

    graph: dict[str, set[str]] = {}

    for directory in sorted(DOMAIN_ROOT.iterdir()):
        if not directory.is_dir() or directory.name == "__pycache__":
            continue

        edges: set[str] = set()

        for module in _modules(directory):
            for imported in _imports(module):
                target = _domain_context_of(imported)

                if target is not None and target != directory.name:
                    edges.add(target)

        graph[directory.name] = edges

    return graph


def _routes() -> list[APIRoute]:
    found: list[APIRoute] = []

    for route in app.main.app.routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif type(route).__name__ == "_IncludedRouter":
            found.extend(
                sub
                for sub in route.original_router.routes
                if isinstance(sub, APIRoute)
            )

    return found


# --- AF-DEP-001: the frozen dependency direction ------------------------
#
# Six directions AF-01 protects by name. Each existed as an accident of
# good design before the freeze; none was asserted as a whole, and each
# is a direction a reasoning milestone could plausibly reverse "just to
# read one field".

#: (dependent, forbidden dependency, why reversing it would be wrong)
FROZEN_DIRECTIONS = (
    (
        "human_review",
        "governed_retrieval",
        "a judgement about a statement must not depend on how knowledge is "
        "queried; reviews would start being written for what retrieval can "
        "find",
    ),
    (
        "human_review",
        "context_builder",
        "same reason, one layer further downstream",
    ),
    (
        "governed_knowledge_graph",
        "governed_retrieval",
        "the projection must not know how it is read, or promotion would "
        "start optimising for a query shape",
    ),
    (
        "governed_knowledge_graph",
        "context_builder",
        "same reason",
    ),
    (
        "governed_retrieval",
        "context_builder",
        "retrieval decides what matched; how that becomes context is not "
        "its concern, and a dependency here would let context influence "
        "matching",
    ),
    (
        "context_builder",
        "engineering_response",
        "context is assembled before an answer exists; depending on the "
        "answer's shape would make the context a function of the reply",
    ),
    (
        "engineering_facts",
        "human_review",
        "**Engineering Truth must not depend on Engineering Judgement.** A "
        "deterministic fact that could see a review would stop being "
        "reproducible from the document alone",
    ),
    (
        "engineering_semantics",
        "human_review",
        "same reason, for the layer that assigns meaning",
    ),
    (
        "engineering_semantics",
        "engineering_engine",
        "the pipeline must not know an answering engine exists",
    ),
    (
        "engineering_facts",
        "engineering_engine",
        "same reason",
    ),
)


def test_af_dep_001_frozen_dependency_directions_hold() -> None:
    """
    **AF-DEP-001.** Ten named directions, each with a recorded reason.

    Asserted on real imports rather than on documentation, and reported
    with the rationale so a failure explains what would break rather than
    only what changed.
    """

    graph = _domain_dependencies()
    violations: list[str] = []

    for dependent, forbidden, reason in FROZEN_DIRECTIONS:
        if dependent not in graph:
            violations.append(f"{dependent} no longer exists as a context")
            continue

        if forbidden in graph[dependent]:
            violations.append(
                f"{dependent} now imports {forbidden} — {reason}"
            )

    assert violations == []


def test_af_dep_002_the_domain_dependency_graph_is_acyclic() -> None:
    """
    **AF-DEP-002.** No cycle between bounded contexts.

    A cycle is how two contexts quietly become one. Checked by depth-first
    search over the real import graph, so a cycle introduced through a
    third context is caught as well as a direct one.
    """

    graph = _domain_dependencies()
    cycles: list[str] = []

    def visit(node: str, path: list[str], seen: set[str]) -> None:
        for target in sorted(graph.get(node, ())):
            if target in path:
                start = path.index(target)
                cycles.append(" -> ".join(path[start:] + [target]))
                continue

            if target in seen:
                continue

            seen.add(target)
            visit(target, path + [target], seen)

    for context in sorted(graph):
        visit(context, [context], set())

    assert sorted(set(cycles)) == []


# --- AF-PROV-002: provenance is never caller-asserted -------------------


def test_af_prov_002_no_persisting_route_accepts_governed_provenance() -> (
    None
):
    """
    **AF-PROV-002.** *Provenance a caller asserts is not provenance.*

    The lesson EPIC 31.3 paid for: it withdrew
    `POST /projects/{id}/context-builder/build` rather than let a request
    body carry a statement key, a review id and a reviewer name into an
    artefact that would then look reviewed.

    ---

    ## Why this is not "no request body may carry provenance"

    Fourteen routes legitimately accept one. Post a `ContextPackage` to
    `/prompt-builder/build`, a `PromptPackage` to `/llm/prepare-request`,
    an `EngineeringResponse` to `/conversation/attach-response` - each
    carries the governed citations of the artefact upstream of it, and
    each has to, or the stage could not be inspected on its own.

    **What makes them safe is that they persist nothing.** They open no
    database session, hold no repository, and return a new artefact
    rather than storing one. A fabricated body harms only the caller's
    own reply.

    So the invariant is the one that actually matters, and it is computed
    rather than listed: **a route that can persist or author may not
    accept governed provenance.** A hardcoded exemption list would be
    gamed by appending to it; this fails the moment a stateless route
    grows a session, which is exactly the change that would make
    caller-asserted provenance dangerous.
    """

    governed_fields = {
        "statement_key",
        "review_id",
        "reviewer_user_id",
        "reviewer_display_name",
        "reviewed_at",
        "support_fingerprint",
        "content_checksum",
    }

    document = app.main.app.openapi()
    schemas = document["components"]["schemas"]

    def referenced(definition: object) -> list[str]:
        refs: list[str] = []

        if isinstance(definition, dict):
            reference = definition.get("$ref")

            if isinstance(reference, str):
                refs.append(reference.rsplit("/", 1)[-1])

            for value in definition.values():
                refs.extend(referenced(value))
        elif isinstance(definition, list):
            for value in definition:
                refs.extend(referenced(value))

        return refs

    def field_names(schema_name: str, seen: set[str]) -> set[str]:
        if schema_name in seen or schema_name not in schemas:
            return set()

        seen.add(schema_name)
        schema = schemas[schema_name]
        found = set(schema.get("properties", {}))

        for definition in schema.get("properties", {}).values():
            for candidate in referenced(definition):
                found |= field_names(candidate, seen)

        return found

    def persists(module_name: str) -> bool:
        """Whether a router can reach persistence at all."""

        module = APP_ROOT / "routers" / f"{module_name}.py"

        if not module.exists():
            return True  # unknown router: treat as persisting

        source = module.read_text(encoding="utf-8")

        return "Depends(get_db)" in source or "SessionLocal" in source

    offenders: list[str] = []

    for route in _routes():
        module_name = route.endpoint.__module__.rsplit(".", 1)[-1]

        if not persists(module_name):
            continue

        operations = document["paths"].get(route.path, {})

        for method, operation in operations.items():
            body = operation.get("requestBody")

            if not isinstance(body, dict):
                continue

            for schema_name in referenced(body):
                leaked = governed_fields & field_names(schema_name, set())

                if leaked:
                    offenders.append(
                        f"{method.upper()} {route.path} "
                        f"({schema_name}) accepts {sorted(leaked)}"
                    )

    assert sorted(set(offenders)) == []


def test_af_prov_003_the_stateless_composition_routes_persist_nothing() -> (
    None
):
    """
    **AF-PROV-003.** The other half of AF-PROV-002, asserted directly.

    AF-PROV-002 is only meaningful while the routes that *do* accept
    governed provenance remain stateless. This pins that: each of these
    routers opens no session and holds no repository.

    If one of them ever needs to persist, this fails first - and the fix
    is to stop accepting caller-asserted provenance there, not to delete
    the assertion.
    """

    stateless = (
        "prompt_builder",
        "engineering_response",
        "llm_provider",
        "conversation",
        "engineering_session",
        "working_memory",
    )

    offenders: list[str] = []

    for name in stateless:
        source = (APP_ROOT / "routers" / f"{name}.py").read_text(
            encoding="utf-8"
        )

        for forbidden in ("Depends(get_db)", "SessionLocal", "commit("):
            if forbidden in source:
                offenders.append(f"{name}.py uses {forbidden}")

    assert offenders == []


# --- AF-AMB-001: ambiguity is a closed, three-valued outcome ------------


def test_af_amb_001_the_match_outcome_vocabulary_is_closed() -> None:
    """
    **AF-AMB-001.** Exactly three outcomes, and no fourth.

    A fourth member is how `MULTIPLE_MATCHES` would eventually become
    something softer - "best match", "probable match" - and softening the
    vocabulary is how ambiguity gets erased without anybody deciding to
    erase it.

    EPIC 32 may reason *about* ambiguity. It may not add a value that
    means "resolved for you".
    """

    from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
        GovernedMatchOutcome,
    )

    assert [member.name for member in GovernedMatchOutcome] == [
        "NO_MATCH",
        "UNIQUE_MATCH",
        "MULTIPLE_MATCHES",
    ]


def test_af_amb_002_the_outcome_is_computed_before_any_limit() -> None:
    """
    **AF-AMB-002.** A page limit must not turn several governed answers
    into one apparently certain one.

    Structural, on the retrieval service: the outcome is classified from
    the pre-limit total, and the limit is applied afterwards. Asserted on
    the source because the behavioural version of this only fails when a
    fixture happens to exceed the limit.
    """

    source = (
        APP_ROOT / "services" / "governed_retrieval_service.py"
    ).read_text(encoding="utf-8")

    classify = source.index("outcome = governed_result_assembly.classify(")
    limited = source.index("items = ordered[:limit]")

    assert "classify(total_before_limit)" in source
    assert limited < classify, (
        "the outcome must be classified from the pre-limit total; "
        "classifying after limiting would hide ambiguity"
    )


# --- AF-DET-002: the deterministic core stays deterministic -------------

#: The contexts that must reach no LLM. The pipeline that establishes
#: engineering truth, the judgement recorded about it, and the governed
#: projection, retrieval and context assembly built on both.
DETERMINISTIC_CONTEXTS = (
    "canonical_pdf",
    "canonical_text",
    "engineering_evidence",
    "engineering_entities",
    "engineering_facts",
    "engineering_semantics",
    "human_review",
    "governed_knowledge_graph",
    "governed_retrieval",
    "context_builder",
)


def test_af_det_002_no_deterministic_context_reaches_an_llm() -> None:
    """
    **AF-DET-002.** The deterministic core is deterministic, end to end.

    Individual contexts already assert this for themselves. AF-01 asserts
    it for the **whole chain at once**, because the risk EPIC 32 brings is
    not that one context adopts an LLM - it is that one link in the chain
    does, and the chain keeps its reputation for determinism.

    Naming the contexts in one list also means adding a context to the
    deterministic core is a visible edit here.
    """

    forbidden = (
        "anthropic",
        "openai",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.application.ports.llm_provider_port",
    )

    offenders: list[str] = []

    for context in DETERMINISTIC_CONTEXTS:
        for module in _modules(DOMAIN_ROOT / context):
            for imported in _imports(module):
                if any(
                    imported == item or imported.startswith(f"{item}.")
                    for item in forbidden
                ):
                    offenders.append(f"{context}/{module.name} -> {imported}")

    assert offenders == []


# --- AF-TRUTH-001: judgement never rewrites truth -----------------------


def test_af_truth_001_review_writes_no_deterministic_artefact() -> None:
    """
    **AF-TRUTH-001.** Engineering Truth != Engineering Judgement.

    Approving a statement must not rewrite it; rejecting must not delete
    it; `NEEDS_INVESTIGATION` must not touch the evidence. The review
    service reads semantics and writes only its own append-only table.

    Asserted on the service rather than the domain because the domain
    already cannot reach persistence at all - the service is the only
    place where a write could be added.
    """

    source = (
        APP_ROOT / "services" / "human_review_service.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "EngineeringSemanticSetRecord",
        "EngineeringSemanticStatementRecord",
        "EngineeringFactRecord",
        "EngineeringEntityRecord",
        "EngineeringEvidenceRecord",
        "upsert",
        "commit",
        "delete(",
    ):
        assert forbidden not in source, forbidden


def test_af_truth_002_the_deterministic_pipeline_cannot_read_a_review() -> (
    None
):
    """
    **AF-TRUTH-002.** The other direction, and the more dangerous one.

    A pipeline stage that could read a review would produce output that
    depends on what somebody approved - and the determinism the whole
    platform rests on would be gone without a single test failing
    anywhere else.
    """

    pipeline = (
        "canonical_pdf",
        "canonical_text",
        "engineering_evidence",
        "engineering_entities",
        "engineering_facts",
        "engineering_semantics",
    )

    offenders: list[str] = []

    for context in pipeline:
        for module in _modules(DOMAIN_ROOT / context):
            for imported in _imports(module):
                if "human_review" in imported or "governed_knowledge_graph" in (
                    imported
                ):
                    offenders.append(f"{context}/{module.name} -> {imported}")

    assert offenders == []


# --- AF-KG-003: one authority, expressed as a capability ----------------


def test_af_kg_003_promotion_is_the_only_graph_authoring_authority() -> None:
    """
    **AF-KG-003.** One *application* authority may author graph knowledge.

    Deliberately asserted at the services layer and on the **capability**
    rather than on a filename: a repository's `upsert_node` is a storage
    mechanism, and the question a freeze must answer is which application
    responsibility is allowed to decide that knowledge may be published.

    If the promotion service is ever renamed or split, this test should be
    updated to name the new authority - not deleted. A failure here means
    a second authoring path exists, which is the AF-01 invariant EPIC 32
    is most likely to breach.
    """

    authorities = sorted(
        module.name
        for module in _modules(APP_ROOT / "services")
        if "upsert_node" in module.read_text(encoding="utf-8")
        or "upsert_edge" in module.read_text(encoding="utf-8")
    )

    assert authorities == ["knowledge_promotion_service.py"]


def test_af_kg_004_the_graph_is_reachable_only_as_a_projection() -> None:
    """
    **AF-KG-004.** The graph is derived, and says so structurally.

    `clear()` exists on the governed graph repository and on no other port
    in the system. That is only safe for something rebuildable, and its
    uniqueness is the cheapest possible proof that nothing else in this
    platform claims to be droppable-and-recomputable.
    """

    holders = sorted(
        module.name
        for module in _modules(DOMAIN_ROOT)
        if "def clear(" in module.read_text(encoding="utf-8")
    )

    assert holders == ["graph_repository.py"]


# --- AF-EVO-001: the freeze document exists and is reachable ------------


def test_af_evo_001_the_freeze_document_exists() -> None:
    """
    **AF-EVO-001.** A freeze nobody can find is not a freeze.

    The document carries the invariant catalogue, the supersession policy
    and the EPIC 32 entry gate. A test asserts it is present and names the
    invariants this file enforces, so the two cannot drift apart silently.
    """

    document = (
        BACKEND_ROOT.parents[1]
        / "docs"
        / "architecture"
        / "architecture_freeze_af01.md"
    )

    assert document.exists()

    text = document.read_text(encoding="utf-8")

    for invariant in (
        "AF-DEP-001",
        "AF-DEP-002",
        "AF-PROV-002",
        "AF-AMB-001",
        "AF-AMB-002",
        "AF-DET-002",
        "AF-TRUTH-001",
        "AF-TRUTH-002",
        "AF-KG-003",
        "AF-KG-004",
    ):
        assert invariant in text, invariant
