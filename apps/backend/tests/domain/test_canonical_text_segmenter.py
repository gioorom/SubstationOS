"""
Tests for the canonical text segmenter (Milestone 27.1).

Pure domain tests: no PDF, no database, no I/O. They specify the four
mappings the segmenter performs - page to section, block to paragraph,
line to line, whitespace to token - and, just as importantly, the
inferences it refuses to make.
"""

from __future__ import annotations

import dataclasses

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
    CanonicalTextParagraph,
    CanonicalTextSection,
)
from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from tests.domain._canonical_text_support import (
    CHECKSUM,
    image_block,
    page,
    representation,
    simple_representation,
    span,
    text_block,
)


def _tokens(segmentation: CanonicalTextDocument):
    return list(segmentation.tokens())


# --- The hierarchy -------------------------------------------------------


def test_a_single_page_document_segments_into_one_section() -> None:
    segmentation = segment_canonical_document(simple_representation())

    assert segmentation.section_count == 1
    assert segmentation.sections[0].page_number == 1
    assert segmentation.sections[0].section_index == 0


def test_each_page_becomes_exactly_one_section() -> None:
    """A section is a page. Not a chapter, not a heading, not an
    engineering section - the page transition is the only division of
    this size the parser actually observed."""

    segmentation = segment_canonical_document(
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21"))),
            page(2, text_block(0, span(0, 0, "Bay 22"))),
            page(3, text_block(0, span(0, 0, "Bay 23"))),
        )
    )

    assert segmentation.section_count == 3
    assert [section.page_number for section in segmentation.sections] == [
        1,
        2,
        3,
    ]
    assert [section.section_index for section in segmentation.sections] == [
        0,
        1,
        2,
    ]


def test_each_block_becomes_exactly_one_paragraph() -> None:
    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "Rated voltage")),
                text_block(1, span(0, 0, "145 kV")),
            )
        )
    )
    paragraphs = segmentation.sections[0].paragraphs

    assert len(paragraphs) == 2
    assert [p.block_reading_order for p in paragraphs] == [0, 1]
    assert [p.paragraph_index for p in paragraphs] == [0, 1]


def test_spans_sharing_a_line_index_become_one_line() -> None:
    """The parser's own line grouping, carried through Milestone 26.1's
    spans. Re-deriving line membership from coordinates would be
    inference; reading the index the parser gave is an observation."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 0, "Rated voltage"),
                    span(1, 0, " 145 kV"),
                    span(2, 1, "Frequency 50 Hz"),
                ),
            )
        )
    )
    lines = segmentation.sections[0].paragraphs[0].lines

    assert len(lines) == 2
    assert [line.line_index for line in lines] == [0, 1]
    assert len(lines[0].tokens) == 4
    assert len(lines[1].tokens) == 3


def test_tokens_are_whitespace_delimited_runs() -> None:
    segmentation = segment_canonical_document(
        simple_representation("Rated voltage 145 kV")
    )

    assert [token.text for token in _tokens(segmentation)] == [
        "Rated",
        "voltage",
        "145",
        "kV",
    ]


# --- Ordering -------------------------------------------------------------


def test_token_position_counts_across_the_whole_line() -> None:
    """A line built from three spans still numbers its tokens 0..n, so
    ordering survives the span boundaries that produced it."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 0, "Rated"),
                    span(1, 0, " voltage"),
                    span(2, 0, " 145 kV"),
                ),
            )
        )
    )
    line = segmentation.sections[0].paragraphs[0].lines[0]

    assert [token.position for token in line.tokens] == [0, 1, 2, 3]
    assert [token.text for token in line.tokens] == [
        "Rated",
        "voltage",
        "145",
        "kV",
    ]


