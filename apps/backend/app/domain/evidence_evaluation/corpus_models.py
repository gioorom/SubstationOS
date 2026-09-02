"""
The Reference Evidence Corpus (EPIC 2, Milestone 28.2).

A corpus is a **version-controlled set of documents whose evidence
somebody has written down by hand**. It is the only thing in this system
that can say whether an extraction rule is any good: the extractor's own
output cannot grade itself.

## What a corpus is made of

```
ReferenceCorpus            id, version, what it was annotated against
  └─ ReferenceDocument     a document's text, plus what should be found in it
       └─ ExpectedObservation   one evidence item a human asserts is there
```

The document text lives in the corpus, so a corpus is reproducible from
the repository alone - no database state, no stored PDF, no network. That
is what lets an evaluation run in CI and mean the same thing next year.

## The same domain model, not a second one

``ExpectedObservation`` is built from the **Engineering Evidence value
objects** - ``EvidenceType``, ``EvidenceStatus``, ``EvidenceProvenance``,
``EngineeringQuantity``, ``DesignationValue``. A parallel annotation model
would be a second definition of what an observation is, and the two would
drift: an annotation format that could express something the evidence
model cannot is an annotation nobody can ever satisfy.

The one field it does **not** carry is ``evidence_key``. That key is a
SHA-256 the extractor computes; asking an annotator to produce one by
hand would be asking them to run the extractor, which is precisely what
the corpus exists to check independently.

## Corpora are immutable

A corpus is data in the repository. Editing one changes what "correct"
means, so it changes the corpus *version* - and evaluations recorded
against the old version stay valid statements about the old definition of
correct. Nothing in this system writes a corpus at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
)


@dataclass(frozen=True, slots=True)
class ExpectedObservation:
    """
    One evidence item a human asserts a document contains.

    ``rule_id``/``rule_version`` record which rule the annotator expected
    to produce it. They are part of the corpus rather than derived,
    because "rule X version 1.0 should find this" is a different claim
    from "something should find this" - and when a rule version changes,
    the corpus states plainly what it was annotated against.
    """

    evidence_type: EvidenceType
    observed_text: str
    status: EvidenceStatus
    provenance: EvidenceProvenance
    rule_id: str
    rule_version: str
    quantity: EngineeringQuantity | None = None
    designation: DesignationValue | None = None

    @property
    def location(self) -> tuple[int, int, int, int, int]:
        """The coarse location, for reporting: page, paragraph, line and
        token range."""

        return (
            self.provenance.page_number,
            self.provenance.paragraph_index,
            self.provenance.line_index,
            self.provenance.token_start,
            self.provenance.token_end,
        )


@dataclass(frozen=True, slots=True)
class ReferenceSource:
    """
    Where a real corpus line came from (EPIC 32.E2, pseudonymised by
    EPIC 33.R1 - see ADR-0033).

    Enough to identify the source **consistently**, and nothing that ties
    the corpus either to one machine or to one client.

    ``document_code`` is a **stable pseudonymous handle** in a
    ``REF-<family>-<sheet>`` scheme, not the code printed on the drawing.
    It resolves to a real document only through a private map held
    outside this repository. The sheet suffix is kept because the
    document *type* - an HV-line sheet index versus a transformer one -
    is engineering signal the corpus makes claims about.

    ``source_ref_digest`` is SHA-256 over that handle. It is **not** a
    checksum of any file: the drawings are external inputs, and a digest
    of bytes no reader can obtain would assert a provenance nobody could
    check. What it does is prove the handle has not drifted, and give two
    entries transcribed from one drawing one identifier - both
    recomputable from this file alone.

    No filesystem path - a corpus that recorded ``C:\\Users\\...``
    would be reproducible on exactly one computer.
    """

    document_code: str
    page_number: int
    source_ref_digest: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReferenceDocument:
    """
    One annotated document.

    ``lines`` is the document's text, one entry per canonical line. The
    corpus loader turns it into canonical text through the **real**
    segmenter, so an evaluation exercises the same input path a live
    document takes - a corpus that hand-built its own tokens would be
    measuring the extractor against a world that does not exist.

    ``expected`` is what a human says should be found. An empty tuple is
    a meaningful annotation: "this document contains nothing these rules
    should observe", which is exactly how false positives are caught.

    ``source`` names the real engineering document a line was copied
    from, when there is one (EPIC 32.E2). A corpus entry whose lines were
    transcribed from a real drawing and one that was written to exercise
    a rule are different kinds of evidence, and a metric that mixed them
    would be measuring the extractor partly against itself.
    """

    document_ref: str
    title: str
    lines: tuple[str, ...]
    expected: tuple[ExpectedObservation, ...] = ()
    source: "ReferenceSource | None" = None

    @property
    def is_real_source(self) -> bool:
        """Whether these lines were transcribed from a real engineering
        document rather than authored for the corpus."""

        return self.source is not None

    @property
    def expected_count(self) -> int:
        return len(self.expected)


@dataclass(frozen=True, slots=True)
class ReferenceCorpus:
    """
    A named, versioned set of annotated documents.

    ``annotated_against_policy_version`` and ``annotated_rule_versions``
    record the state of the rule catalogue when the annotations were
    written. They do not constrain what may be evaluated - evaluating a
    new rule version against an old corpus is the whole point of
    regression detection - but they make the comparison honest: a report
    can say "this corpus was annotated against policy 1.0 and evaluated
    against 1.1".
    """

    corpus_id: str
    corpus_version: str
    description: str
    annotated_against_policy_version: str
    annotated_rule_versions: tuple[tuple[str, str], ...]
    documents: tuple[ReferenceDocument, ...] = ()

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def expected_count(self) -> int:
        return sum(document.expected_count for document in self.documents)

    def document(self, document_ref: str) -> ReferenceDocument | None:
        for document in self.documents:
            if document.document_ref == document_ref:
                return document

        return None
