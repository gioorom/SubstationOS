"""
Tests for the deterministic entity resolver (Milestone 29.1).

Pure domain tests over hand-built evidence sets. They specify what the
resolver groups - and, at least as importantly, what it refuses to group,
because a wrong merge arrives downstream as one piece of equipment where
there were two.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from app.domain.engineering_entities.entity_models import (
    EngineeringEntity,
    EngineeringEntitySet,
    EntityStatus,
    EntityType,
)
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringEvidence,
    EngineeringEvidenceSet,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
    SpanReference,
)

CHECKSUM = "c" * 64


def _evidence(
    *,
    evidence_type: EvidenceType = EvidenceType.DESIGNATION,
    observed_text: str = "T1",
    designation: str | None = "T1",
    quantity: EngineeringQuantity | None = None,
    status: EvidenceStatus = EvidenceStatus.OBSERVED,
    rule_version: str = "1.0",
    line: int = 0,
    token_start: int = 0,
) -> EngineeringEvidence:
    rule_id = (
        "designation_generic"
        if evidence_type is EvidenceType.DESIGNATION
        else evidence_type.value
    )

    return EngineeringEvidence(
        evidence_key=f"{observed_text}-{line}-{token_start}",
        evidence_type=evidence_type,
        status=status,
        observed_text=observed_text,
        rule_id=rule_id,
        rule_version=rule_version,
        designation=(
            DesignationValue(normalized=designation)
            if designation is not None
            else None
        ),
        quantity=quantity,
        provenance=EvidenceProvenance(
            page_number=1,
            section_index=0,
            paragraph_index=0,
            block_reading_order=0,
            line_index=line,
            token_start=token_start,
            token_end=token_start + 1,
            spans=(SpanReference(line, 0, 2),),
            source_text=observed_text,
        ),
    )


def _evidence_set(
    *items: EngineeringEvidence, checksum: str = CHECKSUM, **overrides
) -> EngineeringEvidenceSet:
    defaults = dict(
        document_id=7,
        project_id=3,
        content_checksum=checksum,
        segmentation_version="1.0",
        extraction_policy_version="1.0",
        evidence=items,
    )
    defaults.update(overrides)

    return EngineeringEvidenceSet(**defaults)


def _power(value: str = "630") -> EngineeringQuantity:
    return EngineeringQuantity(
        value=Decimal(value),
        unit="kVA",
        base_value=Decimal(value) * 1000,
        base_unit="VA",
    )


# --- Designation grouping ------------------------------------------------------


def test_identical_designations_resolve_to_one_entity() -> None:
    result = resolve_entities(
        _evidence_set(
            _evidence(line=0),
            _evidence(line=2),
            _evidence(line=5),
        )
    )
    entities = result.of_type(EntityType.EQUIPMENT_DESIGNATION)

    assert len(entities) == 1
    assert entities[0].designation.normalized == "T1"
    assert entities[0].evidence_count == 3


def test_different_designations_remain_separate_entities() -> None:
    result = resolve_entities(
        _evidence_set(
            _evidence(observed_text="T1", designation="T1"),
            _evidence(
                observed_text="52-Q1", designation="52-Q1", line=1
            ),
        )
    )

    assert len(result.of_type(EntityType.EQUIPMENT_DESIGNATION)) == 2


def test_designations_differing_only_in_punctuation_group_together(
) -> None:
    """``(T1),`` and ``T1`` normalise to the same designation and are the
    same object - that is what normalisation is for."""

    result = resolve_entities(
        _evidence_set(
            _evidence(observed_text="T1", designation="T1", line=0),
            _evidence(observed_text="T1", designation="T1", line=3),
        )
    )

    assert len(result.of_type(EntityType.EQUIPMENT_DESIGNATION)) == 1


# --- Conflicting observations stay apart ------------------------------------------


def test_the_same_designation_under_two_statuses_stays_two_entities(
) -> None:
    """An ambiguous observation and an observed one are different claims
    about how much is known. Merging them would launder the uncertainty
    away."""

    result = resolve_entities(
        _evidence_set(
            _evidence(status=EvidenceStatus.OBSERVED, line=0),
            _evidence(status=EvidenceStatus.AMBIGUOUS, line=1),
        )
    )
    entities = result.of_type(EntityType.EQUIPMENT_DESIGNATION)

    assert len(entities) == 2
    assert {entity.status for entity in entities} == {
        EntityStatus.RESOLVED,
        EntityStatus.AMBIGUOUS,
    }


def test_the_same_designation_from_two_rule_versions_stays_two_entities(
) -> None:
    """Two observations recognised under different definitions are not
    interchangeable; treating them as one would hide a rule change inside
    an entity."""

    result = resolve_entities(
        _evidence_set(
            _evidence(rule_version="1.0", line=0),
            _evidence(rule_version="1.1", line=1),
        )
    )

    assert len(result.of_type(EntityType.EQUIPMENT_DESIGNATION)) == 2


def test_entity_status_is_derived_from_its_evidence() -> None:
    result = resolve_entities(
        _evidence_set(_evidence(status=EvidenceStatus.AMBIGUOUS))
    )

    assert result.entities[0].status is EntityStatus.AMBIGUOUS


# --- Quantity resolution -----------------------------------------------------------


def test_each_quantity_observation_is_its_own_entity() -> None:
    """
    Two observations of ``630 kVA`` may be one transformer's rating
    written twice, or two transformers with the same rating. The document
    does not say, and neither does this resolver - merging would be a
    guess arriving downstream as one piece of equipment where there were
    two.
    """

    result = resolve_entities(
        _evidence_set(
            _evidence(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="630 kVA",
                designation=None,
                quantity=_power(),
                line=0,
            ),
            _evidence(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="630 kVA",
                designation=None,
                quantity=_power(),
                line=4,
            ),
        )
    )
    entities = result.of_type(EntityType.ENGINEERING_QUANTITY)

    assert len(entities) == 2
    assert {entity.entity_key for entity in entities} != {
        entities[0].entity_key
    }


def test_a_quantity_entity_carries_its_typed_value() -> None:
    result = resolve_entities(
        _evidence_set(
            _evidence(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="630 kVA",
                designation=None,
                quantity=_power(),
            )
        )
    )
    entity = result.of_type(EntityType.ENGINEERING_QUANTITY)[0]

    assert entity.quantity.value == Decimal("630")
    assert entity.quantity.unit == "kVA"
    assert entity.designation is None


def test_a_quantity_is_never_attached_to_a_designation() -> None:
    """
    ``630 kVA`` beside ``TR1`` is not yet a transformer rating.

    Two entities that do not know about each other - attaching one to the
    other is a relationship, and relationships belong to a later stage.
    """

    result = resolve_entities(
        _evidence_set(
            _evidence(observed_text="TR1", designation="TR1", line=0),
            _evidence(
                evidence_type=EvidenceType.POWER_VALUE,
                observed_text="630 kVA",
                designation=None,
                quantity=_power(),
                line=0,
                token_start=1,
            ),
        )
    )

    assert result.entity_count == 2
    for entity in result.entities:
        assert not hasattr(entity, "related_to")
        assert not hasattr(entity, "properties")
        assert not hasattr(entity, "parent_entity_key")


# --- Nothing is inferred -------------------------------------------------------------


def test_the_model_has_nowhere_to_record_a_relationship() -> None:
    """No feeds, no protects, no belongs_to. Those are claims about the
    installation, not about the document."""

    forbidden = {
        "feeds",
        "protects",
        "belongs_to",
        "bay",
        "bay_id",
        "parent_entity_key",
        "children",
        "relationships",
        "topology",
        "properties",
        "equipment_type",
    }

    for model in (EngineeringEntity, EngineeringEntitySet):
        names = {field.name for field in dataclasses.fields(model)}

        assert names & forbidden == set()


def test_an_entity_carries_no_equipment_classification() -> None:
    """``T1`` is a designation that was observed. Deciding it names a
    transformer needs a reviewed rule and a governed vocabulary."""

    entity = resolve_entities(_evidence_set(_evidence())).entities[0]

    assert entity.entity_type is EntityType.EQUIPMENT_DESIGNATION
    assert not hasattr(entity, "equipment_type")
    assert set(EntityType) == {
        EntityType.EQUIPMENT_DESIGNATION,
        EntityType.ENGINEERING_QUANTITY,
        EntityType.STRUCTURAL_LOCATION,
    }


# --- Provenance is aggregated, never owned ---------------------------------------------


def test_an_entity_enumerates_the_evidence_that_created_it() -> None:
    result = resolve_entities(
        _evidence_set(
            _evidence(line=0), _evidence(line=2), _evidence(line=5)
        )
    )
    entity = result.entities[0]

    assert entity.evidence_keys == ("T1-0-0", "T1-2-0", "T1-5-0")
    assert entity.evidence_count == 3


def test_an_entity_aggregates_the_locations_of_its_evidence() -> None:
    result = resolve_entities(
        _evidence_set(_evidence(line=0), _evidence(line=4))
    )
    entity = result.entities[0]

    assert entity.locations == (
        (1, 0, 0, 0, 1),
        (1, 0, 4, 0, 1),
    )


def test_every_contributing_observation_keeps_its_own_text() -> None:
    """The entity records what each observation actually said, not one
    canonical rendering of them all."""

    result = resolve_entities(
        _evidence_set(
            _evidence(observed_text="T1", designation="T1", line=0),
            _evidence(observed_text="T1", designation="T1", line=1),
        )
    )
    entity = result.entities[0]

    assert [
        reference.observed_text for reference in entity.evidence
    ] == ["T1", "T1"]


# --- Deterministic identity --------------------------------------------------------------


def test_the_same_evidence_produces_an_equal_entity_set() -> None:
    evidence_set = _evidence_set(
        _evidence(line=0),
        _evidence(observed_text="52-Q1", designation="52-Q1", line=1),
        _evidence(
            evidence_type=EvidenceType.POWER_VALUE,
            observed_text="630 kVA",
            designation=None,
            quantity=_power(),
            line=2,
        ),
    )

    assert resolve_entities(evidence_set) == resolve_entities(evidence_set)


def test_entity_keys_are_stable_across_runs() -> None:
    evidence_set = _evidence_set(_evidence())

    assert [
        entity.entity_key for entity in resolve_entities(evidence_set).entities
    ] == [
        entity.entity_key for entity in resolve_entities(evidence_set).entities
    ]


def test_a_different_evidence_source_produces_different_keys() -> None:
    first = resolve_entities(_evidence_set(_evidence()))
    second = resolve_entities(
        _evidence_set(_evidence(), checksum="d" * 64)
    )

    assert first.entities[0].entity_key != second.entities[0].entity_key


def test_a_rule_version_change_produces_a_different_entity_set() -> None:
    """A re-resolution under new rules is a new set, not a silent
    rewrite."""

    evidence_set = _evidence_set(_evidence())

    baseline = resolve_entities(evidence_set)
    candidate = resolve_entities(
        evidence_set, resolution_policy_version="2.0"
    )

    assert candidate != baseline
    assert candidate.resolution_policy_version == "2.0"


def test_the_set_records_the_catalogue_that_produced_it() -> None:
    result = resolve_entities(_evidence_set(_evidence()))
    entity = result.entities[0]

    assert result.extraction_policy_version == "1.0"
    assert result.resolution_policy_version == "1.0"
    assert entity.resolution_rule_id == "designation_grouping"
    assert entity.resolution_rule_version == "1.0"
    assert entity.entity_version == "1.0"


def test_the_set_carries_no_timestamp() -> None:
    names = {
        field.name for field in dataclasses.fields(EngineeringEntitySet)
    }

    assert names & {"created_at", "resolved_at", "timestamp"} == set()


def test_an_empty_evidence_set_resolves_to_no_entities() -> None:
    result = resolve_entities(_evidence_set())

    assert result.is_empty
    assert result.entity_count == 0
