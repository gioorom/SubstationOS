"""
Tests for the deterministic evidence extractor (Milestone 28.1).

Pure domain tests over hand-built canonical text: no PDF, no database, no
I/O. They specify what the rule catalogue observes - and, at least as
importantly, what it refuses to observe, because a false designation
becomes an entity somebody has to disprove.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)


def _evidence(*lines: str, **overrides):
    """One page, one block, one span per line."""

    source = representation(
        page(
            1,
            text_block(
                0,
                *[
                    span(index, index, text)
                    for index, text in enumerate(lines)
                ],
            ),
        ),
        **overrides,
    )

    return extract_evidence(segment_canonical_document(source))


def _texts(evidence_set, evidence_type: EvidenceType) -> list[str]:
    return [item.observed_text for item in evidence_set.of_type(evidence_type)]


# --- Designations ----------------------------------------------------------


def test_letter_digit_designations_are_observed() -> None:
    result = _evidence("Trasformatore T1 e motore M1, quadro QMT01")

    assert _texts(result, EvidenceType.DESIGNATION) == ["T1", "M1", "QMT01"]


def test_a_numeric_function_code_designation_is_observed() -> None:
    result = _evidence("Interruttore 52-Q1 chiuso")

    assert _texts(result, EvidenceType.DESIGNATION) == ["52-Q1"]


def test_an_iec_81346_designation_is_observed() -> None:
    result = _evidence("Morsettiera +E01-QA1 in cabina")

    assert _texts(result, EvidenceType.DESIGNATION) == ["+E01-QA1"]


def test_punctuation_around_a_designation_is_trimmed() -> None:
    result = _evidence("Il trasformatore (T1), come da schema.")
    item = result.of_type(EvidenceType.DESIGNATION)[0]

    assert item.observed_text == "T1"
    assert item.designation.normalized == "T1"


def test_a_designation_carries_no_equipment_type() -> None:
    """``QMT01`` looks like a medium-voltage panel to an engineer.
    Reading it that way is exactly the inference this layer refuses."""

    item = _evidence("Quadro QMT01").of_type(EvidenceType.DESIGNATION)[0]

    assert item.designation.normalized == "QMT01"
    assert not hasattr(item.designation, "equipment_type")
    assert not hasattr(item, "entity_id")


# --- Designation false positives -------------------------------------------


def test_plain_words_are_not_designations() -> None:
    result = _evidence("Il trasformatore di potenza principale")

    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_uppercase_words_are_not_designations() -> None:
    """Not every capitalised token is a designation - ``TRASFORMATORE``
    and ``AT`` are words, and treating them as equipment names would fill
    the system with nonsense."""

    result = _evidence("TRASFORMATORE AT MT LINEA SEZIONATORE")

    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_bare_numbers_are_not_designations() -> None:
    result = _evidence("Pagina 145 di 200")

    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_a_unit_symbol_is_not_a_designation() -> None:
    result = _evidence("Tensione in kV e corrente in A")

    assert result.of_type(EvidenceType.DESIGNATION) == ()


def test_a_quantity_is_not_read_as_a_designation() -> None:
    """``20kV`` is a voltage. The quantity rules run first precisely so a
    number-unit compound cannot be mistaken for equipment."""

    result = _evidence("Tensione 20kV nominale")

    assert result.of_type(EvidenceType.DESIGNATION) == ()
    assert _texts(result, EvidenceType.VOLTAGE_VALUE) == ["20kV"]


def test_lowercase_tokens_are_not_designations() -> None:
    result = _evidence("vedere fig1 e nota2 del documento")

    assert result.of_type(EvidenceType.DESIGNATION) == ()


# --- Quantities -------------------------------------------------------------


def test_voltage_is_observed_with_an_exact_value() -> None:
    item = _evidence("Tensione nominale 20 kV").of_type(
        EvidenceType.VOLTAGE_VALUE
    )[0]

    assert item.observed_text == "20 kV"
    assert item.quantity.value == Decimal("20")
    assert item.quantity.unit == "kV"


def test_current_is_observed() -> None:
    item = _evidence("Corrente nominale 1250 A").of_type(
        EvidenceType.CURRENT_VALUE
    )[0]

    assert item.quantity.value == Decimal("1250")
    assert item.quantity.unit == "A"


def test_power_is_observed() -> None:
    item = _evidence("Potenza 630 kVA").of_type(
        EvidenceType.POWER_VALUE
    )[0]

    assert item.quantity.value == Decimal("630")
    assert item.quantity.unit == "kVA"


def test_cable_section_is_observed() -> None:
    item = _evidence("Cavo 240 mm² tripolare").of_type(
        EvidenceType.CABLE_SECTION_VALUE
    )[0]

    assert item.observed_text == "240 mm²"
    assert item.quantity.value == Decimal("240")
    assert item.quantity.unit == "mm²"


def test_a_number_and_unit_in_one_token_are_observed() -> None:
    item = _evidence("Tensione 20kV").of_type(
        EvidenceType.VOLTAGE_VALUE
    )[0]

    assert item.observed_text == "20kV"
    assert item.quantity.value == Decimal("20")
    assert item.provenance.token_count == 1


def test_a_quantity_spans_two_tokens_where_written_apart() -> None:
    item = _evidence("Tensione 20 kV").of_type(
        EvidenceType.VOLTAGE_VALUE
    )[0]

    assert item.provenance.token_count == 2


def test_multiple_quantities_on_one_line_are_all_observed() -> None:
    result = _evidence("20 kV / 400 V, 630 kVA, 1250 A, 240 mm²")

    assert _texts(result, EvidenceType.VOLTAGE_VALUE) == ["20 kV", "400 V"]
    assert _texts(result, EvidenceType.POWER_VALUE) == ["630 kVA"]
    assert _texts(result, EvidenceType.CURRENT_VALUE) == ["1250 A"]
    assert _texts(result, EvidenceType.CABLE_SECTION_VALUE) == ["240 mm²"]


def test_a_decimal_value_is_exact() -> None:
    """``Decimal``, never ``float``: 0.1 is not representable in binary
    floating point, and a rated value that read back as
    20.100000000000001 would be a defect nobody could explain."""

    item = _evidence("Tensione 20,5 kV").of_type(
        EvidenceType.VOLTAGE_VALUE
    )[0]

    assert item.quantity.value == Decimal("20.5")
    assert isinstance(item.quantity.value, Decimal)


def test_a_number_without_a_unit_is_not_a_quantity() -> None:
    """Nothing is inferred from neighbouring words. ``Potenza 630`` is a
    number beside a word, not a power value."""

    result = _evidence("Potenza 630 nominale")

    assert result.of_type(EvidenceType.POWER_VALUE) == ()


def test_an_undeclared_unit_is_not_a_unit() -> None:
    result = _evidence("Peso 1200 kg e lunghezza 5 m")

    assert result.evidence_count == 0


# --- Units --------------------------------------------------------------------


def test_declared_unit_variants_are_accepted() -> None:
    result = _evidence("20 KV, 400 Volt, 630 KVA, 1250 Ampere, 240 mm2")

    assert len(result.of_type(EvidenceType.VOLTAGE_VALUE)) == 2
    assert len(result.of_type(EvidenceType.POWER_VALUE)) == 1
    assert len(result.of_type(EvidenceType.CURRENT_VALUE)) == 1
    assert len(result.of_type(EvidenceType.CABLE_SECTION_VALUE)) == 1


def test_a_variant_is_stored_under_its_canonical_symbol() -> None:
    item = _evidence("Tensione 20 KV").of_type(
        EvidenceType.VOLTAGE_VALUE
    )[0]

    assert item.observed_text == "20 KV"
    assert item.quantity.unit == "kV"


def test_exact_conversions_are_applied_and_others_are_not() -> None:
    """kV to V is exact. mm² has no declared base unit, and inventing one
    would mean inventing a conversion."""

    voltage = _evidence("20 kV").of_type(EvidenceType.VOLTAGE_VALUE)[0]
    section = _evidence("240 mm²").of_type(
        EvidenceType.CABLE_SECTION_VALUE
    )[0]

    assert voltage.quantity.base_value == Decimal("20000")
    assert voltage.quantity.base_unit == "V"
    assert section.quantity.base_value is None
    assert section.quantity.base_unit is None


def test_unit_case_is_never_folded() -> None:
    """``mV``, ``kV`` and ``MV`` are three different quantities. Folding
    case would silently turn a millivolt into a megavolt."""

    result = _evidence("Segnale 400 mV")

    assert result.of_type(EvidenceType.VOLTAGE_VALUE) == ()


# --- Statuses -------------------------------------------------------------------


def test_an_ambiguous_separator_is_marked_and_carries_no_value() -> None:
    """``1.250`` is 1250 in one convention and 1.25 in the other. The
    observation is real; the number is not settled, and a consumer must
    not be able to read a guess as a measurement."""

    item = _evidence("Potenza 1.250 kVA").of_type(
        EvidenceType.POWER_VALUE
    )[0]

    assert item.status is EvidenceStatus.AMBIGUOUS
    assert item.quantity is None
    assert item.observed_text == "1.250 kVA"


def test_an_exact_quantity_is_observed_not_ambiguous() -> None:
    item = _evidence("Potenza 630 kVA").of_type(
        EvidenceType.POWER_VALUE
    )[0]

    assert item.status is EvidenceStatus.OBSERVED


def test_a_malformed_number_is_rejected_as_a_diagnostic() -> None:
    item = _evidence("Potenza 1.234,5 kVA").of_type(
        EvidenceType.POWER_VALUE
    )[0]

    assert item.status is EvidenceStatus.AMBIGUOUS
    assert item.is_persistable is True


def test_rejected_items_are_not_persistable() -> None:
    from app.domain.engineering_evidence.evidence_models import (
        EngineeringEvidence,
        EvidenceProvenance,
        SpanReference,
    )

    item = EngineeringEvidence(
        evidence_key="k",
        evidence_type=EvidenceType.VOLTAGE_VALUE,
        status=EvidenceStatus.REJECTED,
        observed_text="x",
        rule_id="voltage_value",
        rule_version="1.0",
        provenance=EvidenceProvenance(
            page_number=1,
            section_index=0,
            paragraph_index=0,
            block_reading_order=0,
            line_index=0,
            token_start=0,
            token_end=1,
            spans=(SpanReference(0, 0, 1),),
            source_text="x",
        ),
    )

    assert item.is_persistable is False


# --- Nothing is inferred ---------------------------------------------------------


def test_a_quantity_beside_a_designation_creates_no_relationship() -> None:
    """
    Two observations that happen to be adjacent. Adjacency is a fact
    about ink; attribution is a judgement, and there is nowhere in the
    model to record one.
    """

    result = _evidence("Trasformatore T1 630 kVA")
    designation = result.of_type(EvidenceType.DESIGNATION)[0]
    power = result.of_type(EvidenceType.POWER_VALUE)[0]

    assert designation.observed_text == "T1"
    assert power.observed_text == "630 kVA"
    for item in (designation, power):
        assert not hasattr(item, "related_to")
        assert not hasattr(item, "belongs_to")
        assert not hasattr(item, "entity_id")


def test_the_set_carries_no_entities_or_relationships() -> None:
    import dataclasses

    from app.domain.engineering_evidence.evidence_models import (
        EngineeringEvidenceSet,
    )

    names = {
        field.name for field in dataclasses.fields(EngineeringEvidenceSet)
    }

    assert names & {
        "entities",
        "relationships",
        "nodes",
        "edges",
        "equipment",
    } == set()


# --- Determinism -------------------------------------------------------------------


def test_the_same_canonical_text_produces_an_equal_evidence_set() -> None:
    source = representation(
        page(
            1,
            text_block(
                0,
                span(0, 0, "Trasformatore T1 20 kV 630 kVA"),
                span(1, 1, "Cavo 240 mm² interruttore 52-Q1"),
            ),
        )
    )
    segmentation = segment_canonical_document(source)

    assert extract_evidence(segmentation) == extract_evidence(segmentation)


def test_evidence_keys_are_stable_across_runs() -> None:
    first = _evidence("Trasformatore T1 20 kV")
    second = _evidence("Trasformatore T1 20 kV")

    assert [item.evidence_key for item in first.evidence] == [
        item.evidence_key for item in second.evidence
    ]


def test_a_different_canonical_source_produces_a_different_set() -> None:
    first = _evidence("Tensione 20 kV")
    second = _evidence("Tensione 20 kV", content_checksum="d" * 64)

    assert first != second
    assert [item.evidence_key for item in first.evidence] != [
        item.evidence_key for item in second.evidence
    ]


def test_the_set_records_the_catalogue_that_produced_it() -> None:
    result = _evidence("Tensione 20 kV")
    item = result.evidence[0]

    assert result.extraction_policy_version == "1.0"
    assert result.segmentation_version == "1.0"
    assert item.rule_id == "voltage_value"
    assert item.rule_version == "1.0"
