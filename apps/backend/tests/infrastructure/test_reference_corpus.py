"""
Tests for the reference corpus and its loader (Milestone 28.2).

Two things are checked here, and the second matters more than the first:

1. the loader reads and validates a corpus correctly;
2. **the shipped reference corpus actually describes reality** - its
   annotations are consistent with the documents they annotate, and the
   baseline it establishes against the current rules is recorded.

The corpus is version-controlled domain data, not a fixture. Nothing in
this file writes one: expectations that could be edited beside the
assertion would let anybody make the extractor look good by moving the
goalposts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_models import (
    EvidenceStatus,
    EvidenceType,
)
from app.domain.engineering_evidence.evidence_rules import RULES_BY_ID
from app.domain.evidence_evaluation.evaluation_matcher import (
    evaluate_document,
)
from app.infrastructure.evidence_evaluation.yaml_reference_corpus_repository import (  # noqa: E501
    CORPUS_ROOT,
    InvalidReferenceCorpusError,
    YamlReferenceCorpusRepository,
)

REFERENCE_CORPUS = "substation_reference"


@pytest.fixture()
def repository() -> YamlReferenceCorpusRepository:
    return YamlReferenceCorpusRepository()


# --- Loading -------------------------------------------------------------------


def test_the_reference_corpus_is_in_the_repository(
    repository: YamlReferenceCorpusRepository,
) -> None:
    assert REFERENCE_CORPUS in repository.list_corpora()
    assert (CORPUS_ROOT / f"{REFERENCE_CORPUS}.yaml").is_file()


def test_the_corpus_declares_its_versions(
    repository: YamlReferenceCorpusRepository,
) -> None:
    corpus = repository.load(REFERENCE_CORPUS)

    assert corpus.corpus_version == "1.0"
    assert corpus.annotated_against_policy_version == "1.0"
    assert corpus.annotated_rule_versions


def test_an_unknown_corpus_loads_as_none(
    repository: YamlReferenceCorpusRepository,
) -> None:
    assert repository.load("no_such_corpus") is None


def test_a_corpus_naming_a_different_id_is_refused(tmp_path: Path) -> None:
    """A file must be named by its corpus id, or two ids would refer to
    one corpus."""

    (tmp_path / "alpha.yaml").write_text(
        "corpus_id: beta\ncorpus_version: '1.0'\n"
        "annotated_against_policy_version: '1.0'\n",
        encoding="utf-8",
    )

    with pytest.raises(InvalidReferenceCorpusError):
        YamlReferenceCorpusRepository(tmp_path).load("alpha")


def test_a_corpus_missing_a_required_field_is_refused(
    tmp_path: Path,
) -> None:
    """A partially-read definition of "correct" is worse than none: it
    would quietly redefine what every rule is measured against."""

    (tmp_path / "alpha.yaml").write_text(
        "corpus_id: alpha\ncorpus_version: '1.0'\n", encoding="utf-8"
    )

    with pytest.raises(InvalidReferenceCorpusError):
        YamlReferenceCorpusRepository(tmp_path).load("alpha")


def test_an_annotation_citing_a_line_the_document_lacks_is_refused(
    tmp_path: Path,
) -> None:
    (tmp_path / "alpha.yaml").write_text(
        """
corpus_id: alpha
corpus_version: '1.0'
annotated_against_policy_version: '1.0'
documents:
  - document_ref: doc
    title: doc
    lines:
      - "Tensione 20 kV"
    expected:
      - evidence_type: voltage_value
        observed_text: "20 kV"
        status: observed
        rule_id: voltage_value
        rule_version: '1.0'
        provenance:
          line_index: 7
          token_start: 1
          token_end: 3
