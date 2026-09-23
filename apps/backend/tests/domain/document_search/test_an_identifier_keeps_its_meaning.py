"""
An engineering designation survives being made searchable.

The whole risk this file guards against is a normalization that is
*convenient* - strip the punctuation, lowercase it, be done - and that
in doing so quietly asserts two different pieces of equipment are one.
In IEC 81346 the leading ``-`` marks a product, ``+`` a location and
``=`` a function. ``-Q1`` is not ``Q1``, and no amount of tidying may
make them the same.
"""

from __future__ import annotations

import pytest

from app.domain.document_search.search_normalization import (
    normalize,
    prefixed_variants,
    terms,
    tokenize,
    tokenize_with_spans,
    unprefixed,
)


class TestAnAspectPrefixIsPartOfTheDesignation:
    def test_a_product_aspect_is_not_the_bare_designation(self) -> None:
        assert terms("-Q1") != terms("Q1")

    def test_a_location_aspect_is_not_the_bare_designation(self) -> None:
        assert terms("+189L") != terms("189L")

    def test_a_function_aspect_is_not_the_bare_designation(self) -> None:
        assert terms("=K1") != terms("K1")

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("-Q1", "-q1"),
            ("+189L", "+189l"),
            ("=K1", "=k1"),
            ("Q1", "q1"),
            ("189L", "189l"),
        ],
    )
    def test_the_prefix_is_carried_into_the_term(
        self, written: str, expected: str
    ) -> None:
        assert terms(written) == (expected,)


class TestWhatAnEngineerTypesIsWhatIsSearched:
    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("TR1", ("tr1",)),
            ("Q01", ("q01",)),
            ("M1", ("m1",)),
            ("trasformatore", ("trasformatore",)),
            ("quadro MT", ("quadro", "mt")),
            ("TR1 150 kV", ("tr1", "150", "kv")),
            ("MORSETTIERA E1", ("morsettiera", "e1")),
        ],
    )
    def test_the_brief_cases_are_read_as_written(
        self, written: str, expected: tuple[str, ...]
    ) -> None:
        assert terms(written) == expected

    def test_case_makes_no_difference(self) -> None:
        assert terms("tr1 Kv") == terms("TR1 KV") == ("tr1", "kv")

    def test_accents_make_no_difference(self) -> None:
        assert terms("Però") == terms("Pero") == ("pero",)

    def test_a_repeated_term_is_asked_for_once(self) -> None:
        assert terms("TR1 TR1") == ("tr1",)

    def test_terms_keep_the_order_they_were_typed(self) -> None:
        assert terms("kV 150 TR1") == ("kv", "150", "tr1")


class TestATermMatchesWhole:
    def test_a_shorter_designation_is_not_found_inside_a_longer_one(
        self,
    ) -> None:
        """``TR1`` and ``TR15`` are different transformers."""

        assert " tr1 " not in normalize("TR15")

    def test_a_unit_is_not_found_inside_another_unit(self) -> None:
        """150 kV and 150 kVA are not the same rating."""

        assert " kv " not in normalize("150 kVA")

    def test_a_designation_standing_alone_is_found(self) -> None:
        assert " tr1 " in normalize("Trasformatore TR1 di potenza")


class TestPunctuationThatIsNotADesignation:
    def test_a_slash_separates_two_ratings(self) -> None:
        """``150/20 kV`` is two voltages, and both are searchable."""

        assert terms("150/20 kV") == ("150", "20", "kv")

    def test_a_minus_before_a_number_is_arithmetic_not_an_aspect(
        self,
    ) -> None:
        """
        Every IEC 81346 designation carries a letter class. ``-20`` has
        none, so it is minus twenty - and a cell holding it stays
        findable by its digits.
        """

        assert terms("-20") == ("20",)
        assert terms("temperatura -20 gradi") == (
            "temperatura",
            "20",
            "gradi",
        )

    def test_a_dotted_designation_survives_whole(self) -> None:
        assert terms("-Q1.1") == ("-q1.1",)

    def test_brackets_and_commas_separate(self) -> None:
        assert terms("(TR1), E1; E2") == ("tr1", "e1", "e2")


