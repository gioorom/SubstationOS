"""
The entity resolution rule catalogue (Milestone 29.1) - the **one**
authoritative statement of when two observations are treated as one
thing.

Each rule declares:

| Property | Answers |
|---|---|
| grouping key | what makes two observations the same object |
| separation | what keeps two observations apart |
| entity type | what kind of hypothesis it produces |
| versioning | which rule, at which version, produced an entity |

**Rule versions are part of every stored entity.** When a rule changes,
the entities it produced before keep saying which rule produced them, and
a re-resolution under the new version creates a new entity set rather
than rewriting the old one.

## No fuzzy matching, anywhere

No edit distance, no embeddings, no similarity score, no model. Two
observations are the same object because a **stated rule** says so, or
they are not. A resolver that grouped `TR1` with `TR-1` because they look
alike would be guessing, and the guess would arrive downstream as an
equipment record nobody could question.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_entities.entity_models import EntityType


@dataclass(frozen=True, slots=True)
class ResolutionRule:
    """
    One rule, identified and versioned.

    ``rule_id`` is a stable contract: once published it appears in stored
    entities, so renaming it is a migration rather than an edit.
    """

    rule_id: str
    rule_version: str
    entity_type: EntityType
    description: str


DESIGNATION_GROUPING_RULE = ResolutionRule(
    rule_id="designation_grouping",
    rule_version="1.0",
    entity_type=EntityType.EQUIPMENT_DESIGNATION,
    description=(
        "Designation observations sharing a normalised designation, an "
        "evidence status, and the extraction rule that produced them "
        "resolve to one entity **within one document**. Says nothing "
        "about what equipment the designation names."
    ),
)

QUANTITY_IDENTITY_RULE = ResolutionRule(
    rule_id="quantity_identity",
    rule_version="1.0",
    entity_type=EntityType.ENGINEERING_QUANTITY,
    description=(
        "Each quantity observation resolves to its own entity. Nothing "
        "in this catalogue proves that two quantity observations "
        "describe one quantity, so nothing merges them."
    ),
)

RESOLUTION_RULES: tuple[ResolutionRule, ...] = (
    DESIGNATION_GROUPING_RULE,
    QUANTITY_IDENTITY_RULE,
)

RULES_BY_ID: dict[str, ResolutionRule] = {
    rule.rule_id: rule for rule in RESOLUTION_RULES
}


def designation_grouping_key(
    normalized_designation: str, status: str, extraction_rule_version: str
) -> tuple[str, str, str]:
    """
    What makes two designation observations the same object.

    Three parts, and each earns its place:

    - **the normalised designation** - the thing being named;
    - **the evidence status** - an ``AMBIGUOUS`` observation and an
      ``OBSERVED`` one are different claims about how much is known, and
      merging them would launder the uncertainty away;
    - **the extraction rule version** - two observations produced by
      different versions of the recognising rule were recognised under
      different definitions, and treating them as interchangeable would
      hide a rule change inside an entity.

    Deliberately **not** part of the key: the observed text. ``(T1),``
    and ``T1`` normalise to the same designation and are the same object;
    that is what normalisation is for.

    Also deliberately not part of the key: the *document*. Grouping is
    per document because the caller resolves one document's evidence at a
    time - two documents writing ``T1`` may mean two different
    transformers, and deciding otherwise is cross-document resolution,
    which this milestone does not perform.
    """

    return (normalized_designation, status, extraction_rule_version)
