"""
Architecture tests for the Canonical Spreadsheet Representation (ADR-0034).

A workbook is the second source family this platform reads, and it forks
the derivation chain at the root rather than extending it. Three
boundaries have to hold, and none of them can be left to discipline.

1. **It transcribes; it does not interpret.** No LLM, no header
   detection, no formula evaluation, no engineering vocabulary. What it
   stores is what the reader observed.
2. **It is the only place a workbook is decoded**, and the two source
   families never meet: nothing here imports the PDF lineage, and
   nothing in the PDF lineage imports this one.
3. **It borrows no PDF word.** A worksheet is not a page and a row is
   not a line. Naming them so would be the same mistake as calling a
   heading a section, and every consumer downstream would inherit it.

The third is the one a reviewer cannot check by reading, because the
mistake looks harmless in any single file. It is asserted here instead.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_ROOT = APP_ROOT / "domain"

SPREADSHEET_DOMAIN_ROOT = DOMAIN_ROOT / "canonical_spreadsheet"
SPREADSHEET_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "canonical_spreadsheet"
EVIDENCE_DOMAIN_ROOT = DOMAIN_ROOT / "spreadsheet_evidence"
EVIDENCE_ADAPTER_ROOT = APP_ROOT / "infrastructure" / "spreadsheet_evidence"
SPREADSHEET_SERVICE = APP_ROOT / "services" / "canonical_spreadsheet_service.py"

# The whole lineage. Every boundary below scans all of it: a test that
# checked only the representation would leave the evidence context free
# to do the very thing the check exists to forbid.
SPREADSHEET_FAMILY = (
    SPREADSHEET_DOMAIN_ROOT,
    SPREADSHEET_ADAPTER_ROOT,
    EVIDENCE_DOMAIN_ROOT,
    EVIDENCE_ADAPTER_ROOT,
)
SPREADSHEET_DOMAINS = (SPREADSHEET_DOMAIN_ROOT, EVIDENCE_DOMAIN_ROOT)

# The library that opens a workbook. Exactly one module may import it,
# for the reason the PDF context gives about PyMuPDF: an extractor that
# re-decoded the bytes would do so under whatever version happened to be
# installed that day, and would silently destroy reproducibility.
WORKBOOK_LIBRARIES = frozenset(
    {"openpyxl", "xlrd", "pyexcel", "pandas", "calamine", "python_calamine"}
)

# Evaluating a formula is not reading a file. A value this platform
# computed would be indistinguishable in the record from a value the
# engineer's spreadsheet computed, so no evaluator may be imported.
FORMULA_EVALUATORS = frozenset({"formulas", "pycel", "xlcalculator", "koala"})

# The PDF lineage. The two families share a root and nothing else.
PDF_LINEAGE = ("app.domain.canonical_pdf", "app.domain.canonical_text")

# Words that carry a page-oriented meaning. A worksheet has no page, no
# block, no span and no reading order, and borrowing the vocabulary would
# make the model claim structure the file does not have.
PDF_VOCABULARY = (
    "page_number",
    "block_reading_order",
    "reading_order",
    "bounding_box",
    "line_index",
    "paragraph_index",
    "section_index",
    "span_reading_order",
)

# An interpretation this milestone refuses. Deciding that row 1 - or row
# 7, after a title block - is a header is a guess, and nothing here can
# validate a guess. The moment one of these names exists, every reader
# downstream treats the guess as an observation.
INTERPRETATION_NAMES = (
    "header",
    "header_row",
    "column_name",
    "column_header",
    "field_name",
    "record",
    "register_kind",
    "table_region",
)

# Engineering meaning. A cable register read here yields cells at stated
# coordinates; that two of them share a row is a fact about a grid, and a
# connection is a judgement with nowhere to live in this model.
SEMANTIC_NAMES = (
    "cable",
    "cablerun",
    "circuit",
    "terminal",
    "conductor",
    "connects",
    "connected_to",
    "from_id",
    "to_id",
    "source_endpoint",
    "destination",
    "entity_id",
    "equipment_type",
    "node_id",
    "edge_id",
)


def _python_files(*roots: Path) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
        elif root.is_file():
            files.append(root)
    return files


def _imported_names(path: Path) -> set[str]:
    """Every module named by an import in one file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def test_only_the_reader_adapter_opens_a_workbook() -> None:
    """One module decodes a workbook. Every consumer reads the port."""

    reader = SPREADSHEET_ADAPTER_ROOT / "openpyxl_workbook_reader.py"
    offenders: dict[str, set[str]] = {}
    for path in _python_files(APP_ROOT):
        if path == reader:
            continue
        found = {
            name
            for name in _imported_names(path)
            if _top_level(name) in WORKBOOK_LIBRARIES
        }
        if found:
            offenders[str(path.relative_to(APP_ROOT))] = found
    assert offenders == {}, (
        "a workbook library is imported outside the one reader adapter: "
        f"{offenders}"
    )


