"""
The versioned policy of deterministic engineering reasoning.

Two versions, and the split is deliberate.

| Version | Owns | Bump it when |
|---|---|---|
| `rule_version` on each rule | what **one** rule concludes | that rule's comparison, required inputs or outcome mapping changes |
| `REASONING_POLICY_VERSION` (here) | what is true of **every** rule | contributor ordering, identity composition, or the shared outcome/diagnostic vocabulary changes |

A single global version would make a change to one rule look like a
change to all of them; per-rule versions alone would leave a change to
the shared evaluation policy invisible. Both are recorded on every
`ReasoningResult`.

There is deliberately **no reasoning "engine version"** beyond this: the
Engineering Engine already versions its workflows and its plan policy,
and a third number describing the same execution would be a version
field nobody could attribute a behaviour change to.
"""

from __future__ import annotations

#: Shared evaluation policy: contributor ordering, result identity
#: composition, and the outcome and diagnostic vocabularies.
REASONING_POLICY_VERSION = "1.0"
