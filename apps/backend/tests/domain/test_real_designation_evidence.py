"""
Real-world designation evidence (EPIC 32.E2).

Every positive case in this file is a **verbatim line from a real
an Italian DSO HV/MV functional diagram**, discovered by EPIC 32.E1 and
transcribed into the reference corpus with its document code, page and
file checksum. Synthetic strings appear only as negative canaries and
boundary probes, never as positive evidence.

The four families are tested separately, because EPIC 32.E2's instruction
was not to solve one by broadening a regex until the others break:

A. dot-qualified product designations - ``-E1.L``
B. bare product designations - ``-E``, ``-TA``
C. location aspects, alphanumeric and word-form - ``+GSH002``, ``+TELAIO``
D. false-positive rejection - ``SF6``

The load-bearing decision this file protects is that a dot-qualified
designation is **atomic**. ``-E1.L`` is one observation of one object. It
does not decompose, and it authorises no relationship to ``-E1``.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_entities.entity_models import EntityType
from app.domain.engineering_entities.entity_resolver import resolve_entities
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_models import EvidenceType
from tests.domain._canonical_text_support import (
    page,
    representation,
    span,
    text_block,
)

# --- Real source lines, verbatim -----------------------------------------
#
# LINEE AT   sha256 835469be… p.5 / p.3
# TR PUG     sha256 22f27637… p.6
REAL_DOT_PRODUCT_LINES = (
    "MORSETTIERA -E.AM +GSH002",
    "MORSETTIERA -E.TAL +GSH002",
    "MORSETTIERA -EV.TVL +GSH002",
    "MORSETTIERA -E.L +GSH002",
    "MORSETTIERA -E1.L +GSH002",
    "MORSETTIERA -E1.SB +GSH002",
)
REAL_DOT_PRODUCT_FORMS = (
    "-E.AM",
    "-E.TAL",
    "-EV.TVL",
    "-E.L",
    "-E1.L",
    "-E1.SB",
)
REAL_BARE_PRODUCT_LINES = (
    "MORSETTIERA -E +GSH001",
    "MORSETTIERA -TA +GSH001",
    "MORSETTIERA -E1 +GSH003",
)
REAL_LOCATION_LINES = (
    "MORSETTIERA Q8 +TELAIO",
    "MORSETTIERA B4 +CELLA TR MT",
    "MORSETTIERA Z +Z",
    "MORSETTIERA A/COM +DQ1910",
)
REAL_SF6_LINES = (
    "IBRIDO AT - BASSA PRESSIONE SF6 (P1 GAS)",
    "IBRIDO AT - BASSA PRESSIONE SF6 (P4 GAS)",
    "TA AT - ALLARMI SF6 TA (63GTAAL)",
    "RIO 3 - ALLARMI SF6 TA",
)


def _evidence(*lines: str):
    source = representation(
        page(
            1,
            text_block(
                0,
                *[span(i, i, text) for i, text in enumerate(lines)],
            ),
        )
    )

    return extract_evidence(segment_canonical_document(source))


def _texts(lines, evidence_type):
    return [
        item.observed_text
        for item in _evidence(*lines).of_type(evidence_type)
    ]


# --- A. Dot-qualified product designations -------------------------------


def test_every_real_dot_qualified_form_is_observed() -> None:
    assert _texts(REAL_DOT_PRODUCT_LINES, EvidenceType.DESIGNATION) == list(
        REAL_DOT_PRODUCT_FORMS
    )


def test_a_dot_qualified_designation_is_one_atomic_observation() -> None:
    """
    The milestone's central freeze.

    ``-E1.L`` is ONE designation. The dot is lexical syntax inside a
    single object's name, and it is not treated as a parent/child mark.

    The reason is the absence of positive evidence, not the presence of
    a disproof: nothing in the available source establishes that the
    leading segment denotes the parent engineering object. The observed
    location divergence (``-E`` at ``+GSH001``, ``-E.AM`` at
    ``+GSH003``) argues against a naive physical-containment reading,
    but it does not by itself prove that no reference-designation
    hierarchy exists - this platform has never established that a
    hierarchy implies co-location.
    """

    result = _evidence("MORSETTIERA -E1.L +GSH002")
    designations = result.of_type(EvidenceType.DESIGNATION)

    assert [item.observed_text for item in designations] == ["-E1.L"]
    assert "-E1" not in [item.observed_text for item in designations]
    assert "L" not in [item.observed_text for item in designations]


def test_a_dot_qualified_designation_creates_no_second_asset() -> None:
    """No prefix synthesis and no suffix synthesis - one observation,
    one asset."""

    entities = resolve_entities(_evidence("MORSETTIERA -E1.L +GSH002"))
    assets = entities.of_type(EntityType.EQUIPMENT_DESIGNATION)

    assert [entity.label for entity in assets] == ["-E1.L"]


def test_the_dot_qualified_span_covers_the_whole_token() -> None:
    """Atomic means the evidence points at all of it - a span covering
    only ``-E1`` would be recording a decomposition by other means."""

    item = _evidence("MORSETTIERA -E1.L +GSH002").of_type(
        EvidenceType.DESIGNATION
    )[0]
    span_reference = item.provenance.spans[0]

    line = "MORSETTIERA -E1.L +GSH002"
    start = line.index("-E1.L")

    assert span_reference.character_start == start
    assert span_reference.character_end == start + len("-E1.L")


# --- B. Bare product designations ----------------------------------------


def test_real_bare_product_designations_are_observed() -> None:
    """``-E``, ``-TA`` and ``-E1`` are real terminal blocks. The first
    two carry no digit, and were invisible before 32.E2."""

    assert _texts(REAL_BARE_PRODUCT_LINES, EvidenceType.DESIGNATION) == [
        "-E",
        "-TA",
        "-E1",
    ]


def test_a_hyphen_before_a_word_is_not_a_designation() -> None:
    """The bounded length is what separates a product aspect from a
    hyphenated title fragment."""

    assert _texts(
        ("TRASFORMATORE AT/MT ROSSO -SCHEMA FUNZIONALE",),
        EvidenceType.DESIGNATION,
    ) == []


# --- C. Location aspects, alphanumeric and word-form ---------------------


def test_real_word_form_locations_are_observed() -> None:
    """``+TELAIO`` and ``+CELLA`` are real locations that the pre-32.E2
    alphanumeric-only pattern could not see."""

    found = _texts(REAL_LOCATION_LINES, EvidenceType.LOCATION_ASPECT)

    assert "+TELAIO" in found
    assert "+CELLA" in found
    assert "+Z" in found
    assert "+DQ1910" in found


def test_a_standalone_location_is_not_also_a_designation() -> None:
    """
    Precedence, and it matters at scale: the real set writes 268
    standalone location aspects. Recording them as equipment would have
    put 268 places into the graph as assets.
    """

    result = _evidence("MORSETTIERA -E1.L +GSH002")

    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.DESIGNATION)
    ] == ["-E1.L"]
    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.LOCATION_ASPECT)
    ] == ["+GSH002"]


def test_a_standalone_location_resolves_to_a_structural_location() -> None:
    entities = resolve_entities(_evidence("MORSETTIERA Q8 +TELAIO"))

    assert [
        entity.label
        for entity in entities.of_type(EntityType.STRUCTURAL_LOCATION)
    ] == ["+TELAIO"]
    assert [
        entity.label
        for entity in entities.of_type(EntityType.EQUIPMENT_DESIGNATION)
    ] == ["Q8"]


def test_a_word_location_is_not_classified() -> None:
    """``+TELAIO`` is Italian for *frame* and ``+CELLA`` for *cubicle*.
    The platform records the designation and assigns no equipment class -
    naming a location is not knowing what kind of place it is."""

    entities = resolve_entities(_evidence("MORSETTIERA B4 +CELLA TR MT"))
    location = entities.of_type(EntityType.STRUCTURAL_LOCATION)[0]

    assert location.label == "+CELLA"
    assert not hasattr(location, "equipment_type")
    assert not hasattr(location, "location_kind")


def test_the_compound_location_form_still_works() -> None:
    """EPIC 32.P1's compound reading is untouched."""

    result = _evidence("Morsettiera +E01-QA1 in cabina")

    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.DESIGNATION)
    ] == ["+E01-QA1"]
    assert [
        item.observed_text
        for item in result.of_type(EvidenceType.LOCATION_ASPECT)
    ] == ["+E01"]