def test_nothing_evaluates_a_formula() -> None:
    """
    The workbook records a formula and the value some other application
    cached into the file. It never computes one.
    """

    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        found = {
            name
            for name in _imported_names(path)
            if _top_level(name) in FORMULA_EVALUATORS
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, f"a formula evaluator is imported: {offenders}"


def test_the_spreadsheet_domain_holds_no_infrastructure_dependency() -> None:
    """The domain declares the port; the adapter holds the library."""

    forbidden = {
        "sqlalchemy",
        "fastapi",
        "pydantic",
        "httpx",
        "requests",
        "os",
        "pathlib",
        "shutil",
        "tempfile",
        "boto3",
    }
    forbidden_prefixes = (
        "app.models",
        "app.database",
        "app.infrastructure",
        "app.routers",
        "app.schemas",
        "app.services",
        "app.application",
    )
    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_DOMAINS):
        found = {
            name
            for name in _imported_names(path)
            if _top_level(name) in forbidden
            or name.startswith(forbidden_prefixes)
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, f"the domain reached outside itself: {offenders}"


def test_the_two_source_families_never_meet() -> None:
    """
    A workbook and a PDF share a root and nothing else. A shared import
    would let one family's assumptions reach the other, which is the
    whole reason the chain forks rather than widening.
    """

    reaching_pdf: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        found = {
            name
            for name in _imported_names(path)
            if name.startswith(PDF_LINEAGE)
        }
        if found:
            reaching_pdf[path.name] = found
    assert reaching_pdf == {}, (
        f"spreadsheet reached the PDF lineage: {reaching_pdf}"
    )

    reaching_spreadsheet: dict[str, set[str]] = {}
    for root in (DOMAIN_ROOT / "canonical_pdf", DOMAIN_ROOT / "canonical_text"):
        for path in _python_files(root):
            found = {
                name
                for name in _imported_names(path)
                if "canonical_spreadsheet" in name or "spreadsheet_evidence" in name
            }
            if found:
                reaching_spreadsheet[path.name] = found
    assert reaching_spreadsheet == {}, (
        f"the PDF lineage reached the spreadsheet family: {reaching_spreadsheet}"
    )


def test_the_representation_borrows_no_page_vocabulary() -> None:
    """
    A worksheet is not a page and a row is not a line.

    This is asserted rather than reviewed because the mistake looks
    harmless in any single file: one ``page_number`` field, added for
    symmetry, and every consumer downstream inherits a claim the file
    never made.
    """

    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = {
            node.id if isinstance(node, ast.Name) else node.attr
            for node in ast.walk(tree)
            if isinstance(node, (ast.Name, ast.Attribute))
            and (node.id if isinstance(node, ast.Name) else node.attr)
            in PDF_VOCABULARY
        }
        found |= {
            target.target.id
            for target in ast.walk(tree)
            if isinstance(target, ast.AnnAssign)
            and isinstance(target.target, ast.Name)
            and target.target.id in PDF_VOCABULARY
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, (
        f"PDF vocabulary appears in the spreadsheet family: {offenders}"
    )


def test_there_is_nowhere_to_record_a_header() -> None:
    """
    Nothing in this milestone can *validate* a header guess, so nothing
    in it may record one. A guess that cannot be checked is wrong
    silently, and the wrong answer propagates as a whole mislabelled
    register.
    """

    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = {
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id.lower() in INTERPRETATION_NAMES
        }
        found |= {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and node.name.lower() in INTERPRETATION_NAMES
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, f"a header interpretation was modelled: {offenders}"


def test_the_representation_has_nowhere_to_record_engineering_meaning() -> None:
    """
    Row adjacency is a fact about a grid. A connection is a judgement,
    and this milestone introduces no place to keep one.
    """

    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
            if isinstance(node, ast.ClassDef) and node.name.lower() in SEMANTIC_NAMES
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, f"engineering meaning was modelled: {offenders}"


def test_the_spreadsheet_family_reaches_no_knowledge_context() -> None:
    """
    This milestone produces observations about a workbook and nothing
    else: no entity, no fact, no semantic statement, no governed
    knowledge. The absence is asserted rather than intended.
    """

    forbidden = (
        "app.domain.engineering_entities",
        "app.domain.engineering_facts",
        "app.domain.engineering_semantics",
        "app.domain.governed_knowledge_graph",
        "app.domain.human_review",
        "app.domain.proposed_claims",
        "app.domain.engineering_index",
        "app.domain.engineering_engine",
        "app.domain.prompt_builder",
        "app.services.knowledge_promotion_service",
    )
    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        found = {
            name for name in _imported_names(path) if name.startswith(forbidden)
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, (
        f"the spreadsheet family reached knowledge: {offenders}"
    )


def test_the_spreadsheet_family_reaches_no_llm() -> None:
    """A workbook is read deterministically or not at all."""

    forbidden = {"anthropic", "openai", "cohere", "transformers", "torch"}
    # The three application-layer names are the ones AF-DET-002 bans and
    # this list originally missed: they are provider-neutral, so a module
    # importing them looks innocent, and none of the vendor names above
    # would have caught it.
    forbidden_prefixes = (
        "app.domain.llm",
        "app.application.llm",
        "app.infrastructure.llm",
        "app.application.services.llm_invocation_service",
        "app.application.services.llm_runtime",
        "app.application.ports.llm_provider_port",
    )
    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_FAMILY):
        found = {
            name
            for name in _imported_names(path)
            if _top_level(name) in forbidden or name.startswith(forbidden_prefixes)
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, (
        f"an LLM dependency reached the spreadsheet family: {offenders}"
    )


def test_the_reader_port_receives_bytes_rather_than_a_location() -> None:
    """
    The port takes content, so the adapter cannot open a file, walk a
    directory or reach storage. The document content port stays the one
    governed route into stored bytes.
    """

    from app.domain.canonical_spreadsheet.workbook_reader_port import (
        WorkbookReaderPort,
    )

    parameters = inspect.signature(WorkbookReaderPort.read).parameters

    assert parameters["content"].annotation == "bytes"
    for named_location in ("path", "file_path", "location", "storage_reference"):
        assert named_location not in parameters


def test_the_spreadsheet_domain_never_opens_a_file() -> None:
    """No open(), no Path, no filesystem call anywhere in the domain."""

    offenders: dict[str, set[str]] = {}
    for path in _python_files(*SPREADSHEET_DOMAINS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"open", "Path"}
        }
        if found:
            offenders[path.name] = found
    assert offenders == {}, f"the domain opened a file: {offenders}"


def test_the_shared_failure_codes_agree_with_canonicalisation() -> None:
    """
    The five shared causes are restated here rather than imported, so
    that PDF concerns do not leak into a context that has none. Restating
    is only safe while the values agree, which is what this asserts.
    """

    from app.domain.canonical_pdf.canonical_pdf_failures import (
        CanonicalizationFailureCode,
    )
    from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (
        WorkbookCanonicalizationFailureCode,
    )

    shared = (
        "DOCUMENT_NOT_FOUND",
        "UNSUPPORTED_FORMAT",
        "CONTENT_NOT_FOUND",
        "CONTENT_INACCESSIBLE",
        "EMPTY_CONTENT",
    )
    for name in shared:
        assert (
            WorkbookCanonicalizationFailureCode[name].value
            == CanonicalizationFailureCode[name].value
        ), f"{name} disagrees between the two canonicalisation contexts"


def test_the_spreadsheet_service_reaches_no_storage() -> None:
    """
    Three closed-list allowlists now name this service as a legitimate
    reader of raw content, each with a comment saying it reaches bytes
    only through the governed content port and cannot open a file.

    That was prose. This is the assertion, mirroring the guard the PDF
    service has carried since Milestone 26.1 - a claim in a comment is
    worth exactly as much as the next edit that ignores it.
    """

    forbidden = {"pathlib", "os", "io", "shutil"}
    found = {
        name
        for name in _imported_names(SPREADSHEET_SERVICE)
        if _top_level(name) in forbidden
        or name.startswith("app.services.storage")
    }
    assert found == set(), f"the spreadsheet service reached storage: {found}"

    tree = ast.parse(SPREADSHEET_SERVICE.read_text(encoding="utf-8"))
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "Path"}
    }
    assert calls == set(), f"the spreadsheet service opened a file: {calls}"
