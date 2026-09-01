"""
The deterministic artifact identity primitive (EPIC 32.E2.4).

Everything downstream of this module trusts one property: the same
computation yields the same digest, and a different computation yields a
different one. These tests hold that property directly, so a failure
here explains a failure anywhere in the chain.
"""

from __future__ import annotations

import pytest

from app.domain.artifact_identity.artifact_identity_builder import (
    derive_identity,
    source_identity,
)
from app.domain.artifact_identity.artifact_identity_exceptions import (
    InvalidArtifactIdentityError,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
)

CHECKSUM = "c" * 64


def _root() -> ArtifactIdentity:
    return source_identity(
        document_id=1,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    )


def _derived(kind=ArtifactKind.EVIDENCE_SET, upstream=None, **local):
    return derive_identity(
        kind,
        upstream=upstream or _root(),
        local=tuple(local.items()) or (("version", "1.0"),),
    )


# --- Determinism --------------------------------------------------------


def test_the_same_computation_yields_the_same_identity() -> None:
    assert _derived(version="1.0").value == _derived(version="1.0").value


def test_the_identity_is_a_sha256_digest() -> None:
    identity = _derived()

    assert len(identity.value) == 64
    assert set(identity.value) <= set("0123456789abcdef")
    assert identity.contract_version == ARTIFACT_IDENTITY_CONTRACT_VERSION


def test_field_order_is_declared_not_discovered() -> None:
    """
    The caller states the order and it is used as given. Sorting, or
    accepting a mapping and iterating it, would make the digest depend on
    how the caller happened to build its arguments.
    """

    root = _root()
    first = derive_identity(
        ArtifactKind.FACT_SET,
        upstream=root,
        local=(("a", "1"), ("b", "2")),
    )
    second = derive_identity(
        ArtifactKind.FACT_SET,
        upstream=root,
        local=(("b", "2"), ("a", "1")),
    )

    assert first.value != second.value


def test_no_value_can_forge_a_field_boundary() -> None:
    """
    Components are length-prefixed. A plain ``"|".join`` would let
    ``("a|b", "c")`` and ``("a", "b|c")`` hash alike - and an identity
    that two different computations share is not an identity.
    """

    root = _root()
    first = derive_identity(
        ArtifactKind.FACT_SET,
        upstream=root,
        local=(("a", "b;c"), ("d", "e")),
    )
    second = derive_identity(
        ArtifactKind.FACT_SET,
        upstream=root,
        local=(("a", "b"), ("c;d", "e")),
    )

    assert first.value != second.value


# --- What changes the identity ------------------------------------------


def test_a_different_upstream_is_a_different_identity() -> None:
    other = source_identity(
        document_id=1,
        content_checksum="d" * 64,
        checksum_algorithm="sha256",
    )

    assert _derived().value != _derived(upstream=other).value


def test_a_different_local_version_is_a_different_identity() -> None:
    assert _derived(version="1.0").value != _derived(version="2.0").value


def test_every_artifact_kind_is_domain_separated() -> None:
    """Identical material of different kinds must never collide - the
    kind is inside the hash, not beside it."""

    root = _root()
    digests = {
        kind: derive_identity(
            kind, upstream=root, local=(("version", "1.0"),)
        ).value
        for kind in ArtifactKind
        if kind is not ArtifactKind.SOURCE
    }

    assert len(set(digests.values())) == len(digests)


def test_the_source_identity_depends_on_no_derivation_version() -> None:
    """The root is not derived. A downstream contract reaching into it
    would re-identify every artifact whenever any stage's rules changed."""

    assert _root().value == source_identity(
        document_id=1,
        content_checksum=CHECKSUM,
        checksum_algorithm="sha256",
    ).value


def test_the_checksum_algorithm_is_part_of_the_source_identity() -> None:
    """The same hex string means different bytes under a different
    algorithm."""

    assert (
        _root().value
        != source_identity(
            document_id=1,
            content_checksum=CHECKSUM,
            checksum_algorithm="sha512",
        ).value
    )


# --- What is refused ----------------------------------------------------


def test_a_derived_artifact_without_an_upstream_is_refused() -> None:
    with pytest.raises(InvalidArtifactIdentityError):
        derive_identity(
            ArtifactKind.ENTITY_SET,
            upstream=None,
            local=(("version", "1.0"),),
        )


def test_a_source_artifact_given_an_upstream_is_refused() -> None:
    with pytest.raises(InvalidArtifactIdentityError):
        derive_identity(
            ArtifactKind.SOURCE,
            upstream=_root(),
            local=(("version", "1.0"),),
        )


def test_an_artifact_declaring_no_derivation_identity_is_refused() -> None:
    """A stage that declared none could never be invalidated when its own
    rules changed."""

    with pytest.raises(InvalidArtifactIdentityError):
        derive_identity(
            ArtifactKind.FACT_SET, upstream=_root(), local=()
        )


def test_an_empty_derivation_component_is_refused() -> None:
    """An unknown version is not a version."""

    with pytest.raises(InvalidArtifactIdentityError):
        derive_identity(
            ArtifactKind.FACT_SET,
            upstream=_root(),
            local=(("version", ""),),
        )


def test_an_unbound_source_is_refused() -> None:
    with pytest.raises(InvalidArtifactIdentityError):
        source_identity(
            document_id=0,
            content_checksum=CHECKSUM,
            checksum_algorithm="sha256",
        )


def test_a_malformed_digest_cannot_become_an_identity() -> None:
    """The value object refuses what the builder would never produce, so
    a corrupt stored digest fails at the boundary rather than
    downstream."""

    for malformed in ("", "not-a-digest", "c" * 63, "C" * 64, "z" * 64):
        with pytest.raises(InvalidArtifactIdentityError):
            ArtifactIdentity(
                value=malformed,
                kind=ArtifactKind.FACT_SET,
                contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
            )


def test_an_identity_must_name_its_contract() -> None:
    with pytest.raises(InvalidArtifactIdentityError):
        ArtifactIdentity(
            value="c" * 64,
            kind=ArtifactKind.FACT_SET,
            contract_version="",
        )


def test_an_unbound_document_sentinel_stays_unbound() -> None:
    """
    The segmenter gives a representation no identity when it is not
    bound to a stored document - which is how the reference corpus
    exercises the rules without fabricating provenance for a document
    that does not exist.

    That behaviour depends on the sentinel staying non-positive. Pinned
    here because changing it to a positive value would silently start
    composing identities for a nonexistent document.
    """

    from app.services.evidence_evaluation_service import (
        REFERENCE_DOCUMENT_ID,
    )

    assert REFERENCE_DOCUMENT_ID <= 0

    with pytest.raises(InvalidArtifactIdentityError):
        source_identity(
            document_id=REFERENCE_DOCUMENT_ID,
            content_checksum=CHECKSUM,
            checksum_algorithm="sha256",
        )