def test_a_telephone_number_is_not_a_location() -> None:
    """``T+390000000`` appears in every real title block. Requiring a
    letter after the ``+`` is what keeps it out."""

    result = _evidence("Roma-Italia T+390000000")

    assert result.of_type(EvidenceType.LOCATION_ASPECT) == ()


# --- D. False-positive rejection -----------------------------------------


def test_sf6_is_a_known_and_measured_false_positive() -> None:
    """
    ``SF6`` is sulphur hexafluoride, and the extractor observes it as a
    designation. This test **pins the defect** rather than hiding it.

    Two suppressions were built during EPIC 32.E2 and both were removed
    on review:

    - a token catalogue would encode "SF6 is never a designation" as
      universal truth, turning a visible false positive into a permanent
      invisible false negative the day a real object is designated
      ``SF6``;
    - a source-context rule (reject after ``ALLARMI``/``PRESSIONE``)
      rests on two words, four lines, two documents and one language,
      and misses ``GAS SF6`` and a bare ``SF6`` cell.

    No grammar can separate the token from ``MI1``, ``MO2`` or ``Q8``.
    The fix belongs upstream, in a governed substance vocabulary, and
    until it exists this stays measured and documented.
    """

    found = _texts(REAL_SF6_LINES, EvidenceType.DESIGNATION)

    assert "SF6" in found


