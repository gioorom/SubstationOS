"""
Architecture invariants of Document Version Identity (ADR-0036).

Three things the ADR decides in prose and nothing else could keep true:

1. **§18 / §19 - the recorded identity is written once.** No service,
   adapter, route or migration issues an ``UPDATE`` against the three
   identity columns, *including* the ``NULL`` -> value write that looks
   like closing a gap rather than rewriting a fact. This is the test the
   ADR calls the only defence against the boundary eroding quietly.
2. **§26 - the milestone introduces no engineering semantics.** A
   milestone about bytes must not acquire a vocabulary about
   substations, one plausible name at a time; §5 and §13 add that it
   must not acquire a lineage vocabulary either.
3. **§21 - ``document_identity`` is inside the deterministic core.** It
   computes the first local component of every deterministic identity in
   the system, and was absent from the list that constrains that core.

Scope, stated honestly. These are source scans, so they catch the
spellings a change would plausibly take - an attribute assignment, a
bulk update, a hand-written statement - in the modules that can reach a
``documents`` row. They cannot catch a write performed through some
entirely different mechanism, such as raw DBAPI access assembled at
runtime. That remains a review question, and the persistence tests in
``tests/infrastructure/test_document_content_identity_persistence.py``
assert the observable half.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.architecture.test_architecture_freeze_af01 import (
    DETERMINISTIC_CONTEXTS,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = BACKEND_ROOT / "app"
MIGRATIONS = BACKEND_ROOT / "migrations" / "versions"

#: Operational scripts are scanned too, and deliberately.
#:
#: ADR-0036 §25 rejects "a one-off script that hashes the stored files
#: and fills in the column" as the backfill alternative - so that script
#: is the single most likely form a violation of §18 would take, and it
#: is the one form that runs outside both the application and the test
#: suite. A scan that stopped at ``app/`` would be blind to exactly the
#: thing the ADR names.
REPOSITORY_ROOT = BACKEND_ROOT.parent.parent

#: Both script trees, and the loose scripts beside them.
#:
#: The repository keeps operational scripts in two places, and the one
#: that matters here is the backend's: `scripts/maintenance/` already
#: holds a script whose whole purpose is backfilling a `documents`
#: column. A widening that scanned only the repository-root tree would
#: have missed the established home of exactly the act this test
#: forbids, while appearing to cover it.
SCRIPT_ROOTS = (
    REPOSITORY_ROOT / "scripts",
    BACKEND_ROOT / "scripts",
)

#: `migrate_project_documents.py` lives loose at the backend root and
#: rewrites `documents` rows in hand-written SQL, so a sibling of it
#: would be the least ceremonious place to put a backfill.
LOOSE_BACKEND_SCRIPTS = tuple(
    path for path in sorted(BACKEND_ROOT.glob("*.py"))
)

DOCUMENT_MODEL_MODULE = "app.models.document"

#: The three columns ADR-0036 §6 adds to ``documents``.
IDENTITY_COLUMNS = (
    "content_checksum",
    "content_checksum_algorithm",
    "content_size_bytes",
)

#: A hand-written statement that rewrites the table, in any spelling a
#: string constant could carry.
#:
#: Scoped to statements that name an identity column, because this test
#: forbids rewriting an identity and not rewriting a `documents` row.
#: The repository already updates that table in hand-written SQL for
#: unrelated columns - `migrate_project_documents.py` sets `revision`
#: and `project_name` - and flagging those would make the test fail for
#: a reason it does not hold, which is how a fitness function gets
#: weakened by whoever has to make it green again.
_SQL_UPDATE = re.compile(
    r"\bupdate\s+(\"|`|')?documents(\"|`|')?\b", re.IGNORECASE
)


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


def _sees_a_document_row(path: Path, tree: ast.Module) -> bool:
    """
    Whether a module can reach a ``documents`` row at all.

    A write to the row needs the mapped class, and the only way to hold
    it is to import it - or to be the module that declares it, which is
    where a mapper event or a convenience setter would live. Modules
    that assign the same column names on a *different* record - an
    ingestion job, a graph provenance row - are therefore out of scope
    by construction rather than by an exemption list somebody could
    append to.
    """

    if path == APP_ROOT / "models" / "document.py":
        return True

    return DOCUMENT_MODEL_MODULE in _imported_module_names(tree)


def _identity_writes(tree: ast.Module) -> set[str]:
    """Every expression in one module that would write an identity
    column onto an existing row."""

    found: set[str] = set()

    for node in ast.walk(tree):
        targets: list[ast.expr] = []

        if isinstance(node, (ast.Assign,)):
            targets = list(node.targets)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]

        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr in IDENTITY_COLUMNS
            ):
                found.add(f"assignment to .{target.attr}")

        if not isinstance(node, ast.Call):
            continue

        name = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", "")
        )

        if name == "setattr":
            for argument in node.args:
                if (
                    isinstance(argument, ast.Constant)
                    and argument.value in IDENTITY_COLUMNS
                ):
                    found.add(f"setattr(..., '{argument.value}', ...)")

        # ``query(...).update({...})`` and ``update(...).values(...)``:
        # the bulk forms, which never touch an instance and so would
        # never appear as an attribute assignment.
        if name in {"update", "values"}:
            for keyword in node.keywords:
                if keyword.arg in IDENTITY_COLUMNS:
                    found.add(f"{name}({keyword.arg}=...)")

            for argument in node.args:
                if not isinstance(argument, ast.Dict):
                    continue

                for key in argument.keys:
                    if (
                        isinstance(key, ast.Constant)
                        and key.value in IDENTITY_COLUMNS
                    ):
                        found.add(f"{name}({{'{key.value}': ...}})")

    return found


def _sql_updates(tree: ast.Module) -> set[str]:
    return {
        node.value[:60]
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _SQL_UPDATE.search(node.value)
        and any(column in node.value for column in IDENTITY_COLUMNS)
    }


# --- §18 and §19: written once, never updated ---------------------------


def test_no_production_module_writes_a_recorded_content_identity() -> None:
    """
    **ADR-0036 §28 row 9.** The single most important test in the
    milestone.

    §18 and §19 are otherwise prose: the recorded identity is set when
    the row is created and never afterwards. The first "repair" that
    writes it only when it is currently ``NULL`` makes both false, and
    that is exactly the change most likely to be waved through as
    harmless - nothing is overwritten, a gap is merely closed. It is the
    same forbidden write, because the value it writes is a claim about
    bytes the document row never observed, and because a document whose
    identity can be established later is a document whose identity can
    be established *wrongly* later, with no evidence left that it moved.

    Row construction - ``Document(content_checksum=...)`` - is the one
    permitted write and is a keyword argument, not an assignment, so it
    is not flagged here.
    """

    offenders: dict[str, set[str]] = {}

    script_files = [
        path for root in SCRIPT_ROOTS for path in _python_files(root)
    ]

    scanned = (
        _python_files(APP_ROOT)
        + _python_files(MIGRATIONS)
        + script_files
        + list(LOOSE_BACKEND_SCRIPTS)
    )

    unconditional = set(script_files) | set(LOOSE_BACKEND_SCRIPTS)

    for path in scanned:
        tree = _parse(path)
        found: set[str] = set()

        if (
            _sees_a_document_row(path, tree)
            or path.is_relative_to(MIGRATIONS)
            or path in unconditional
        ):
            found |= _identity_writes(tree)

        found |= _sql_updates(tree)

        if found:
            # Relative to the repository root, because ``scripts/`` sits
            # outside the backend and naming it against the backend root
            # would raise here - turning the one moment this test has
            # something to say into a crash.
            offenders[str(path.relative_to(REPOSITORY_ROOT))] = found

    assert offenders == {}, (
        "a recorded content identity is written after creation: "
        f"{offenders}"
    )


def test_the_scan_above_recognises_the_writes_it_forbids() -> None:
    """
    The detector, tested.

    A source scan that matched nothing would pass for the wrong reason
    forever, and the invariant above would look enforced while being
    vacuous. Each spelling below is one a repair would plausibly take,
    and the ``NULL`` guard is the one §19 names by hand.
    """

    violations = (
        "document.content_checksum = digest",
        "if document.content_checksum is None:\n"
        "    document.content_checksum = digest",
        "document.content_size_bytes = 12",
        "setattr(document, 'content_checksum_algorithm', 'sha256')",
        "session.query(Document).update({'content_checksum': digest})",
        "session.execute(update(Document).values(content_checksum=d))",
    )

    for source in violations:
        assert _identity_writes(ast.parse(source)), source

    assert _sql_updates(
        ast.parse('op.execute("UPDATE documents SET content_checksum = 1")')
    )

    # And the permitted write - construction - is not mistaken for one.
    assert not _identity_writes(
        ast.parse("Document(filename=name, content_checksum=digest)")
    )


def test_the_document_row_carries_no_lineage_or_ordering_column() -> None:
    """
    **§5 and §13**, which refuse rather than omit.

    A digest is an identity: not a timestamp, not a sequence, and
    comparable only by equality. Nothing here answers "which version came
    first" or "what did this supersede", because ordering versions
    requires lineage and lineage is undecided. Naming the refused
    columns makes their arrival an edit to this list rather than a quiet
    feature.
    """

    refused = {
        "supersedes",
        "superseded_by",
        "previous_document_id",
        "previous_content_checksum",
        "version_number",
        "is_current",
        "document_version_id",
    }

    declared = {
        node.target.id
        for node in ast.walk(_parse(APP_ROOT / "models" / "document.py"))
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    assert declared & refused == set()


# --- §26: no engineering semantics --------------------------------------

#: The surface this milestone owns: where content identity is decided,
#: where the bytes are written and hashed, and the revision that records
#: the result. Scoped deliberately - the registry and the upload route
#: carry pre-existing document vocabulary this milestone did not add, and
#: scanning them would assert something other than "no *new* semantics".
MILESTONE_SURFACE = (
    APP_ROOT / "domain" / "document_identity",
    APP_ROOT / "infrastructure" / "document_identity",
    APP_ROOT / "services" / "storage.py",
    APP_ROOT / "services" / "document_identity_service.py",
    MIGRATIONS / "3ca7e14b90d2_add_document_content_identity.py",
)

#: Engineering meaning, from ADR-0036 §26's own non-goal list. A file's
#: digest says nothing about substations, and a name from this set would
#: mean something in this context had started to.
SEMANTIC_NAMES = (
    "cable",
    "cablerun",
    "cable_run",
    "circuit",
    "terminal",
    "conductor",
    "busbar",
    "feeder",
    "connects",
    "connected_to",
    "terminates_at",
    "equipment",
    "equipment_type",
    "designation",
    "entity_id",
    "node_id",
    "edge_id",
)


def _milestone_files() -> list[Path]:
    files: list[Path] = []

    for entry in MILESTONE_SURFACE:
        if entry.is_dir():
            files.extend(_python_files(entry))
        else:
            files.append(entry)

    return files


def test_the_milestone_surface_models_no_engineering_meaning() -> None:
    """
    **ADR-0036 §28 row 21.**

    Without it, a milestone about bytes acquires a vocabulary about
    substations one plausible name at a time - and the vocabulary is
    what carries the review obligations, so it arrives without them.
    """

    offenders: dict[str, set[str]] = {}

    for path in _milestone_files():
        tree = _parse(path)

        found = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id.lower() in SEMANTIC_NAMES
        }
        found |= {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))
            and node.name.lower() in SEMANTIC_NAMES
        }

        if found:
            offenders[path.name] = found

    assert offenders == {}, f"engineering meaning was modelled: {offenders}"


def test_the_milestone_surface_reaches_no_knowledge_context() -> None:
    """
    §26 again, from the import side.

    This milestone produces one observation about a file's bytes. It
    introduces no entity, no fact, no semantic statement, no governed
    knowledge and no human assertion - ADR-0035 stays deferred, and a
    dependency on any of these would be the first sign that it had
    stopped being deferred by accident.
    """

    forbidden = (
        "app.domain.engineering_entities",
        "app.domain.engineering_facts",
        "app.domain.engineering_semantics",
        "app.domain.engineering_evidence",
        "app.domain.governed_knowledge_graph",
        "app.domain.governed_retrieval",
        "app.domain.human_review",
        "app.domain.proposed_claims",
        "app.domain.engineering_reasoning",
    )

    offenders: dict[str, set[str]] = {}

    for path in _milestone_files():
        found = {
            name
            for name in _imported_module_names(_parse(path))
            if name.startswith(forbidden)
        }

        if found:
            offenders[path.name] = found

    assert offenders == {}, f"the surface reached knowledge: {offenders}"


# --- §21: the root of the chain is inside the deterministic core --------


def test_document_identity_is_named_in_the_deterministic_core() -> None:
    """
    **ADR-0036 §28 row 22**, asserted rather than assumed.

    ``AF-DET-002`` iterates ``DETERMINISTIC_CONTEXTS``, so removing a
    name from that tuple removes coverage **and turns no test red** -
    which is precisely the failure row 22 describes. Membership is
    therefore asserted here, so the strengthening §21 records cannot be
    undone silently.

    It matters for this context in particular: ``document_identity``
    computes the first local component of every deterministic identity
    in the system, and its own boundary test - broader in libraries and
    broader in surface - omits
    ``app.application.ports.llm_provider_port``, which AF-DET-002 names.
    """

    assert "document_identity" in DETERMINISTIC_CONTEXTS
