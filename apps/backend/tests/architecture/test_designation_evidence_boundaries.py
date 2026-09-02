"""
Architecture invariants for real-world designation evidence
(EPIC 32.E2).

This milestone taught the extractor to see designation forms it had been
blind to. The risk in that is not the seeing - it is that a richer
observation quietly becomes a richer *claim*. These tests hold the line
between the two.

The three that matter most:

1. **The dot stays lexical.** ``-E1.L`` is one designation. Nothing in
   the platform may turn it into ``-E1`` plus a relationship, and EPIC
   32.3 remains blocked regardless of how well the form is now read.
2. **Better extraction added no ontology.** Fact predicates, statement
   types, graph kinds and reasoning families are all exactly as EPIC
   32.2 left them.
3. **Real and synthetic corpus evidence stay distinguishable**, so an
   evidence metric can never quietly measure the extractor against
   strings written to make it pass.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
EVIDENCE_ROOT = APP_ROOT / "domain" / "engineering_evidence"


def _modules(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _executable_source(path: Path) -> str:
    """One module's code, with documentation removed - docstrings must
    be free to name what the code refuses to do."""

    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body.pop(0)

    return "\n".join(
        line
        for line in ast.unparse(tree).splitlines()
        if not line.strip().startswith("#")
    )


# --- 1. The dot stays lexical -------------------------------------------


def test_a_dot_qualified_designation_yields_one_observation() -> None:
    from app.domain.canonical_text.canonical_text_segmenter import (
        segment_canonical_document,
    )
    from app.domain.engineering_evidence.evidence_extractor import (
        extract_evidence,
    )
    from app.domain.engineering_evidence.evidence_models import EvidenceType
    from tests.domain._canonical_text_support import (
        page,
        representation,
        span,
        text_block,
    )

    source = representation(
        page(1, text_block(0, span(0, 0, "MORSETTIERA -E.AM +GSH003")))
    )
    result = extract_evidence(segment_canonical_document(source))

    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.DESIGNATION)
    ] == ["-E.AM"]


def test_no_module_decomposes_a_designation_on_the_dot() -> None:
    """
    A split on ``.`` inside the evidence or entity contexts would be
    decomposition by another name - the mechanism EPIC 32.3 is blocked
    from having.
    """

    roots = (
        EVIDENCE_ROOT,
        APP_ROOT / "domain" / "engineering_entities",
        APP_ROOT / "domain" / "engineering_facts",
        APP_ROOT / "domain" / "engineering_semantics",
    )

    for root in roots:
        for module in _modules(root):
            source = _executable_source(module)

            for forbidden in (
                "split('.')",
                'split(".")',
                "partition('.')",
                'partition(".")',
                "rsplit('.')",
                'rsplit(".")',
            ):
                assert forbidden not in source, f"{module.name}: {forbidden}"


def test_no_hierarchy_vocabulary_exists_anywhere() -> None:
    """EPIC 32.3 stays blocked. Reading the form better did not authorise
    the relationship."""

    from app.domain.engineering_facts.fact_predicates import FactPredicate
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
        GraphNodeKind,
    )

    forbidden = {
        "PART_OF",
        "CONTAINS",
        "PARENT_OF",
        "CHILD_OF",
        "IS_DESIGNATED_UNDER",
        "HAS_PARENT",
        "HAS_COMPONENT",
        "HAS_PRODUCT_ASPECT_PARENT",
        "MOUNTED_IN",
        "BELONGS_TO",
    }

    for vocabulary in (
        FactPredicate,
        SemanticStatementType,
        GraphEdgeKind,
        GraphNodeKind,
    ):
        declared = {member.name for member in vocabulary}

        assert not declared & forbidden, vocabulary.__name__


# --- 2. Better extraction added no ontology -----------------------------


def test_the_governed_vocabularies_are_exactly_as_32_2_left_them() -> None:
    from app.domain.engineering_entities.entity_models import EntityType
    from app.domain.engineering_facts.fact_predicates import FactPredicate
    from app.domain.engineering_reasoning.reasoning_vocabulary import (
        ReasoningRuleFamily,
    )
    from app.domain.engineering_semantics.semantic_statement_types import (
        SemanticStatementType,
    )
    from app.domain.governed_knowledge_graph.graph_vocabulary import (
        GraphEdgeKind,
        GraphNodeKind,
    )

    assert {member.value for member in GraphNodeKind} == {
        "engineering_asset",
        "engineering_quantity",
        "structural_location",
    }
    assert {member.value for member in GraphEdgeKind} == {
        "has_rated_power",
        "is_located_in",
    }
    assert {member.value for member in SemanticStatementType} == {
        "has_rated_power",
        "is_located_in",
    }
    assert {member.value for member in FactPredicate} == {
        "has_associated_quantity",
        "has_location_aspect",
    }
    assert {member.value for member in EntityType} == {
        "equipment_designation",
        "engineering_quantity",
        "structural_location",
    }
    assert {member.value for member in ReasoningRuleFamily} == {
        "quantity_consistency",
        "structural_relationship",
    }


def test_the_evidence_vocabulary_gained_nothing() -> None:
    """32.E2 hardened rules, not categories: every real form it now sees
    is a designation or a location aspect, both of which already
    existed."""

    from app.domain.engineering_evidence.evidence_models import EvidenceType

    assert {member.value for member in EvidenceType} == {
        "designation",
        "voltage_value",
        "current_value",
        "power_value",
        "cable_section_value",
        "location_aspect",
    }


def test_the_reasoning_rules_are_unchanged() -> None:
    from app.domain.engineering_reasoning import (
        quantity_consistency_rule,
        shared_structural_location_rule,
    )

    assert (
        quantity_consistency_rule.QUANTITY_CONSISTENCY_RULE.rule_id
        == "governed_quantity_consistency"
    )
    assert (
        shared_structural_location_rule.SHARED_STRUCTURAL_LOCATION_RULE
        .rule_id
        == "shared_structural_location"
    )
    assert (
        shared_structural_location_rule.SHARED_STRUCTURAL_LOCATION_RULE
        .rule_version
        == "1.0"
    )


# --- 3. Extraction stays deterministic and offline ----------------------


def test_extraction_uses_no_model_or_similarity() -> None:
    forbidden = (
        "anthropic",
        "openai",
        "embedding",
        "similarity",
        "levenshtein",
        "difflib",
        "fuzzy",
        "confidence",
        "score",
        "probability",
        "random",
    )

    for module in _modules(EVIDENCE_ROOT):
        lowered = _executable_source(module).lower()

        for banned in forbidden:
            assert banned not in lowered, f"{module.name}: {banned}"


def test_the_evidence_context_imports_no_infrastructure() -> None:
    for module in _modules(EVIDENCE_ROOT):
        tree = ast.parse(module.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            names = []

            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]

            for name in names:
                for banned in (
                    "sqlalchemy",
                    "fastapi",
                    "app.models",
                    "app.database",
                    "app.infrastructure",
                    "fitz",
                ):
                    assert not name.startswith(banned), (
                        f"{module.name} imports {name}"
                    )


def test_evidence_writes_no_graph() -> None:
    for module in _modules(EVIDENCE_ROOT):
        source = _executable_source(module)

        for banned in ("upsert_node", "upsert_edge", "promote", "commit("):
            assert banned not in source, f"{module.name}: {banned}"


# --- 4. Real and synthetic corpus evidence stay distinguishable ---------


def test_the_corpus_marks_which_documents_are_real() -> None:
    """
    An evidence metric that could not tell a transcribed drawing from a
    string written to exercise a rule would be measuring the extractor
    partly against itself.
    """

    from app.infrastructure.evidence_evaluation.yaml_reference_corpus_repository import (  # noqa: E501
        YamlReferenceCorpusRepository,
    )

    corpus = YamlReferenceCorpusRepository().load("substation_reference")
    real = [doc for doc in corpus.documents if doc.is_real_source]

    assert real, "the corpus carries no real-source documents"

    for document in real:
        assert document.source is not None
        assert document.source.document_code
        assert document.source.page_number > 0
        # Not a length check. Under ADR-0033 the digest is SHA-256
        # over the handle, so this fails if either field is edited on
        # its own - and it enforces the shared-source invariant that
        # nothing else in the suite guards: two entries transcribed
        # from one drawing carry one handle and therefore one digest.
        assert document.source.source_ref_digest == hashlib.sha256(
            document.source.document_code.encode("utf-8")
        ).hexdigest()


def test_a_real_corpus_document_records_no_local_path() -> None:
    """A corpus that recorded ``C:\\Users\\...`` would be reproducible on
    exactly one machine."""

    corpus_file = (
        APP_ROOT
        / "domain"
        / "evidence_evaluation"
        / "corpora"
        / "substation_reference.yaml"
    )
    text = corpus_file.read_text(encoding="utf-8")

    for banned in ("C:\\", "/Users/", "/home/", "storage/documents"):
        assert banned not in text, banned


def test_no_token_value_blacklist_exists() -> None:
    """
    Token identity alone may never suppress a designation.

    A module-level tuple of forbidden words would encode "this string is
    never an engineering designation" as universal truth - a claim the
    platform has no source-authoritative basis to make, and one that
    converts a visible false positive into an invisible false negative
    the day a real object carries that designation.

    The one exclusion `matches_designation` applies is **structural**,
    not lexical: a standalone location aspect names a place, so the
    location rule observes it instead.
    """

    source = _executable_source(EVIDENCE_ROOT / "evidence_rules.py")

    for forbidden in (
        "SUBSTANCE_NOTATION",
        "not in SUBSTANCE",
        "FORBIDDEN_TOKENS",
        "EXCLUDED_TOKENS",
        "NOT_DESIGNATIONS",
        "BLACKLIST",
    ):
        assert forbidden not in source, forbidden

    for chemical in ('"SF6"', "'SF6'", '"CO2"', '"N2"', '"O2"'):
        assert chemical not in source, chemical


def test_shape_equivalent_tokens_are_treated_alike() -> None:
    """
    ``SF6`` is shaped exactly like ``MI1``, ``MO2`` and ``Q8``. Whatever
    the extractor decides, it must decide the same thing for all of them
    - a divergence could only come from a curated list.
    """

    from app.domain.engineering_evidence.evidence_rules import (
        matches_designation,
    )

    verdicts = {
        token: matches_designation(token)
        for token in ("SF6", "MI1", "MO2", "Q8", "B7", "TR1")
    }

    assert len(set(verdicts.values())) == 1, verdicts