class TestATermPointsBackAtTheSourceItCameFrom:
    """
    Every term knows the exact slice of the original text it was read
    from. Without that a snippet could not highlight what matched, and a
    spreadsheet hit could not work out which cell it fell in.
    """

    def test_each_span_slices_the_source_text_it_was_read_from(
        self,
    ) -> None:
        text = "Sezionatore -Q1 del trasformatore TR1"

        assert [
            text[span.start : span.end] for span in tokenize_with_spans(text)
        ] == ["Sezionatore", "-Q1", "del", "trasformatore", "TR1"]

    def test_spans_survive_a_character_that_folding_shortens(self) -> None:
        """
        Accent folding changes the length of a string, so offsets have
        to be tracked rather than assumed. ``però`` is four characters
        in the source whatever the folded form costs.
        """

        text = "però TR1"
        spans = tokenize_with_spans(text)

        assert spans[0].term == "pero"
        assert text[spans[0].start : spans[0].end] == "però"
        assert text[spans[1].start : spans[1].end] == "TR1"


class TestANearMissIsReportedNeverSubstituted:
    """
    The system may *tell* an engineer that the project writes ``-Q1``
    when they searched ``Q1``. It may not decide that is what they
    meant.
    """

    def test_a_prefixed_term_offers_its_bare_designation(self) -> None:
        assert unprefixed("-q1") == "q1"

    def test_a_bare_term_has_nothing_to_strip(self) -> None:
        assert unprefixed("q1") is None

    def test_a_lone_prefix_is_not_a_designation(self) -> None:
        assert unprefixed("-") is None

    def test_a_bare_term_offers_every_aspect(self) -> None:
        assert prefixed_variants("q1") == ("-q1", "+q1", "=q1")

    def test_an_already_prefixed_term_offers_no_further_prefix(
        self,
    ) -> None:
        assert prefixed_variants("-q1") == ()


class TestNormalizedTextIsBounded:
    def test_text_is_wrapped_so_a_term_can_be_matched_whole(self) -> None:
        assert normalize("TR1") == " tr1 "

    def test_text_with_no_terms_is_still_a_matchable_string(self) -> None:
        """
        A row of punctuation must not normalize to something a
        containment pattern matches against everything.
        """

        assert normalize("---") == " "
        assert normalize("") == " "


class TestADashThatIsNotAHyphenMinus:
    """
    Unicode has a dozen dashes and none of them decompose to ``-``. A
    PDF produced by a plotter carries U+2212 where the drawing shows a
    hyphen; a spreadsheet autocorrected in Word carries U+2013. Folded
    naively they all disappear, which turns ``-Q1`` into ``Q1`` - the
    exact collapse this module exists to prevent.
    """

    @pytest.mark.parametrize(
        "dash",
        [
            "‐",  # hyphen
            "‑",  # non-breaking hyphen
            "‒",  # figure dash
            "–",  # en dash
            "—",  # em dash
            "―",  # horizontal bar
            "−",  # minus sign
            "－",  # fullwidth hyphen-minus
        ],
    )
    def test_a_designation_keeps_its_aspect_whichever_dash_was_used(
        self, dash: str
    ) -> None:
        assert terms(f"{dash}Q1") == ("-q1",)

    @pytest.mark.parametrize("dash", ["−", "–", "‐"])
    def test_a_unicode_dash_still_does_not_make_the_bare_designation(
        self, dash: str
    ) -> None:
        assert terms(f"{dash}Q1") != terms("Q1")

    def test_a_unicode_dash_before_a_number_is_still_arithmetic(
        self,
    ) -> None:
        assert terms("−20") == ("20",)


