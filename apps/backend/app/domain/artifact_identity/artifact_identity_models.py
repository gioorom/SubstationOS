"""
The identity of one deterministic derived artifact (EPIC 32.E2.4).

The pipeline is a chain of deterministic derivations, each persisted so
that re-running it is cheap and a historical result stays explainable:

    Source -> Canonical PDF -> Canonical Text -> Evidence -> Entities
           -> Facts -> Semantics

An artifact may be reused only when it is the *same computation* as the
one being asked for. This module says what "the same computation" means,
once, for every stage:

    identity = H(identity contract, kind, upstream identity, local
                 derivation identity)

Two consequences follow, and they are the whole point:

**Invalidation propagates by construction.** A change at any stage
changes that stage's identity, which is the next stage's upstream
identity, which changes its identity, and so on to the end. No layer
needs to know the version constants of the layers above it, and none can
drift out of step with them - which is the failure this replaced.

**Ownership stays local.** Each stage declares only what *it* can change:
its own policy and contract versions. Facts do not know how evidence was
extracted; they know which entity set they consumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.artifact_identity.artifact_identity_exceptions import (
    InvalidArtifactIdentityError,
)


class ArtifactKind(str, Enum):
    """
    The deterministic persisted artifacts of the derivation chain.

    The kind is part of the identity preimage, so two artifacts built
    from identical material but of different kinds cannot collide. It is
    a closed vocabulary: a new deterministic persisted artifact is an
    architecture decision, and adding a member here is where that
    decision becomes visible.
    """

    #: The immutable source content a document's chain begins from. Not
    #: derived by this platform - it is the root the chain hangs on.
    SOURCE = "source"

    CANONICAL_PDF = "canonical_pdf"
    CANONICAL_TEXT = "canonical_text"
    EVIDENCE_SET = "evidence_set"
    ENTITY_SET = "entity_set"
    FACT_SET = "fact_set"
    SEMANTIC_SET = "semantic_set"


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """
    One artifact's deterministic identity.

    ``value`` is a SHA-256 hex digest - compact enough to key a row on,
    and collision-resistant because it is persisted identity rather than
    a cache key that could be recomputed if it went wrong.

    The digest is opaque; the **model** is not. ``kind`` and
    ``contract_version`` travel with it so a stored identity can always
    say what it identifies and under which composition rules, without
    anyone reversing a hash. Persisted artifacts keep their explicit
    provenance columns alongside: identity compresses, it does not
    replace explanation.
    """

    value: str
    kind: ArtifactKind
    contract_version: str

    def __post_init__(self) -> None:
        if len(self.value) != 64 or not all(
            character in "0123456789abcdef" for character in self.value
        ):
            raise InvalidArtifactIdentityError(
                f"An artifact identity must be a SHA-256 hex digest; "
                f"got {self.value!r}."
            )

        if not self.contract_version:
            raise InvalidArtifactIdentityError(
                "An artifact identity must name the identity contract "
                "that composed it."
            )

    def __str__(self) -> str:
        return self.value
