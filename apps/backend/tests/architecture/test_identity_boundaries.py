"""
Architecture tests for the identity and audit contexts.

Everything here is structural - on the AST or the filesystem - never on
prose. The load-bearing one is
``test_no_engineering_domain_module_imports_identity``: it is what keeps
the deterministic pipeline deterministic, and it will still be checking
long after everybody who remembers why has left.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

IDENTITY_DOMAIN = APP_ROOT / "domain" / "identity"
AUDIT_DOMAIN = APP_ROOT / "domain" / "audit"

#: Every bounded context that models the deterministic pipeline. None of
#: them may learn that users exist.
ENGINEERING_DOMAINS = (
    "canonical_pdf",
    "canonical_text",
    "engineering_evidence",
    "engineering_entities",
    "engineering_facts",
    "engineering_semantics",
    "ontology",
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


# --- The rule the whole EPIC turns on ------------------------------------


def test_no_engineering_domain_module_imports_identity() -> None:
    """
    **The deterministic pipeline must not know who is running it.**

    An entity, a fact and a semantic statement are functions of the
    document's bytes and the versioned rules that read them. The moment
    one of them could reference a user, running the pipeline twice under
    two logins could produce two different answers, idempotency would
    break, artefact re-use would stop working, and "why does the system
    believe this?" would acquire an answer involving a person.

    Audit identity attaches to *actions*. This test is the fence.
    """

    offenders: list[str] = []

    # Matched on the exact module path. `document_identity` is a
    # different context entirely - the identity of a document's *bytes* -
    # and a substring match would flag it.
    forbidden = ("app.domain.identity", "app.domain.audit")

    for context in ENGINEERING_DOMAINS:
        for module in _modules(APP_ROOT / "domain" / context):
            for imported in _imports(module):
                if any(imported.startswith(item) for item in forbidden):
                    offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_no_engineering_persistence_model_has_a_user_column() -> None:
    """
    The same rule, one layer down. A nullable ``user_id`` that nobody
    populates today is a column somebody populates next year.
    """

    engineering_models = (
        "canonical_pdf.py",
        "canonical_text.py",
        "engineering_evidence.py",
        "engineering_entities.py",
        "engineering_facts.py",
        "engineering_semantics.py",
    )

    forbidden = {"user_id", "actor", "created_by", "owner", "owner_user_id"}

    offenders: list[str] = []

    for name in engineering_models:
        path = APP_ROOT / "models" / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # Column *declarations*, not prose. "extractor" contains "actor",
        # and a test that flagged a docstring would be turned off rather
        # than fixed.
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name
            ):
                if node.target.id in forbidden:
                    offenders.append(f"{name}.{node.target.id}")

    assert offenders == []


# --- The identity domain is a domain -------------------------------------


def test_the_identity_domain_imports_no_infrastructure() -> None:
    """
    The dependency rule, applied to the newest context. It may not know
    about SQLAlchemy, FastAPI, the filesystem or an ORM model.
    """

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

    for module in _modules(IDENTITY_DOMAIN) + _modules(AUDIT_DOMAIN):
        for imported in _imports(module):
            if any(imported.startswith(item) for item in forbidden):
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_the_identity_domain_hashes_nothing_itself() -> None:
    """
    Hashing is an adapter. The domain declares *that* passwords are
    hashed, salted and upgradable; which function does it is replaceable
    without the domain learning a new one.
    """

    offenders: list[str] = []

    for module in _modules(IDENTITY_DOMAIN):
        # `token_generator_port` documents the SHA-256 fingerprint in
        # prose; the check is on imports, so prose is not a violation.
        for imported in _imports(module):
            if imported in {"hashlib", "hmac", "secrets", "bcrypt"}:
                offenders.append(f"{module.name} imports {imported}")

    assert offenders == []


def test_password_hashing_uses_an_established_function() -> None:
    """
    No invented cryptography. The adapter calls a standard KDF, and this
    test names it so replacing it is a deliberate act.
    """

    source = (
        APP_ROOT
        / "infrastructure"
        / "identity"
        / "scrypt_password_hasher.py"
    ).read_text(encoding="utf-8")

    assert "hashlib.scrypt" in source
    assert "hmac.compare_digest" in source

    # A hand-rolled construction would look like one of these.
    for invented in ("def _xor", "sha256(password", "md5", "sha1("):
        assert invented not in source


def test_session_tokens_come_from_a_cryptographic_source() -> None:
    source = (
        APP_ROOT
        / "infrastructure"
        / "identity"
        / "secrets_token_generator.py"
    ).read_text(encoding="utf-8")

    assert "secrets.token_urlsafe" in source
    assert "import random" not in source


# --- Nothing stores what it must not -------------------------------------


def test_no_model_declares_a_plaintext_password_column() -> None:
    source = (APP_ROOT / "models" / "identity.py").read_text(
        encoding="utf-8"
    )

    assert "encoded_credential" in source

    for forbidden in ("password", "plaintext", "session_token"):
        assert f"{forbidden}: Mapped" not in source


def test_the_session_table_stores_a_fingerprint_not_a_token() -> None:
    """
    The reason a copy of the database is not a set of live logins.
    """

    source = (APP_ROOT / "models" / "identity.py").read_text(
        encoding="utf-8"
    )

    assert "token_fingerprint: Mapped[str]" in source
    assert "token: Mapped[str]" not in source


def test_the_audit_repository_port_offers_no_update_or_delete() -> None:
    """
    A trail an application can edit proves nothing, so the interface an
    implementer must satisfy offers no way to try.
    """

    source = (AUDIT_DOMAIN / "audit_repository.py").read_text(
        encoding="utf-8"
    )

    assert "def record" in source
    assert "def list_recent" in source

    for forbidden in ("def update", "def delete", "def remove", "def purge"):
        assert forbidden not in source


# --- Authorization is not authentication ---------------------------------


def test_the_authentication_service_makes_no_authorization_decision() -> (
    None
):
    """
    Merging the two is how "may this user read that project?" ends up
    inside a login function.
    """

    source = (
        APP_ROOT / "services" / "authentication_service.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("Capability.", "permits(", "is_administrator"):
        assert forbidden not in source


def test_authorization_is_a_pure_function_of_role_and_capability() -> None:
    """
    No request, no session, no database - checked on the imports and the
    signatures rather than on the prose, which says the same thing and is
    allowed to.
    """

    path = IDENTITY_DOMAIN / "identity_roles.py"

    assert _imports(path) <= {"__future__", "enum"}

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    parameters = {
        argument.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for argument in node.args.args
    }

    assert parameters <= {"role", "capability"}


def test_only_the_security_module_reads_the_session_cookie() -> None:
    """
    Routes never touch cookies. One place resolves an identity, and it is
    the place the tests point at.
    """

    offenders: list[str] = []

    for module in _modules(APP_ROOT / "routers"):
        if module.name in {"security.py", "authentication.py"}:
            continue

        source = module.read_text(encoding="utf-8")

        if "request.cookies" in source or "SESSION_COOKIE" in source:
            offenders.append(module.name)

    assert offenders == []