class TestASymbolAsciiCannotWrite:
    """
    A visible character with no ASCII form must separate its
    neighbours. Deleting it welds them: ``90°C`` becomes the single
    term ``90c``, which neither ``90`` nor ``C`` can find.
    """

    def test_a_degree_sign_separates_the_value_from_the_unit(
        self,
    ) -> None:
        assert terms("90°C") == ("90", "c")

    def test_an_ordinal_sign_does_not_weld_a_number_to_a_letter(
        self,
    ) -> None:
        assert terms("N°1") == ("n", "1")

    def test_an_ohm_sign_separates_rather_than_welds(self) -> None:
        assert terms("50Ω resistenza") == ("50", "resistenza")

    def test_an_invisible_character_still_joins_a_broken_word(
        self,
    ) -> None:
        """
        A soft hyphen is how a PDF records a word broken across two
        lines. It is not drawn, and removing it restores the word.
        """

        assert terms("trasforma­tore") == ("trasformatore",)

    def test_a_combining_accent_does_not_separate_its_letter(
        self,
    ) -> None:
        assert terms("però") == ("pero",)


class TestADotThatEndsASentence:
    """
    ``-Q1.1`` is one designation. ``TR1.Il`` is a full stop somebody
    forgot to put a space after, and ``TR1`` must still find it.
    """

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("-Q1.1", ("-q1.1",)),
            ("1.5", ("1.5",)),
            ("150.20", ("150.20",)),
            ("TR1.Il quadro", ("tr1", "il", "quadro")),
            ("fig.3", ("fig", "3")),
            ("n.189", ("n", "189")),
        ],
    )
    def test_a_continuation_is_kept_only_after_a_digit(
        self, written: str, expected: tuple[str, ...]
    ) -> None:
        assert terms(written) == expected


class TestASpanCanAlwaysBeShownToTheReader:
    """
    Spans become highlights, so a span must sit under the text it
    matched - never under its neighbour's text.
    """

    def test_spans_never_overlap_even_when_one_character_folds_to_many(
        self,
    ) -> None:
        """
        ``U+2100`` is the single character ``A/C``. It yields two terms,
        and both would otherwise claim the same one character.
        """

        spans = tokenize_with_spans("X℀Y")
        ends = [span.end for span in spans]
        starts = [span.start for span in spans]

        assert all(start >= end for start, end in zip(starts[1:], ends))

    def test_a_term_that_cannot_be_placed_is_still_searchable(
        self,
    ) -> None:
        """
        Declining to *point at* a term must not remove it from what the
        text contains.
        """

        assert tokenize("℀") == ("a", "c")
        assert len(tokenize_with_spans("℀")) == 1

    @pytest.mark.parametrize(
        "text",
        [
            "X℀Y",
            "3½ pollici",
            "№1 trasformatore",
            "™TR1",
            "Sezionatore −Q1 del TR1",
            "café TR1",
        ],
    )
    def test_every_span_slices_inside_the_text_it_came_from(
        self, text: str
    ) -> None:
        for span in tokenize_with_spans(text):
            assert 0 <= span.start < span.end <= len(text)