def test_lines_keep_the_parsers_first_appearance_order() -> None:
    """Not sorted by line index. The parser's ordering is what the
    representation records, and re-ordering here would reintroduce the
    geometric guessing Milestone 26.1 refused."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 3, "printed last, indexed third"),
                    span(1, 1, "printed first, indexed first"),
                ),
            )
        )
    )
    lines = segmentation.sections[0].paragraphs[0].lines

    assert [line.line_index for line in lines] == [3, 1]


def test_document_order_walks_sections_paragraphs_lines_and_tokens(
) -> None:
    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "first")),
                text_block(1, span(0, 0, "second")),
            ),
            page(2, text_block(0, span(0, 0, "third"))),
        )
    )

    assert [token.text for token in _tokens(segmentation)] == [
        "first",
        "second",
        "third",
    ]


# --- Provenance -----------------------------------------------------------


def test_every_token_carries_the_full_chain_back_to_its_span() -> None:
    """document -> page -> block -> span -> characters. An extractor that
    concludes something from a token must be able to point at the exact
    characters it came from."""

    segmentation = segment_canonical_document(
        representation(
            page(1, text_block(0, span(0, 0, "Cover sheet"))),
            page(
                2,
                text_block(0, span(0, 0, "Bay 21")),
                text_block(
                    1, span(0, 0, "Ignored"), span(1, 3, "Rated voltage 145 kV")
                ),
            ),
        )
    )
    token = [
        token for token in segmentation.tokens() if token.text == "145"
    ][0]

    assert token.provenance.page_number == 2
    assert token.provenance.block_reading_order == 1
    assert token.provenance.span_reading_order == 1
    assert token.provenance.line_index == 3


def test_character_offsets_locate_the_token_inside_its_span() -> None:
    """The offsets are the provenance: the substring must be recoverable
    from the representation, not merely equal to something in it."""

    source = "Rated voltage 145 kV"
    representation_ = representation(page(1, text_block(0, span(0, 0, source))))
    segmentation = segment_canonical_document(representation_)

    for token in segmentation.tokens():
        recovered = source[
            token.provenance.character_start : token.provenance.character_end
        ]

        assert recovered == token.text


def test_offsets_are_relative_to_the_span_not_the_line() -> None:
    """A line assembled from two spans: the second span's tokens are
    located inside *that* span, or the chain would point at the wrong
    characters."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(
                    0, span(0, 0, "Rated voltage"), span(1, 0, "145 kV")
                ),
            )
        )
    )
    tokens = _tokens(segmentation)

    assert tokens[2].text == "145"
    assert tokens[2].provenance.span_reading_order == 1
    assert tokens[2].provenance.character_start == 0


def test_provenance_survives_a_multi_page_document() -> None:
    segmentation = segment_canonical_document(
        representation(
            page(1, text_block(0, span(0, 0, "first"))),
            page(2, text_block(0, span(0, 0, "second"))),
        )
    )

    assert [
        token.provenance.page_number for token in _tokens(segmentation)
    ] == [1, 2]


def test_the_segmentation_records_the_representation_it_came_from(
) -> None:
    segmentation = segment_canonical_document(simple_representation())

    assert segmentation.document_id == 7
    assert segmentation.content_checksum == CHECKSUM
    assert segmentation.representation_version == "1.0"
    assert segmentation.segmentation_version == "1.0"


# --- Nothing is inferred ---------------------------------------------------