def test_the_designations_beside_sf6_are_observed() -> None:
    """``P1`` and ``P4`` are real pressure-switch designations on the
    same lines, and were never at risk."""

    found = _texts(REAL_SF6_LINES, EvidenceType.DESIGNATION)

    assert "P1" in found
    assert "P4" in found


def test_no_global_token_catalogue_suppresses_a_designation() -> None:
    """
    The correction this micro-fix exists for.

    Token identity alone must never suppress an otherwise valid
    designation. There is no module-level list of forbidden words, and
    ``matches_designation`` decides on **shape** plus the one structural
    exclusion (a standalone location aspect is a place, not equipment).
    """

    from app.domain.engineering_evidence import evidence_rules

    module_lists = [
        name
        for name in dir(evidence_rules)
        if name.isupper()
        and isinstance(getattr(evidence_rules, name), (tuple, frozenset, set))
        and any(
            isinstance(value, str) and value.isalnum()
            for value in getattr(evidence_rules, name)
        )
    ]

    assert module_lists == [], module_lists


def test_an_isolated_sf6_token_is_treated_by_shape_alone() -> None:
    """
    No context, no suppression: ``SF6`` standing alone is observed on the
    same terms as any other letters-then-digits token.

    That is the point of removing the catalogue. The behaviour is
    consistent whatever surrounds the token, so nothing about this
    occurrence depends on a curated word appearing nearby.
    """

    isolated = _texts(("SF6",), EvidenceType.DESIGNATION)
    in_prose = _texts(("BASSA PRESSIONE SF6",), EvidenceType.DESIGNATION)

    assert isolated == ["SF6"]
    assert in_prose == ["SF6"]


def test_designations_shaped_like_sf6_are_unaffected() -> None:
    """``MI1``, ``MO2`` and ``Q8`` are structurally identical to ``SF6``.
    Whatever is ever done about the false positive must not touch
    them."""

    assert _texts(
        ("Circuito MI1 MO2 Q8 B7 P4 A3",), EvidenceType.DESIGNATION
    ) == ["MI1", "MO2", "Q8", "B7", "P4", "A3"]


# --- Boundary and precedence --------------------------------------------


def test_rule_precedence_is_deterministic_for_every_real_shape() -> None:
    """One row per shape the real documents write, and exactly what each
    yields. This is the precedence table, executable."""

    expected = {
        "-E1.L": ("designation", None),
        "-E": ("designation", None),
        "+GSH002": (None, "location_aspect"),
        "+TELAIO": (None, "location_aspect"),
        "+E01-QA1": ("designation", "location_aspect"),
        # A known false positive - see the SF6 tests below.
        "SF6": ("designation", None),
        "T1": ("designation", None),
        "52-Q1": ("designation", None),
    }

    for token, (designation, location) in expected.items():
        result = _evidence(f"Riga {token} fine")
        got_designation = [
            item.observed_text
            for item in result.of_type(EvidenceType.DESIGNATION)
        ]
        got_location = [
            item.observed_text
            for item in result.of_type(EvidenceType.LOCATION_ASPECT)
        ]

        assert got_designation == ([token] if designation else []), token
        assert got_location == (
            [token if token != "+E01-QA1" else "+E01"] if location else []
        ), token


def test_malformed_forms_are_not_observed() -> None:
    for token in ("-", "-.L", "+", "+1", "--E1", "-E1.L.X"):
        result = _evidence(f"Riga {token} fine")

        assert result.of_type(EvidenceType.DESIGNATION) == (), token
        assert result.of_type(EvidenceType.LOCATION_ASPECT) == (), token


def test_a_trailing_sentence_dot_is_trimmed_not_treated_as_a_qualifier(
) -> None:
    """
    ``-E1.`` at the end of a sentence is ``-E1`` followed by a full stop,
    and the boundary-trimming policy that has always removed ``(T1),``
    removes it here too.

    Worth pinning because the dot now *also* carries meaning inside a
    designation: the trimmer removes it only from the **ends**, so
    ``-E1.L`` keeps its qualifier while ``-E1.`` does not grow one.
    """

    result = _evidence("Morsettiera -E1. Fine")
    designations = result.of_type(EvidenceType.DESIGNATION)

    assert [item.observed_text for item in designations] == ["-E1"]

    span_reference = designations[0].provenance.spans[0]

    assert (
        span_reference.character_end - span_reference.character_start
    ) == len("-E1")


def test_extraction_is_deterministic() -> None:
    first = _evidence(*REAL_DOT_PRODUCT_LINES)
    second = _evidence(*REAL_DOT_PRODUCT_LINES)

    assert [item.evidence_key for item in first.evidence] == [
        item.evidence_key for item in second.evidence
    ]