class TestAHyphenThatJoinsRatherThanQualifies:
    """
    An aspect prefix **starts** a designation. A hyphen sitting between
    two alphanumerics joins them into one name, and reading it as a
    product aspect splits the name and invents a prefix the document
    never wrote.

    Found against a real substation corpus, where it affected nearly
    eight thousand occurrences: drawing numbers, equipment codes and
    the distributor's own name were all shattered, and neither half
    could be searched for.
    """

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            # A terminal block named X-VDC is one block, and both
            # halves must find it.
            ("X-VDC", ("x", "vdc")),
            ("X-VAC", ("x", "vac")),
            # A compound whose first segment is a single letter.
            # The hyphen joins; it is not a product aspect on "mail".
            ("e-mail", ("e", "mail")),
            # A drawing number. An engineer quoting any part of it
            # should arrive at the drawing.
            ("REF-A-X01", ("ref", "a", "x01")),
            ("Roma-Italia", ("roma", "italia")),
        ],
    )
    def test_an_internal_hyphen_separates_instead_of_qualifying(
        self, written: str, expected: tuple[str, ...]
    ) -> None:
        assert terms(written) == expected

    @pytest.mark.parametrize(
        "designation",
        ["-Q1", "+189L", "=K1", "+CELLA", "-TA", "-E1", "-X", "+DQ1910"],
    )
    def test_a_designation_that_starts_with_its_aspect_keeps_it(
        self, designation: str
    ) -> None:
        """The repair must not cost the guarantee it was built around."""

        assert terms(designation) == (designation.lower(),)

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("MORSETTIERA -X +CELLA", ("morsettiera", "-x", "+cella")),
            ("(-Q1)", ("-q1",)),
            ("cavo, -W1", ("cavo", "-w1")),
        ],
    )
    def test_an_aspect_after_a_separator_is_still_an_aspect(
        self, written: str, expected: tuple[str, ...]
    ) -> None:
        assert terms(written) == expected

    def test_a_compound_is_found_by_typing_it_back(self) -> None:
        """
        Whatever the rule, it applies identically to the query and to
        the text, so an engineer who types what they see finds it.
        """

        from app.domain.document_search.search_normalization import (
            containment_pattern,
            normalize,
        )

        stored = normalize("Morsettiera X-VDC +CELLA")

        for query in ("X-VDC", "VDC", "x vdc", "+CELLA"):
            for term in terms(query):
                pattern = containment_pattern(term).strip("%")

                assert pattern in stored, (query, term)


class TestACompoundDesignationKeepsEveryAspect:
    """
    IEC 81346 writes a product inside a location as one token:
    ``+E01-QA1``. This repository already defines that notation -
    ``evidence_patterns.DESIGNATION_IEC_81346_COMPOUND`` - and names
    ``-QA1-XB2`` (a product within a product) as the other real form.

    A first attempt at separating joining hyphens from qualifying ones
    did it by looking only at what preceded the hyphen, which discarded
    the second aspect of every compound: searching ``-QA1`` stopped
    finding a drawing that writes ``+E01-QA1``, while searching ``QA1``
    started finding it - the system asserting an identity the document
    never stated. Both halves are pinned here.
    """

    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("+E01-QA1", ("+e01", "-qa1")),
            ("-QA1-XB2", ("-qa1", "-xb2")),
            ("=K1-Q1", ("=k1", "-q1")),
            ("=G1+H2-K3", ("=g1", "+h2", "-k3")),
            ("+CELLA-Q1", ("+cella", "-q1")),
        ],
    )
    def test_each_aspect_of_a_chain_is_its_own_term(
        self, written: str, expected: tuple[str, ...]
    ) -> None:
        assert terms(written) == expected

    def test_a_compound_is_found_by_its_product_aspect(self) -> None:
        assert "-qa1" in terms("+E01-QA1")

    def test_a_compound_does_not_answer_for_the_bare_designation(
        self,
    ) -> None:
        """
        ``QA1`` and ``-QA1`` remain different designations even when the
        one in the document is written inside a location.
        """

        assert "qa1" not in terms("+E01-QA1")

    def test_a_chain_only_starts_where_a_designation_can_start(
        self,
    ) -> None:
        """
        The hyphen in ``X-VDC`` follows a plain run, so it joins rather
        than qualifies - otherwise every hyphenated name in the corpus
        would sprout an aspect it never had.
        """

        assert terms("X-VDC") == ("x", "vdc")
        assert terms("REF-A-S") == ("ref", "a", "s")

    def test_every_aspect_of_a_chain_points_at_its_own_characters(
        self,
    ) -> None:
        text = "Sezionatore +E01-QA1 chiuso"
        spans = tokenize_with_spans(text)

        assert [
            (span.term, text[span.start : span.end]) for span in spans
        ] == [
            ("sezionatore", "Sezionatore"),
            ("+e01", "+E01"),
            ("-qa1", "-QA1"),
            ("chiuso", "chiuso"),
        ]
