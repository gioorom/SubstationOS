"""Typed failures of the artifact identity contract."""

from __future__ import annotations


class ArtifactIdentityError(Exception):
    """Base for every failure of the identity contract."""


class InvalidArtifactIdentityError(ArtifactIdentityError):
    """
    An identity was asked for over material that cannot identify
    anything - an empty component, a missing upstream, a kind that does
    not match the artifact being identified.

    Raised rather than returning a degraded identity: an identity nobody
    can reproduce is worse than a visible refusal, because it would be
    persisted and trusted.
    """
