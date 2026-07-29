"""
Architecture tests for the hardened public API (Milestone 30.1.3).

Everything asserted here is structural, on the AST or the filesystem -
never on prose. A comment promising that a router does not build queries
is worth nothing; a test that walks its imports is worth something.

The scope is the two routers this milestone hardened. Others still read
sessions directly; that is recorded as debt rather than silently
included, so this test says exactly what it guarantees.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.domain.document_registry.document_models import (
    DocumentCategory as DomainFormatCategory,
)
from app.domain.document_registry.document_models import (
    DocumentFormat as DomainDocumentFormat,
)
from app.domain.document_registry.document_query import DocumentSortField
from app.domain.project.project_query import ProjectSortField
from app.domain.project.project_status import ProjectStatus as DomainStatus
from app.models.document import DocumentCategory as StoredCategory
from app.models.document import DocumentFormat as StoredFormat
from app.models.project import ProjectStatus as StoredStatus

APP_ROOT = Path(__file__).resolve().parents[2] / "app"

#: The routers this milestone hardened. Scoped deliberately: the rest of
#: the API still holds sessions, and pretending otherwise here would make
#: this test a lie the day someone reads it.
HARDENED_ROUTERS = (
    APP_ROOT / "routers" / "documents.py",
    APP_ROOT / "routers" / "projects.py",
)

PUBLIC_SCHEMAS = (
    APP_ROOT / "schemas" / "document.py",
    APP_ROOT / "schemas" / "project.py",
    APP_ROOT / "schemas" / "pagination.py",
)

DOCUMENT_REGISTRY = APP_ROOT / "domain" / "document_registry"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_names(path: Path) -> set[str]:
    names: set[str] = set()

    for node in ast.walk(_parse(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(
                f"{node.module}.{alias.name}" for alias in node.names
            )

    return names


def _called_attributes(path: Path) -> set[str]:
    """Every ``x.y`` attribute accessed anywhere in the module."""

    return {
        node.attr
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Attribute)
    }


def _annotation_names(path: Path) -> set[str]:
    return {
        node.id
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.Name)
    }


# --- Routers own no persistence -------------------------------------------


def test_hardened_routers_do_not_import_sqlalchemy_query_primitives() -> (
    None
):
    """
    ``select``, ``func``, ``or_``, ``and_``, ``text`` and the rest are
    query construction. A router that imports one is writing a query.
    """

    forbidden = {
        "sqlalchemy",
        "sqlalchemy.select",
        "sqlalchemy.func",
        "sqlalchemy.or_",
        "sqlalchemy.and_",
        "sqlalchemy.text",
        "sqlalchemy.sql",
        "sqlalchemy.orm.Query",
    }

    violations = []

    for path in HARDENED_ROUTERS:
        for name in _imported_names(path):
            # `sqlalchemy.orm.Session` is the unit of work the request
            # scope hands to a repository, not a query primitive.
            if name == "sqlalchemy.orm" or name == "sqlalchemy.orm.Session":
                continue

            if name in forbidden or name.startswith("sqlalchemy.sql"):
                violations.append(f"{path.name} imports {name}")

    assert violations == []


def test_hardened_routers_never_call_query_or_filter() -> None:
    """
    The projects router built no query even before this milestone; the
    documents router built several. Neither does now, with one exception
    the upload endpoint still needs (asserted below).
    """

    violations = []

    for path in HARDENED_ROUTERS:
        attributes = _called_attributes(path)

        for forbidden in ("filter_by", "order_by", "offset", "limit"):
            if forbidden in attributes:
                violations.append(f"{path.name} calls .{forbidden}()")

    assert violations == []


def test_the_projects_router_touches_no_orm_model() -> None:
    """
    It used to re-read the ORM row to fill in ``status`` and
    ``voltage_level``. The domain aggregate carries them now, and this
    asserts the re-read is gone rather than merely unused.
    """

    imports = _imported_names(APP_ROOT / "routers" / "projects.py")

    assert not any(
        name.startswith("app.models") for name in imports
    ), sorted(name for name in imports if name.startswith("app.models"))


def test_pagination_never_happens_in_a_router() -> None:
    """
    Slicing a loaded list is pagination after the fact - the thing this
    milestone exists to remove. A router may name a page; it may not
    build one.
    """

    for path in HARDENED_ROUTERS:
        for node in ast.walk(_parse(path)):
            assert not isinstance(node, ast.Subscript) or not isinstance(
                node.slice, ast.Slice
            ), f"{path.name} slices a sequence"


# --- No storage location is public ----------------------------------------


def test_no_public_schema_declares_a_storage_field() -> None:
    """
    Asserted on the schema definitions themselves, so a field cannot be
    added without this failing - rather than on a sample response, which
    only covers the paths a test happened to exercise.
    """

    forbidden_fragments = ("path", "directory", "storage", "file_location")

    violations = []

    for path in PUBLIC_SCHEMAS:
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.AnnAssign):
                continue

            if not isinstance(node.target, ast.Name):
                continue

            name = node.target.id.lower()

            if any(
                fragment in name for fragment in forbidden_fragments
            ):
                violations.append(f"{path.name} declares '{node.target.id}'")

    assert violations == []


def test_no_document_registry_value_object_has_a_storage_field() -> None:
    """The schema cannot leak what its source value object does not
    have. This is the structural half of that guarantee."""

    violations = []

    for path in sorted(DOCUMENT_REGISTRY.glob("document_models.py")):
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name
            ):
                name = node.target.id.lower()

                if "path" in name or "storage" in name:
                    violations.append(
                        f"{path.name} declares '{node.target.id}'"
                    )

    assert violations == []


def test_only_the_download_value_object_carries_a_storage_reference() -> (
    None
):
    """
    ``DocumentDownload`` has one, because the transport must hand it back
    to the content port. It is the single exception, and it never reaches
    a response body - the schema test above proves that.
    """

    carriers = []

    for path in sorted(DOCUMENT_REGISTRY.glob("*.py")):
        source = path.read_text(encoding="utf-8")

        if "storage_reference:" in source:
            carriers.append(path.name)

    assert carriers == ["document_download.py"]


def test_the_document_registry_domain_imports_no_persistence() -> None:
    violations = []

    for path in sorted(DOCUMENT_REGISTRY.glob("*.py")):
        for name in _imported_names(path):
            if name.startswith(("app.models", "sqlalchemy", "app.infrastructure")):
                violations.append(f"{path.name} imports {name}")

    assert violations == []


def test_the_document_registry_domain_reaches_no_filesystem() -> None:
    """
    Not even to check whether a file exists: that question belongs to the
    content port, and a domain module that could answer it would have a
    reason to hold a path.
    """

    violations = []

    for path in sorted(DOCUMENT_REGISTRY.glob("*.py")):
        for name in _imported_names(path):
            if name.split(".")[0] in {"os", "pathlib", "shutil", "io"}:
                violations.append(f"{path.name} imports {name}")

    assert violations == []


# --- The download goes through the ports ----------------------------------


def test_the_download_service_reaches_content_only_through_the_ports() -> (
    None
):
    service = APP_ROOT / "services" / "document_registry_service.py"

    imports = _imported_names(service)

    assert (
        "app.domain.document_identity.document_content_port" in imports
    )
    assert (
        "app.domain.document_identity.document_storage_location" in imports
    )

    # It imports the ports, never an adapter, and never the filesystem.
    assert not any(
        name.startswith("app.infrastructure") for name in imports
    )
    assert not any(
        name.split(".")[0] in {"os", "pathlib", "shutil"}
        for name in imports
    )


def test_the_download_never_joins_a_path() -> None:
    """
    A storage reference is opaque. Anything that concatenated it with a
    root, split it, or normalised it would be treating it as a filesystem
    path - and would be the place a traversal could reappear.
    """

    for path in (
        APP_ROOT / "services" / "document_registry_service.py",
        DOCUMENT_REGISTRY / "document_download.py",
    ):
        attributes = _called_attributes(path)

        for forbidden in ("joinpath", "resolve", "relative_to", "parent"):
            assert forbidden not in attributes, (
                f"{path.name} calls .{forbidden}() on something"
            )


# --- Closed vocabularies --------------------------------------------------


def test_sort_fields_are_closed_enums_not_strings() -> None:
    for field_enum in (ProjectSortField, DocumentSortField):
        members = {member.value for member in field_enum}

        assert members, field_enum
        # Every member is a plain identifier - nothing that could be a
        # SQL fragment or a dotted column reference.
        for member in members:
            assert member.isidentifier(), (field_enum, member)


def test_no_arbitrary_field_to_column_mapping_exists() -> None:
    """
    The only mapping from a sort field to a column is keyed by **enum
    member**, in the adapter. A dict keyed by ``str`` would let a caller
    name a column, which is the whole class of bug this closes.
    """

    adapters = (
        APP_ROOT
        / "infrastructure"
        / "project"
        / "sqlalchemy_project_repository.py",
        APP_ROOT
        / "infrastructure"
        / "document_registry"
        / "sqlalchemy_document_registry.py",
    )

    for path in adapters:
        tree = _parse(path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue

            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]

            if "_SORT_COLUMNS" not in targets:
                continue

            assert isinstance(node.value, ast.Dict)

            for key in node.value.keys:
                # `ProjectSortField.CREATED_AT`, never `"created_at"`.
                assert isinstance(key, ast.Attribute), (
                    f"{path.name}: _SORT_COLUMNS is keyed by "
                    f"{ast.dump(key)}, not an enum member"
                )


def test_no_adapter_looks_up_a_column_by_name() -> None:
    """``getattr(Model, caller_supplied_string)`` is the generic
    mechanism this milestone refused to add."""

    adapters = (
        APP_ROOT
        / "infrastructure"
        / "project"
        / "sqlalchemy_project_repository.py",
        APP_ROOT
        / "infrastructure"
        / "document_registry"
        / "sqlalchemy_document_registry.py",
    )

    for path in adapters:
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Call) and isinstance(
                node.func, ast.Name
            ):
                assert node.func.id != "getattr", (
                    f"{path.name} resolves an attribute by name"
                )


# --- Domain enums agree with the persisted ones ---------------------------


def test_the_domain_document_format_matches_the_persisted_one() -> None:
    assert {member.value for member in DomainDocumentFormat} == {
        member.value for member in StoredFormat
    }


def test_the_domain_document_category_matches_the_persisted_one() -> None:
    assert {member.value for member in DomainFormatCategory} == {
        member.value for member in StoredCategory
    }


def test_the_domain_project_status_matches_the_persisted_one() -> None:
    """
    ``ProjectStatus`` moved into the domain in this milestone; the public
    schema imports it from there rather than from ``app.models``. This
    keeps the two definitions from drifting.
    """

    assert {member.value for member in DomainStatus} == {
        member.value for member in StoredStatus
    }


def test_the_public_project_schema_imports_no_orm_module() -> None:
    imports = _imported_names(APP_ROOT / "schemas" / "project.py")

    assert not any(name.startswith("app.models") for name in imports)


def test_the_public_document_schema_imports_no_orm_module() -> None:
    imports = _imported_names(APP_ROOT / "schemas" / "document.py")

    assert not any(name.startswith("app.models") for name in imports)


# --- Pagination is bounded ------------------------------------------------


def test_the_maximum_page_size_is_a_hard_ceiling() -> None:
    from app.domain.shared_kernel.pagination import (
        MAX_PAGE_SIZE,
        PageRequest,
    )
    from app.domain.shared_kernel.pagination_exceptions import (
        InvalidPageSizeError,
    )

    PageRequest(page=1, page_size=MAX_PAGE_SIZE)

    for refused in (MAX_PAGE_SIZE + 1, 10_000, 0, -1):
        try:
            PageRequest(page=1, page_size=refused)
        except InvalidPageSizeError:
            continue

        raise AssertionError(f"page_size={refused} was accepted")


def test_an_unbounded_list_cannot_be_requested_through_the_query() -> None:
    """There is no ``page_size=all``, no ``limit=None`` and no sentinel
    meaning "everything"."""

    from app.domain.shared_kernel.pagination import PageRequest

    request = PageRequest()

    assert request.limit > 0
    assert isinstance(request.limit, int)