""",
        encoding="utf-8",
    )

    with pytest.raises(InvalidReferenceCorpusError):
        YamlReferenceCorpusRepository(tmp_path).load("alpha")


# --- The corpus is internally consistent ------------------------------------------


def test_every_annotation_cites_a_declared_rule(
    repository: YamlReferenceCorpusRepository,
) -> None:
    corpus = repository.load(REFERENCE_CORPUS)

    for document in corpus.documents:
        for expectation in document.expected:
            rule = RULES_BY_ID.get(expectation.rule_id)

            assert rule is not None
            assert rule.evidence_type is expectation.evidence_type


def test_every_annotation_points_at_the_text_it_claims(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """
    The check that makes the corpus trustworthy.

    An annotation's character range must actually contain its observed
    text in its own document - otherwise the corpus would be asserting
    something about characters it never read, and every metric derived
    from it would be meaningless.
    """

    corpus = repository.load(REFERENCE_CORPUS)

    for document in corpus.documents:
        for expectation in document.expected:
            recovered = " ".join(
                document.lines[span.span_reading_order][
                    span.character_start : span.character_end
                ]
                for span in expectation.provenance.spans
            )

            assert recovered == expectation.observed_text


def test_a_document_expecting_nothing_is_a_meaningful_annotation(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """"This prose contains nothing these rules should observe" is how
    false positives are caught."""

    corpus = repository.load(REFERENCE_CORPUS)
    prose = corpus.document("descriptive_prose")

    assert prose is not None
    assert prose.expected == ()


def test_the_corpus_covers_every_supported_evidence_type(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """A rule with no annotation is a rule nothing measures."""

    corpus = repository.load(REFERENCE_CORPUS)
    annotated = {
        expectation.evidence_type
        for document in corpus.documents
        for expectation in document.expected
    }

    assert annotated == set(EvidenceType)


def test_the_corpus_covers_the_ambiguous_status(
    repository: YamlReferenceCorpusRepository,
) -> None:
    corpus = repository.load(REFERENCE_CORPUS)
    statuses = {
        expectation.status
        for document in corpus.documents
        for expectation in document.expected
    }

    assert EvidenceStatus.AMBIGUOUS in statuses
    assert EvidenceStatus.OBSERVED in statuses


# --- Materialisation --------------------------------------------------------------


def test_a_reference_document_materialises_through_the_real_segmenter(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """A corpus that hand-built its own tokens would keep passing on the
    day segmentation changed."""

    corpus = repository.load(REFERENCE_CORPUS)
    document = corpus.document("bay_data_sheet")

    canonical_text = repository.materialize(
        document, document_id=0, content_checksum="reference"
    )

    assert canonical_text.section_count == 1
    assert canonical_text.token_count > 0
    assert len(canonical_text.sections[0].paragraphs[0].lines) == len(
        document.lines
    )


def test_materialisation_is_deterministic(
    repository: YamlReferenceCorpusRepository,
) -> None:
    corpus = repository.load(REFERENCE_CORPUS)
    document = corpus.document("bay_data_sheet")

    first = repository.materialize(
        document, document_id=0, content_checksum="reference"
    )
    second = repository.materialize(
        document, document_id=0, content_checksum="reference"
    )

    assert first == second


# --- The measured baseline ----------------------------------------------------------


def test_the_reference_corpus_records_the_current_measured_baseline(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """
    The baseline this milestone measured, pinned so a rule change that
    moves it has to move this number deliberately.

    18 of 19 annotations are matched exactly - text, value, status and
    full provenance. The single miss is ``TR-1`` in
    ``designation_variants``, a **known and deliberately annotated
    recall gap**: the designation patterns do not recognise
    letters-hyphen-digits, and an engineer reading that document would
    call it a designation. It is in the corpus so the gap is measured
    rather than forgotten, and so the milestone that closes it can show
    recall rising.

    EPIC 32.P1 moved this from 17/18 by annotating the ``+E01`` location
    aspect inside ``+E01-QA1`` on ``bay_data_sheet``. The new rule is
    measured on the same terms as every other: exact text, exact status,
    and a character range covering the four characters it read - not the
    whole token it was found in.
    """

    corpus = repository.load(REFERENCE_CORPUS)
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for document in corpus.documents:
        canonical_text = repository.materialize(
            document, document_id=0, content_checksum="reference"
        )
        evaluation = evaluate_document(
            document, extract_evidence(canonical_text).evidence
        )
        metrics = evaluation.metrics
        true_positives += metrics.true_positives
        false_positives += metrics.false_positives
        false_negatives += metrics.false_negatives

    assert (true_positives, false_positives, false_negatives) == (18, 0, 1)


def test_the_known_recall_gap_is_the_only_miss(
    repository: YamlReferenceCorpusRepository,
) -> None:
    """Named explicitly, so that if a *different* item starts failing the
    test says which."""

    corpus = repository.load(REFERENCE_CORPUS)
    missed: list[str] = []

    for document in corpus.documents:
        canonical_text = repository.materialize(
            document, document_id=0, content_checksum="reference"
        )
        evaluation = evaluate_document(
            document, extract_evidence(canonical_text).evidence
        )
        missed.extend(
            result.observed_text
            for result in evaluation.results
            if not result.is_correct
        )

    assert missed == ["TR-1"]
