"""
Domain tests for document-retrieval aggregation and ranking (Milestone
23B.1) - the pure, deterministic core of "which documents mention X?".

Pure and fast: no I/O, no database, no AI provider.
"""

from __future__ import annotations

from app.domain.engineering_index.document_relevance_policy import (
    WEIGHT_ADDITIONAL_MENTION,
    WEIGHT_EXACT_IDENTIFIER_MATCH,
    WEIGHT_MULTI_TERM_SUPPORT,
    WEIGHT_PARTIAL_IDENTIFIER_MATCH,
)
from app.domain.engineering_index.document_retrieval_factory import (
    DocumentRetrievalRequestFactory,
)
from app.domain.engineering_index.document_retrieval_models import (
    DocumentRelevanceCategory,
)
from app.domain.engineering_index.document_retrieval_ranking import (
    build_document_retrieval_result,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from tests.domain._document_retrieval_support import NOW, entry, metadata


def _request(identifiers=("T2",), limit=20, project_id=1):
    return DocumentRetrievalRequestFactory.create(
        project_id=project_id, identifiers=identifiers, limit=limit
    )


def _build(request, entries, document_metadata=()):
    return build_document_retrieval_result(
        request=request,
        entries=tuple(entries),
        document_metadata=tuple(document_metadata),
        retrieved_at=NOW,
    )


# --- The happy path -------------------------------------------------------


def test_a_matching_document_is_returned_with_its_repository_metadata() -> None:
    result = _build(_request(), [entry()], [metadata()])

    assert len(result.references) == 1
    reference = result.references[0]
    assert reference.document_id == 10
    assert reference.title == "montante-T2-schema-funzionale.pdf"
    assert reference.document_format == "pdf"
    assert reference.document_category == "functional_schematic"
    assert reference.revision == "02"
    assert reference.metadata_available is True


def test_page_references_come_from_page_locators() -> None:
    result = _build(
        _request(),
        [
            entry(entry_id=1, page=3),
            entry(entry_id=2, page=7),
            entry(entry_id=3, page=3),
        ],
        [metadata()],
    )

    assert result.references[0].page_references == (3, 7)


def test_a_non_page_locator_yields_no_fabricated_page() -> None:
    """A spreadsheet cell range is a perfectly good locator; inventing a
    page number for it would be a fabrication."""

    result = _build(
        _request(),
        [
            entry(
                locator=IndexEntryLocator(
                    kind=IndexEntryLocatorKind.CELL_RANGE, value="B12:C15"
                )
            )
        ],
        [metadata()],
    )

    reference = result.references[0]
    assert reference.page_references == ()
    assert reference.mentions[0].locator_value == "B12:C15"


def test_the_recorded_mentions_are_exposed_as_evidence() -> None:
    result = _build(
        _request(),
        [
            entry(
                entry_id=4,
                kind=EngineeringIndexEntryKind.PROTECTION,
                identifier="87T",
                label="Differenziale trasformatore",
            )
        ],
        [metadata()],
    )

    mention = result.references[0].mentions[0]
    assert mention.entry_id == 4
    assert mention.kind is EngineeringIndexEntryKind.PROTECTION
    assert mention.identifier == "87T"
    assert mention.label == "Differenziale trasformatore"


# --- Relevance ------------------------------------------------------------


def test_an_exact_identifier_match_scores_the_exact_weight() -> None:
    result = _build(_request(("T2",)), [entry(identifier="T2")], [metadata()])

    relevance = result.references[0].relevance
    assert relevance.total == WEIGHT_EXACT_IDENTIFIER_MATCH
    assert [component.category for component in relevance.components] == [
        DocumentRelevanceCategory.EXACT_IDENTIFIER_MATCH
    ]


def test_a_partial_identifier_match_scores_less_than_an_exact_one() -> None:
    result = _build(
        _request(("T2",)), [entry(identifier="T21")], [metadata()]
    )

    relevance = result.references[0].relevance
    assert relevance.total == WEIGHT_PARTIAL_IDENTIFIER_MATCH
    assert relevance.total < WEIGHT_EXACT_IDENTIFIER_MATCH


def test_additional_mentions_add_a_scaled_component() -> None:
    result = _build(
        _request(("T2",)),
        [entry(entry_id=1, page=1), entry(entry_id=2, page=2)],
        [metadata()],
    )

    relevance = result.references[0].relevance
    assert relevance.total == (
        WEIGHT_EXACT_IDENTIFIER_MATCH + WEIGHT_ADDITIONAL_MENTION
    )
    assert result.references[0].mention_count == 2


def test_matching_several_requested_identifiers_adds_multi_term_support() -> (
    None
):
    result = _build(
        _request(("T2", "87T")),
        [
            entry(entry_id=1, identifier="T2"),
            entry(entry_id=2, identifier="87T"),
        ],
        [metadata()],
    )

    relevance = result.references[0].relevance
    assert relevance.total == (
        2 * WEIGHT_EXACT_IDENTIFIER_MATCH
        + WEIGHT_ADDITIONAL_MENTION
        + WEIGHT_MULTI_TERM_SUPPORT
    )
    assert result.references[0].matched_terms == ("87T", "T2")


def test_the_relevance_total_is_always_the_sum_of_its_components() -> None:
    result = _build(
        _request(("T2", "87T")),
        [
            entry(entry_id=1, identifier="T2"),
            entry(entry_id=2, identifier="87T"),
            entry(entry_id=3, identifier="T21"),
        ],
        [metadata()],
    )

    relevance = result.references[0].relevance
    assert relevance.total == sum(
        component.weight for component in relevance.components
    )


# --- Ordering, deduplication and limits -----------------------------------


def test_documents_are_ordered_by_descending_relevance() -> None:
    result = _build(
        _request(("T2",)),
        [
            entry(entry_id=1, document_id=10, identifier="T21"),
            entry(entry_id=2, document_id=11, identifier="T2"),
        ],
        [metadata(document_id=10), metadata(document_id=11)],
    )

    assert [
        reference.document_id for reference in result.references
    ] == [11, 10]


def test_equally_relevant_documents_are_ordered_deterministically() -> None:
    result = _build(
        _request(("T2",)),
        [
            entry(entry_id=1, document_id=12, identifier="T2"),
            entry(entry_id=2, document_id=11, identifier="T2"),
        ],
        [metadata(document_id=11), metadata(document_id=12)],
    )

    assert [
        reference.document_id for reference in result.references
    ] == [11, 12]


def test_the_same_entry_matched_by_several_terms_is_counted_once() -> None:
    """A search for "T2" and one for "T" both return the same recorded
    mention. Counting it twice would inflate relevance for no new
    evidence."""

    duplicated = entry(entry_id=1, identifier="T2")
    result = _build(
        _request(("T2", "T")), [duplicated, duplicated], [metadata()]
    )

    assert result.references[0].mention_count == 1
    assert result.statistics.matched_entry_count == 1


def test_the_limit_is_applied_after_ranking_and_reported() -> None:
    entries = [
        entry(entry_id=index, document_id=index, identifier="T2")
        for index in range(1, 6)
    ]
    result = _build(_request(("T2",), limit=2), entries)

    assert result.statistics.matched_document_count == 5
    assert result.statistics.returned_document_count == 2
    assert result.statistics.applied_limit == 2
    assert result.metadata.truncated_by_limit is True


def test_an_untruncated_result_does_not_claim_truncation() -> None:
    result = _build(_request(("T2",), limit=20), [entry()], [metadata()])

    assert result.metadata.truncated_by_limit is False


def test_entries_from_another_project_are_ignored() -> None:
    result = _build(
        _request(project_id=1),
        [entry(project_id=2, document_id=99)],
    )

    assert result.references == ()


# --- No matches -----------------------------------------------------------


def test_no_matching_document_yields_an_empty_result_with_a_warning() -> None:
    result = _build(_request(("99Z",)), [])

    assert result.references == ()
    assert result.statistics.matched_document_count == 0
    assert result.metadata.warnings != ()


# --- Missing document metadata --------------------------------------------


def test_a_document_whose_metadata_is_unavailable_is_still_reported() -> None:
    """An Engineering Index entry is a freely rebuildable lead that may
    outlive its document row (ADR-0002). The mention is real, so it is
    reported - with its metadata honestly absent."""

    result = _build(_request(), [entry()], document_metadata=())

    reference = result.references[0]
    assert reference.metadata_available is False
    assert reference.title is None
    assert reference.revision is None
    assert result.metadata.documents_missing_metadata == (10,)


def test_metadata_is_matched_to_the_right_document() -> None:
    result = _build(
        _request(("T2",)),
        [
            entry(entry_id=1, document_id=10, identifier="T2"),
            entry(entry_id=2, document_id=11, identifier="T2"),
        ],
        [metadata(document_id=11, title="only-eleven.pdf")],
    )

    by_id = {
        reference.document_id: reference for reference in result.references
    }
    assert by_id[11].title == "only-eleven.pdf"
    assert by_id[10].title is None


# --- Determinism ----------------------------------------------------------


def test_the_same_input_always_produces_the_same_result() -> None:
    request = _request(("T2", "87T"))
    entries = [
        entry(entry_id=1, document_id=10, identifier="T2", page=4),
        entry(entry_id=2, document_id=11, identifier="87T", page=9),
        entry(entry_id=3, document_id=10, identifier="87T", page=5),
    ]
    document_metadata = [metadata(document_id=10), metadata(document_id=11)]

    first = _build(request, entries, document_metadata)
    second = _build(request, list(reversed(entries)), document_metadata)

    assert first == second


def test_the_policy_versions_that_produced_the_result_are_recorded() -> None:
    result = _build(_request(), [entry()], [metadata()])

    assert result.metadata.document_retrieval_version
    assert result.metadata.relevance_policy_version
