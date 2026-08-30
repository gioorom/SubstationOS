"""
How one reasoning conclusion is identified.

**Derived from the question, the rule and the governed inputs - and from
nothing else.** The same governed knowledge, asked the same question
under the same rule version, produces the same identity on any machine,
in any process, forever.

Deliberately excluded, each for a reason:

| Excluded | Why |
|---|---|
| wall-clock time | two evaluations of unchanged knowledge are the same conclusion; a timestamp would make them look like two |
| random UUID | an identity nobody can recompute is an identity nobody can compare |
| execution duration | operational, not engineering |
| display labels | ``TR1`` is a label; two different transformers share it. Identity built on a label is identity that eventually merges them |
| the outcome itself | the identity says *which question over which knowledge*; the outcome is the answer, and folding it in would mean a rule change that flipped the answer produced an unrelated id |

## Why the inputs are part of it

A conclusion about `TR1` from two governed statements is not the same
conclusion as one about `TR1` from three. Including the contributing
governed identities - sorted, so ordering cannot perturb the hash -
makes "the knowledge changed" visible as a new identity rather than as a
silently different answer under the old one.
"""

from __future__ import annotations

import hashlib

REASONING_IDENTITY_NAMESPACE = "substationos/engineering-reasoning/result/v1"

#: A separator that cannot occur in a designation, a rule id or a
#: governed identity, so two different compositions cannot hash alike.
_SEPARATOR = "\x1f"


def reasoning_result_id(
    *,
    rule_id: str,
    rule_version: str,
    question: str,
    project_id: int | None,
    contributing_identities: tuple[str, ...],
) -> str:
    """
    The identity of one reasoning conclusion.

    ``contributing_identities`` are the governed identities the rule
    read. They are **sorted here** rather than trusted in the caller's
    order: two evaluations that considered the same governed knowledge
    are the same evaluation, whatever order retrieval happened to return
    it in.
    """

    material = (
        REASONING_IDENTITY_NAMESPACE,
        rule_id,
        rule_version,
        question,
        "" if project_id is None else str(project_id),
        *sorted(contributing_identities),
    )

    return hashlib.sha256(
        _SEPARATOR.join(material).encode("utf-8")
    ).hexdigest()