def test_paragraphs_are_never_merged_across_blocks() -> None:
    """Two blocks stay two paragraphs even when their text would read as
    one sentence. Merging would be a judgement about what the document
    meant."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "The rated voltage of the")),
                text_block(1, span(0, 0, "busbar is 145 kV.")),
            )
        )
    )

    assert len(segmentation.sections[0].paragraphs) == 2


def test_lines_are_never_joined_into_sentences() -> None:
    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(
                    0,
                    span(0, 0, "Rated voltage of the"),
                    span(1, 1, "busbar is 145 kV."),
                ),
            )
        )
    )

    assert len(segmentation.sections[0].paragraphs[0].lines) == 2


def test_a_word_split_across_two_spans_stays_two_tokens() -> None:
    """"MV" in bold followed by "switchgear" is two spans, so it is two
    tokens. Merging them would produce a token that points at no single
    span - and the provenance chain is worth more than the tidier
    word."""

    segmentation = segment_canonical_document(
        representation(
            page(1, text_block(0, span(0, 0, "MV"), span(1, 0, "switchgear")))
        )
    )

    assert [token.text for token in _tokens(segmentation)] == [
        "MV",
        "switchgear",
    ]


def test_the_model_has_nowhere_to_record_a_title_or_a_heading() -> None:
    """No title, no heading, no level, no kind. The moment one appears,
    something upstream has started inferring document structure."""

    forbidden = {
        "title",
        "heading",
        "level",
        "kind",
        "label",
        "caption",
        "is_table",
        "is_list",
        "entity",
        "entities",
    }

    for model in (
        CanonicalTextDocument,
        CanonicalTextSection,
        CanonicalTextParagraph,
    ):
        names = {field.name for field in dataclasses.fields(model)}

        assert names & forbidden == set()


# --- Empty structures are kept ---------------------------------------------


def test_an_empty_page_becomes_an_empty_section() -> None:
    """Dropping it would renumber every section after it and break the
    correspondence between a section and the page an engineer is looking
    at."""

    segmentation = segment_canonical_document(
        representation(
            page(1, text_block(0, span(0, 0, "Bay 21"))),
            page(2),
            page(3, text_block(0, span(0, 0, "Bay 23"))),
        )
    )

    assert segmentation.section_count == 3
    assert segmentation.sections[1].is_empty
    assert segmentation.sections[1].page_number == 2
    assert segmentation.sections[2].page_number == 3


def test_an_image_block_becomes_an_empty_paragraph() -> None:
    """The parser saw something there. A paragraph index that silently
    jumped would stop matching the representation's block ordering."""

    segmentation = segment_canonical_document(
        representation(
            page(
                1,
                text_block(0, span(0, 0, "Site photograph")),
                image_block(1),
            )
        )
    )
    paragraphs = segmentation.sections[0].paragraphs

    assert len(paragraphs) == 2
    assert paragraphs[1].is_empty
    assert paragraphs[1].block_reading_order == 1


def test_a_representation_with_no_pages_segments_to_an_empty_document(
) -> None:
    segmentation = segment_canonical_document(representation())

    assert segmentation.is_empty
    assert segmentation.section_count == 0


def test_a_span_of_only_whitespace_yields_no_tokens() -> None:
    segmentation = segment_canonical_document(
        simple_representation("      ")
    )

    assert segmentation.token_count == 0


# --- Determinism ------------------------------------------------------------


def test_segmenting_the_same_representation_twice_is_equal() -> None:
    source = representation(
        page(
            1,
            text_block(0, span(0, 0, "Rated voltage"), span(1, 1, "145 kV")),
            image_block(1),
        ),
        page(2, text_block(0, span(0, 0, "Frequency 50 Hz"))),
    )

    assert segment_canonical_document(source) == segment_canonical_document(
        source
    )


def test_the_segmentation_carries_no_timestamp() -> None:
    """A timestamp would silently make two runs over the same input
    unequal, and idempotency would become unassertable."""

    field_names = {
        field.name for field in dataclasses.fields(CanonicalTextDocument)
    }

    assert field_names == {
        "document_id",
        "content_checksum",
        "representation_version",
        "segmentation_version",
        "sections",
        "artifact_identity",
        "upstream_identity",
    }


def test_every_level_of_the_segmentation_is_frozen() -> None:
    segmentation = segment_canonical_document(simple_representation())

    for value in (
        segmentation,
        segmentation.sections[0],
        segmentation.sections[0].paragraphs[0],
        segmentation.sections[0].paragraphs[0].lines[0],
        _tokens(segmentation)[0],
    ):
        assert type(value).__dataclass_params__.frozen is True


def test_the_line_text_is_a_reconstruction_not_the_documents_own() -> None:
    """Tokenisation discarded the original spacing. The reconstruction
    joins with single spaces and says so; whoever needs the verbatim line
    reads the representation's spans, which are still authoritative."""

    segmentation = segment_canonical_document(
        simple_representation("Rated    voltage")
    )
    line = segmentation.sections[0].paragraphs[0].lines[0]

    assert line.text == "Rated voltage"
