"""
Architecture invariants of the deterministic artifact identity chain
(EPIC 32.E2.4).

Supersedes the natural-key reuse fitness functions of EPIC 32.E2.1 and
32.E2.2. The rule they enforced by enumeration - every downstream key
must copy every upstream version - is now enforced by construction:

    identity = H(identity contract, kind, upstream identity, local
                 derivation identity)

so what these tests hold is the *shape* of that construction. The
behavioural half lives in
``tests/services/test_artifact_identity_reuse.py``.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
MIGRATIONS = APP_ROOT.parent / "migrations" / "versions"

# The six persisted deterministic artifacts, in derivation order.
#
# This tuple is the audit: a seventh persisted deterministic artifact is
# an architecture decision, and adding one without a line here fails
# ``test_no_persisted_reuse_boundary_is_unaccounted_for``.
CHAIN = (
    dict(
        kind="CANONICAL_PDF",
        context="canonical_pdf",
        port=("app.domain.canonical_pdf.canonical_representation_repository",
              "CanonicalRepresentationRepository"),
        record=("app.models.canonical_pdf", "CanonicalPdfRepresentation"),
        service=("app.services.canonical_pdf_service",
                 "canonicalize_document"),
        local=("representation_version",),
    ),
    dict(
        kind="CANONICAL_TEXT",
        context="canonical_text",
        port=("app.domain.canonical_text.canonical_text_repository",
              "CanonicalTextRepository"),
        record=("app.models.canonical_text", "CanonicalTextDocumentRecord"),
        service=("app.services.canonical_text_service", "segment_document"),
        local=("segmentation_version",),
    ),
    dict(
        kind="EVIDENCE_SET",
        context="engineering_evidence",
        port=("app.domain.engineering_evidence."
              "engineering_evidence_repository",
              "EngineeringEvidenceRepository"),
        record=("app.models.engineering_evidence",
                "EngineeringEvidenceSetRecord"),
        service=("app.services.engineering_evidence_service",
                 "extract_document_evidence"),
        local=("extraction_policy_version",),
    ),
    dict(
        kind="ENTITY_SET",
        context="engineering_entities",
        port=("app.domain.engineering_entities.engineering_entity_repository",
              "EngineeringEntityRepository"),
        record=("app.models.engineering_entities",
                "EngineeringEntitySetRecord"),
        service=("app.services.engineering_entity_service",
                 "resolve_document_entities"),
        local=("resolution_policy_version", "entity_model_version"),
    ),
    dict(
        kind="FACT_SET",
        context="engineering_facts",
        port=("app.domain.engineering_facts.engineering_fact_repository",
              "EngineeringFactRepository"),
        record=("app.models.engineering_facts", "EngineeringFactSetRecord"),
        service=("app.services.engineering_fact_service",
                 "construct_document_facts"),
        local=("fact_policy_version", "fact_contract_version"),
    ),
    dict(
        kind="SEMANTIC_SET",
        context="engineering_semantics",
        port=("app.domain.engineering_semantics."
              "engineering_semantic_repository",
              "EngineeringSemanticRepository"),
        record=("app.models.engineering_semantics",
                "EngineeringSemanticSetRecord"),
        service=("app.services.engineering_semantic_service",
                 "interpret_document_facts"),
        local=("semantic_policy_version", "semantic_contract_version"),
    ),
)


CATALOGUE_PINS = {
    # stage -> (policy version, fingerprint of the effective catalogue)
    #
    # Every stage's rules, pinned beside the policy version that is
    # supposed to identify them. See
    # ``test_a_rule_version_change_cannot_hide_behind_its_policy``.
    "extraction": ("2.0", "9cbc2819b4957551afe58ef551d7c36acc60daa1b253fd5bfe80c818b88aa6a4"),
    "resolution": ("1.0", "a4db9d527dc529d3f8bb0e290d426436e410c5b504b25d2f73d910cfffed2957"),
    # EPIC 32.P2 raised both together: ``same_line_location_association``
    # joined the catalogue, so the policy version that identifies it moved
    # to 1.1. That is this test working, not this test being edited around.
    "fact": ("1.1", "1b83d6695b9edef6c95fcc4520f5efae80890a355313709c721416a0ff2ed214"),
    "semantic": ("1.0", "d0d0be3a4037b54cde7dd45489532f71c40131d8b0fd5d4c8477320e77eaa326"),
}


def _imported(module_path: str, name: str):
    return getattr(__import__(module_path, fromlist=[name]), name)


# --- 1-3. Every artifact has an identity, keyed on its upstream ---------


def test_every_persisted_artifact_has_an_identity_column() -> None:
    for stage in CHAIN:
        table = _imported(*stage["record"]).__table__

        assert "artifact_identity" in table.c, stage["kind"]
        assert "upstream_identity" in table.c, stage["kind"]


def test_every_reuse_port_looks_an_artifact_up_by_identity() -> None:
    for stage in CHAIN:
        port = _imported(*stage["port"])
        parameters = inspect.signature(port.find_by_identity).parameters

        assert tuple(parameters)[1:] == (
            "document_id",
            "artifact_identity",
        ), stage["kind"]


def test_every_service_decides_reuse_on_identity() -> None:
    """
    The reuse decision is a single identity comparison. A service still
    matching on copied upstream version fields would be the model this
    replaced.
    """

    for stage in CHAIN:
        source = inspect.getsource(_imported(*stage["service"]))

        assert "find_by_identity(" in source, stage["kind"]
        assert "find_for_source(" not in source, stage["kind"]
        assert "find_for_representation(" not in source, stage["kind"]
        assert "find_for_content(" not in source, stage["kind"]


def test_the_database_enforces_the_same_identity() -> None:
    """
    The lookup decides what may be *reused*; the constraint decides what
    may *exist*. They must encode the same rule, or the constraint would
    forbid the very row a change upstream has to create.
    """

    for stage in CHAIN:
        table = _imported(*stage["record"]).__table__
        unique = {
            tuple(constraint.columns.keys())
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }

        assert ("document_id", "artifact_identity") in unique, stage["kind"]


# --- 4. No layer reconstructs transitive upstream identity --------------


def test_no_stage_names_another_stages_version() -> None:
    """
    The point of the chain. Each identity builder may name only the
    versions its own stage owns; everything above it arrives through the
    upstream identity.

    Scope: this audits the identity **builders**, which is where a
    stage's own derivation identity is defined. It deliberately does not
    forbid a service from naming an upstream stage's components, because
    exactly one is required to - canonical text recomposes the
    representation's identity from the representation's own columns, the
    ``RECONSTRUCT_UPSTREAM`` case in ADR-0032. That is upstream identity
    *reconstruction*, not this stage restating its own.
    """

    foreign = {
        "CANONICAL_PDF": ("segmentation_version", "extraction_policy",
                          "resolution_policy", "fact_policy",
                          "semantic_policy"),
        "CANONICAL_TEXT": ("extraction_policy", "resolution_policy",
                           "fact_policy", "semantic_policy"),
        "EVIDENCE_SET": ("representation_version", "resolution_policy",
                         "fact_policy", "semantic_policy"),
        "ENTITY_SET": ("representation_version", "segmentation_version",
                       "extraction_policy", "fact_policy",
                       "semantic_policy"),
        "FACT_SET": ("representation_version", "segmentation_version",
                     "extraction_policy", "resolution_policy",
                     "semantic_policy"),
        "SEMANTIC_SET": ("representation_version", "segmentation_version",
                         "extraction_policy", "resolution_policy",
                         "fact_policy"),
    }

    for stage in CHAIN:
        module = __import__(
            f"app.domain.{stage['context']}."
            + _identity_module(stage["context"]),
            fromlist=["x"],
        )
        source = inspect.getsource(module)

        for banned in foreign[stage["kind"]]:
            assert banned not in source, f"{stage['kind']}: {banned}"


def _identity_module(context: str) -> str:
    return {
        "canonical_pdf": "canonical_pdf_identity",
        "canonical_text": "canonical_text_identity",
        "engineering_evidence": "evidence_identity",
        "engineering_entities": "entity_identity",
        "engineering_facts": "fact_identity",
        "engineering_semantics": "semantic_identity",
    }[context]


# --- 5-6. Local derivation identity is complete -------------------------


def test_each_stage_declares_every_version_it_owns() -> None:
    """
    The completeness test: every version that can change what a stage
    persists, while its upstream stays fixed, must be in that stage's
    local derivation identity.
    """

    for stage in CHAIN:
        module = __import__(
            f"app.domain.{stage['context']}."
            + _identity_module(stage["context"]),
            fromlist=["x"],
        )
        source = inspect.getsource(module)

        for owned in stage["local"]:
            assert f'"{owned}"' in source, f"{stage['kind']}: {owned}"


def test_the_policy_and_contract_versions_are_independent() -> None:
    """
    Nine versions, nine reasons to change. None is derived from
    another, which is the property this test exists to hold.

    EPIC 32.E2.4 raised none of them - it changed how invalidation
    propagates, not what any rule means. EPIC 32.P2 raised exactly one:
    the fact **policy**, because it added a construction rule. The fact
    **contract** did not move beside it, and that is the point: a fact's
    shape is unchanged, only the body of rules that produces facts grew.
    A milestone that moved both without a shape change would be bumping
    mechanically.
    """

    from app.domain.canonical_pdf.canonical_pdf_policy import (
        CANONICAL_REPRESENTATION_VERSION,
    )
    from app.domain.canonical_text.canonical_text_policy import (
        CANONICAL_SEGMENTATION_VERSION,
    )
    from app.domain.engineering_entities.entity_policy import (
        ENTITY_MODEL_VERSION,
        RESOLUTION_POLICY_VERSION,
    )
    from app.domain.engineering_evidence.evidence_policy import (
        EXTRACTION_POLICY_VERSION,
    )
    from app.domain.engineering_facts.fact_policy import (
        FACT_CONTRACT_VERSION,
        FACT_POLICY_VERSION,
    )
    from app.domain.engineering_semantics.semantic_policy import (
        SEMANTIC_CONTRACT_VERSION,
        SEMANTIC_POLICY_VERSION,
    )

    assert CANONICAL_REPRESENTATION_VERSION == "1.0"
    assert CANONICAL_SEGMENTATION_VERSION == "1.0"
    assert EXTRACTION_POLICY_VERSION == "2.0"
    assert RESOLUTION_POLICY_VERSION == "1.0"
    assert ENTITY_MODEL_VERSION == "1.0"
    assert FACT_POLICY_VERSION == "1.1"
    assert FACT_CONTRACT_VERSION == "1.0"
    assert SEMANTIC_POLICY_VERSION == "1.0"
    assert SEMANTIC_CONTRACT_VERSION == "1.0"


# --- 7. The rule catalogue cannot change silently -----------------------


def test_a_rule_version_change_cannot_hide_behind_its_policy() -> None:
    """
    The seventh identity axis EPIC 32.E2.3 found, governed for **every**
    stage rather than encoded.

    Each catalogue's per-rule ``rule_version`` feeds the row keys its
    stage produces, while the stage's *policy* version is what its
    derivation identity names. The architecture contract is that a
    policy version identifies the complete effective rule catalogue - so
    raising a rule version without raising the policy would change
    persisted output under an unchanged identity.

    The contract is executable rather than remembered: each catalogue is
    fingerprinted and pinned beside its policy version. Changing either
    alone fails here, and the fix is to change both together.
    """

    import hashlib

    from app.domain.engineering_entities.entity_policy import (
        RESOLUTION_POLICY_VERSION,
    )
    from app.domain.engineering_entities.entity_resolution_rules import (
        RESOLUTION_RULES,
    )
    from app.domain.engineering_evidence.evidence_policy import (
        EXTRACTION_POLICY_VERSION,
    )
    from app.domain.engineering_evidence.evidence_rules import (
        EXTRACTION_RULES,
    )
    from app.domain.engineering_facts.fact_construction_rules import (
        CONSTRUCTION_RULES,
    )
    from app.domain.engineering_facts.fact_policy import FACT_POLICY_VERSION
    from app.domain.engineering_semantics.semantic_policy import (
        SEMANTIC_POLICY_VERSION,
    )
    from app.domain.engineering_semantics.semantic_rules import (
        SEMANTIC_RULES,
    )

    catalogues = {
        "extraction": (EXTRACTION_POLICY_VERSION, EXTRACTION_RULES),
        "resolution": (RESOLUTION_POLICY_VERSION, RESOLUTION_RULES),
        "fact": (FACT_POLICY_VERSION, CONSTRUCTION_RULES),
        "semantic": (SEMANTIC_POLICY_VERSION, SEMANTIC_RULES),
    }

    for stage, (policy_version, rules) in catalogues.items():
        fingerprint = hashlib.sha256(
            "|".join(
                f"{rule.rule_id}@{rule.rule_version}" for rule in rules
            ).encode("utf-8")
        ).hexdigest()

        assert (policy_version, fingerprint) == CATALOGUE_PINS[stage], (
            f"The {stage} rule catalogue changed. Raise its policy "
            "version beside it - that is what the stage's derivation "
            "identity names, and without it the change would not "
            f"invalidate anything. Then update the pin: {fingerprint}"
        )


# --- 8-9. Identity is domain-separated and deterministic ----------------


def test_artifact_kinds_are_domain_separated() -> None:
    from app.domain.artifact_identity.artifact_identity_builder import (
        derive_identity,
        source_identity,
    )
    from app.domain.artifact_identity.artifact_identity_models import (
        ArtifactKind,
    )

    root = source_identity(
        document_id=1,
        content_checksum="c" * 64,
        checksum_algorithm="sha256",
    )
    local = (("version", "1.0"),)
    digests = {
        kind: derive_identity(kind, upstream=root, local=local).value
        for kind in ArtifactKind
        if kind is not ArtifactKind.SOURCE
    }

    assert len(set(digests.values())) == len(digests)


def test_identity_is_deterministic_and_unambiguous() -> None:
    from app.domain.artifact_identity.artifact_identity_builder import (
        derive_identity,
        source_identity,
    )
    from app.domain.artifact_identity.artifact_identity_models import (
        ArtifactKind,
    )

    root = source_identity(
        document_id=1,
        content_checksum="c" * 64,
        checksum_algorithm="sha256",
    )

    def digest(local):
        return derive_identity(
            ArtifactKind.EVIDENCE_SET, upstream=root, local=local
        ).value

    # Same preimage, byte-identical result.
    assert digest((("a", "1"),)) == digest((("a", "1"),))

    # Field boundaries cannot be forged by a value containing the
    # separator - a plain join would collide here.
    assert digest((("a", "b;c"), ("d", "e"))) != digest(
        (("a", "b"), ("c;d", "e"))
    )

    # Order is declared, not discovered.
    assert digest((("a", "1"), ("b", "2"))) != digest(
        (("b", "2"), ("a", "1"))
    )


def test_the_identity_builder_reaches_nothing_ambient() -> None:
    """No clock, no randomness, no environment, no I/O: an identity that
    depended on any of them could not be recomputed."""

    from app.domain.artifact_identity import artifact_identity_builder

    source = inspect.getsource(artifact_identity_builder)

    for banned in (
        "datetime", "time", "random", "uuid", "os.", "open(", "Path",
        "environ", "session", "request",
    ):
        assert banned not in source, banned


def test_the_identity_contract_is_versioned_and_independent() -> None:
    """
    The composition scheme is itself a contract. It must never be
    borrowed to invalidate a cache - that is what the derivation
    versions are for.
    """

    from app.domain.artifact_identity import artifact_identity_policy

    assert (
        artifact_identity_policy.ARTIFACT_IDENTITY_CONTRACT_VERSION == "1.0"
    )

    source = inspect.getsource(artifact_identity_policy)

    for engineering in (
        "EXTRACTION_POLICY", "RESOLUTION_POLICY", "FACT_POLICY",
        "SEMANTIC_POLICY", "ENTITY_MODEL",
    ):
        assert engineering not in source


# --- 10-12. Trust boundary, legacy provenance, migrations ---------------


def test_no_caller_can_supply_an_identity() -> None:
    for stage in CHAIN:
        parameters = inspect.signature(
            _imported(*stage["service"])
        ).parameters

        assert "artifact_identity" not in parameters, stage["kind"]
        assert "upstream_identity" not in parameters, stage["kind"]


def test_unknown_legacy_identity_is_never_current_compatible() -> None:
    """
    ``column == None`` renders as ``IS NULL`` and would pair arbitrary
    legacy rows. Every identity lookup compares a real digest, and a
    legacy row carries none.
    """

    for stage in CHAIN:
        table = _imported(*stage["record"]).__table__

        assert table.c["artifact_identity"].nullable is True, stage["kind"]


def test_no_migration_fabricates_an_identity() -> None:
    """
    An identity computed by a migration would be a claim about a
    derivation the migration never saw.
    """

    writes = re.compile(
        r"\b(insert\s+into|update\s+\S+\s+set|delete\s+from)\b",
        re.IGNORECASE,
    )

    for migration in sorted(MIGRATIONS.glob("*.py")):
        tree = ast.parse(migration.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(
                node.value, str
            ):
                assert not writes.search(node.value), (
                    f"{migration.name}: {node.value[:60]}"
                )

            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    assert keyword.arg != "server_default", migration.name


# --- 13. The audit itself ------------------------------------------------


def test_no_persisted_reuse_boundary_is_unaccounted_for() -> None:
    """
    Exactly six persisted deterministic artifacts exist, and ``CHAIN``
    is the declared audit of them.

    Scope, stated honestly: this compares the declared list against the
    domain ports that define ``find_by_identity``. It catches a seventh
    artifact that follows the established pattern, and a declared one
    that disappears. It cannot catch an artifact persisted through some
    entirely different mechanism - that remains a review question, and
    the repository-wide scan that found these six is recorded in the
    EPIC 32.E2.3 audit.
    """

    found = set()

    for path in sorted((APP_ROOT / "domain").rglob("*repository*.py")):
        if "__pycache__" in path.parts:
            continue

        if "def find_by_identity(" in path.read_text(encoding="utf-8"):
            found.add(path.stem)

    declared = {stage["port"][0].rsplit(".", 1)[1] for stage in CHAIN}

    assert found == declared, f"unaccounted: {found ^ declared}"
