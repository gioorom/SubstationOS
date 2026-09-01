"""
The identity contract of the deterministic derivation chain
(EPIC 32.E2.4).

Everything here versions *how an identity is composed*, never what any
engineering rule means. It is deliberately independent of the extraction,
resolution, fact and semantic policies: those version bodies of
engineering rules, this versions a serialization.
"""

from __future__ import annotations

# The canonicalisation and hashing scheme itself. Raised only when the
# way an identity is composed changes - a field added to a preimage, an
# encoding altered, a hash replaced.
#
# Raising it re-identifies every artifact in the repository, so it is a
# migration event and not a routine edit. It must never be raised to
# invalidate a cache: that is what the derivation versions are for, and
# borrowing this one to do it would make every historical identity
# unexplainable at once.
ARTIFACT_IDENTITY_CONTRACT_VERSION = "1.0"

# The namespace every preimage opens with. Two artifacts of different
# kinds can never collide even if their remaining material is identical,
# because the kind is inside the hash rather than beside it.
ARTIFACT_IDENTITY_NAMESPACE = "substationos.artifact_identity"
