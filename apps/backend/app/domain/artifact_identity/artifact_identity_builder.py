"""
How a deterministic artifact identity is composed (EPIC 32.E2.4).

Pure, total and free of I/O: an identity is a function of the material
handed to it, so the same inputs produce the same digest on any machine,
in any process, forever. That is what lets a stored identity be compared
rather than merely recomputed.
"""

from __future__ import annotations

import hashlib

from app.domain.artifact_identity.artifact_identity_exceptions import (
    InvalidArtifactIdentityError,
)
from app.domain.artifact_identity.artifact_identity_models import (
    ArtifactIdentity,
    ArtifactKind,
)
from app.domain.artifact_identity.artifact_identity_policy import (
    ARTIFACT_IDENTITY_CONTRACT_VERSION,
    ARTIFACT_IDENTITY_NAMESPACE,
)

#: One preimage component, length-prefixed.
#:
#: ``name`` and ``value`` are both written as ``<length>:<text>``, so no
#: value can impersonate a field boundary however many separators it
#: contains. A plain ``"|".join`` would let ``("a|b", "c")`` and
#: ``("a", "b|c")`` hash alike; here they cannot.
_FIELD = "{name_length}:{name}={value_length}:{value}"
_SEPARATOR = ";"


def _component(name: str, value: str) -> str:
    if not name:
        raise InvalidArtifactIdentityError(
            "An identity component must be named."
        )

    return _FIELD.format(
        name_length=len(name),
        name=name,
        value_length=len(value),
        value=value,
    )


def _canonical(
    kind: ArtifactKind,
    upstream: ArtifactIdentity | None,
    local: tuple[tuple[str, str], ...],
) -> str:
    """
    The exact bytes that are hashed.

    Field order is **declared, never discovered**: the caller passes an
    ordered tuple and it is used as given. Sorting, or accepting a
    mapping and iterating it, would make the digest depend on how the
    caller happened to build its arguments.
    """

    components = [
        _component("contract", ARTIFACT_IDENTITY_CONTRACT_VERSION),
        _component("kind", kind.value),
        _component(
            "upstream", "" if upstream is None else upstream.value
        ),
    ]

    for name, value in local:
        components.append(_component(f"local.{name}", value))

    return _SEPARATOR.join([ARTIFACT_IDENTITY_NAMESPACE, *components])


def derive_identity(
    kind: ArtifactKind,
    *,
    upstream: ArtifactIdentity | None,
    local: tuple[tuple[str, str], ...],
) -> ArtifactIdentity:
    """
    The identity of one derived artifact.

    ``upstream`` is the identity of the artifact this one was derived
    *from* - ``None`` only for :attr:`ArtifactKind.SOURCE`, which is the
    root the chain hangs on. ``local`` is the ordered derivation
    identity this stage owns: every version that can change what this
    stage persists while its upstream stays fixed.

    Raises :class:`InvalidArtifactIdentityError` when the material
    cannot identify anything - a derived artifact without an upstream, a
    root artifact given one, or an empty local component. A refusal is
    recoverable; a digest over incomplete material is not, because it
    would be stored and believed.
    """

    if kind is ArtifactKind.SOURCE and upstream is not None:
        raise InvalidArtifactIdentityError(
            "A source artifact is the root of the chain and has no "
            "upstream artifact."
        )

    if kind is not ArtifactKind.SOURCE and upstream is None:
        raise InvalidArtifactIdentityError(
            f"A {kind.value} is derived from an upstream artifact, and "
            "its identity cannot be composed without that artifact's "
            "identity."
        )

    if not local:
        raise InvalidArtifactIdentityError(
            f"A {kind.value} must declare the derivation identity it "
            "owns; an artifact that declares none could not be "
            "invalidated when its own rules change."
        )

    for name, value in local:
        if not value:
            raise InvalidArtifactIdentityError(
                f"The derivation component '{name}' of a {kind.value} "
                "is empty. An unknown version is not a version."
            )

    digest = hashlib.sha256(
        _canonical(kind, upstream, local).encode("utf-8")
    ).hexdigest()

    return ArtifactIdentity(
        value=digest,
        kind=kind,
        contract_version=ARTIFACT_IDENTITY_CONTRACT_VERSION,
    )


def source_identity(
    *, document_id: int, content_checksum: str, checksum_algorithm: str
) -> ArtifactIdentity:
    """
    The root identity of one document's immutable stored content.

    Composed from what the platform observed about the bytes and nothing
    else. It deliberately depends on **no derivation version**: the
    source is not derived, and letting a downstream contract reach into
    the root would make every artifact's identity change whenever any
    stage's rules did.
    """

    if document_id <= 0:
        raise InvalidArtifactIdentityError(
            "A source artifact must name the document it belongs to."
        )

    return derive_identity(
        ArtifactKind.SOURCE,
        upstream=None,
        local=(
            ("document_id", str(document_id)),
            ("content_checksum", content_checksum),
            ("checksum_algorithm", checksum_algorithm),
        ),
    )
