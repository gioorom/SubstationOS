"""
The filesystem/YAML adapter behind ``ReferenceCorpusRepository``
(Milestone 28.2).

Corpora are **domain data in the repository**, alongside the ontology
YAML, and this adapter reads them. It is the only module that knows they
are files; the evaluation domain deals in ``ReferenceCorpus`` values.

## Materialising a reference document

A reference document declares its text as lines. Turning that into
canonical text goes through the **real** pipeline from text onwards -
``canonical_pdf_factory`` builds the representation, and Milestone 27.1's
segmenter segments it - so an evaluation exercises the same input the
extractor sees in production.

A corpus that hand-built its own tokens would be measuring the extractor
against a world that does not exist: the moment segmentation changed, the
evaluation would keep passing while the live path broke.

This is also why the adapter, not the domain, does it. The evaluation
domain imports neither the segmenter nor the canonical PDF value objects;
it receives canonical text already built. No PDF library is involved
anywhere - a representation assembled from known text is not a decoded
document.

## Validation on load

A corpus that does not satisfy the model is refused rather than partially
returned. A partially-read definition of "correct" is worse than none: it
would quietly redefine what every extraction rule is measured against.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from app.domain.canonical_pdf import canonical_pdf_factory
from app.domain.canonical_pdf.canonical_pdf_models import (
    BoundingBox,
    CanonicalBlockKind,
    CanonicalPdfSpan,
    TextStyle,
)
from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.canonical_text.canonical_text_segmenter import (
    segment_canonical_document,
)
from app.domain.engineering_evidence.evidence_models import (
    DesignationValue,
    EngineeringQuantity,
    EvidenceProvenance,
    EvidenceStatus,
    EvidenceType,
    SpanReference,
)
from app.domain.evidence_evaluation.corpus_models import (
    ExpectedObservation,
    ReferenceCorpus,
    ReferenceDocument,
)
from app.domain.evidence_evaluation.corpus_repository import (
    ReferenceCorpusRepository,
)

# Corpora live beside the domain that defines them, exactly as the
# ontology's own YAML does.
CORPUS_ROOT = (
    Path(__file__).resolve().parents[2]
    / "domain"
    / "evidence_evaluation"
    / "corpora"
)

# A reference document is laid out one page, one block, one span per
# line. Geometry is irrelevant to evidence extraction - no rule reads a
# coordinate - so a fixed placeholder box keeps the corpus about text.
_BOX = BoundingBox(0.0, 0.0, 10.0, 10.0)
_STYLE = TextStyle(
    font_family="Helvetica", font_size=11.0, bold=False, italic=False
)


class InvalidReferenceCorpusError(Exception):
    """A corpus file exists and does not describe a usable corpus."""

    def __init__(self, corpus_id: str, detail: str) -> None:
        super().__init__(f"Corpus '{corpus_id}' is invalid: {detail}")
        self.corpus_id = corpus_id
        self.detail = detail


class YamlReferenceCorpusRepository(ReferenceCorpusRepository):
    """Reads versioned corpora from YAML files."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or CORPUS_ROOT

    def list_corpora(self) -> tuple[str, ...]:
        if not self._root.is_dir():
            return ()

        return tuple(
            sorted(path.stem for path in self._root.glob("*.yaml"))
        )

    def load(self, corpus_id: str) -> ReferenceCorpus | None:
        path = self._root / f"{corpus_id}.yaml"

        if not path.is_file():
            return None

        # Safe loading only - a corpus is untrusted input like any other
        # file, and nothing here executes what it reads.
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))

        if not isinstance(raw, dict):
            raise InvalidReferenceCorpusError(
                corpus_id, "the file does not contain a mapping"
            )

        return _corpus(corpus_id, raw)

    def materialize(
        self,
        document: ReferenceDocument,
        *,
        document_id: int,
        content_checksum: str,
    ) -> CanonicalTextDocument:
        return build_canonical_text(
            document,
            document_id=document_id,
            content_checksum=content_checksum,
        )


def build_canonical_text(
    document: ReferenceDocument,
    *,
    document_id: int,
    content_checksum: str,
) -> CanonicalTextDocument:
    """
    Turn a reference document's lines into canonical text, through the
    real segmenter.

    ``document_id`` and ``content_checksum`` are supplied by the caller:
    a reference document is not a row in the documents table, and giving
    it a synthetic identity here keeps evaluation from needing one.
    """

    spans = tuple(
        CanonicalPdfSpan(
            reading_order=index,
            line_index=index,
            text=text,
            bounding_box=_BOX,
            style=_STYLE,
        )
        for index, text in enumerate(document.lines)
    )
    representation = canonical_pdf_factory.build_document(
        document_id=document_id,
        content_checksum=content_checksum,
        checksum_algorithm="sha256",
        representation_version="1.0",
        parser_name="reference_corpus",
        parser_version="1.0",
        pages=(
            canonical_pdf_factory.build_page(
                page_number=1,
                width=595.0,
                height=842.0,
                blocks=(
                    canonical_pdf_factory.build_block(
                        reading_order=0,
                        kind=CanonicalBlockKind.TEXT,
                        bounding_box=_BOX,
                        spans=spans,
                    ),
                ),
            ),
        ),
    )

    return segment_canonical_document(representation)


# --- Parsing ----------------------------------------------------------


def _corpus(corpus_id: str, raw: dict) -> ReferenceCorpus:
    declared = _require(raw, "corpus_id", corpus_id)

    if declared != corpus_id:
        raise InvalidReferenceCorpusError(
            corpus_id,
            f"the file declares corpus_id '{declared}'; a corpus must be "
            "named by its file, or two ids would refer to one corpus",
        )

    return ReferenceCorpus(
        corpus_id=corpus_id,
        corpus_version=str(_require(raw, "corpus_version", corpus_id)),
        description=str(raw.get("description", "")).strip(),
        annotated_against_policy_version=str(
            _require(raw, "annotated_against_policy_version", corpus_id)
        ),
        annotated_rule_versions=tuple(
            (rule_id, str(version))
            for rule_id, version in sorted(
                (raw.get("annotated_rule_versions") or {}).items()
            )
        ),
        documents=tuple(
            _document(corpus_id, entry)
            for entry in raw.get("documents") or ()
        ),
    )


def _document(corpus_id: str, raw: dict) -> ReferenceDocument:
    lines = tuple(str(line) for line in raw.get("lines") or ())

    if not lines:
        raise InvalidReferenceCorpusError(
            corpus_id,
            f"document '{raw.get('document_ref')}' declares no lines",
        )

    return ReferenceDocument(
        document_ref=str(_require(raw, "document_ref", corpus_id)),
        title=str(raw.get("title", "")),
        lines=lines,
        expected=tuple(
            _expected(corpus_id, entry, lines)
            for entry in raw.get("expected") or ()
        ),
    )


def _expected(
    corpus_id: str, raw: dict, lines: tuple[str, ...]
) -> ExpectedObservation:
    provenance = _provenance(corpus_id, raw.get("provenance"), lines)
    quantity = raw.get("quantity")
    designation = raw.get("designation")

    return ExpectedObservation(
        evidence_type=_enum(
            EvidenceType, _require(raw, "evidence_type", corpus_id), corpus_id
        ),
        observed_text=str(_require(raw, "observed_text", corpus_id)),
        status=_enum(
            EvidenceStatus, _require(raw, "status", corpus_id), corpus_id
        ),
        rule_id=str(_require(raw, "rule_id", corpus_id)),
        rule_version=str(_require(raw, "rule_version", corpus_id)),
        quantity=_quantity(corpus_id, quantity),
        designation=(
            DesignationValue(normalized=str(designation))
            if designation is not None
            else None
        ),
        provenance=provenance,
    )


def _quantity(
    corpus_id: str, raw: dict | None
) -> EngineeringQuantity | None:
    if raw is None:
        return None

    return EngineeringQuantity(
        value=_decimal(corpus_id, raw.get("value")),
        unit=str(_require(raw, "unit", corpus_id)),
        base_value=(
            _decimal(corpus_id, raw["base_value"])
            if raw.get("base_value") is not None
            else None
        ),
        base_unit=(
            str(raw["base_unit"])
            if raw.get("base_unit") is not None
            else None
        ),
    )


def _provenance(
    corpus_id: str, raw: dict | None, lines: tuple[str, ...]
) -> EvidenceProvenance:
    if raw is None:
        raise InvalidReferenceCorpusError(
            corpus_id, "an expected observation declares no provenance"
        )

    line_index = int(_require(raw, "line_index", corpus_id))

    if line_index >= len(lines):
        raise InvalidReferenceCorpusError(
            corpus_id,
            f"an expectation cites line {line_index} of a document with "
            f"{len(lines)} line(s)",
        )

    return EvidenceProvenance(
        page_number=int(raw.get("page_number", 1)),
        section_index=int(raw.get("section_index", 0)),
        paragraph_index=int(raw.get("paragraph_index", 0)),
        block_reading_order=int(raw.get("block_reading_order", 0)),
        line_index=line_index,
        token_start=int(_require(raw, "token_start", corpus_id)),
        token_end=int(_require(raw, "token_end", corpus_id)),
        spans=tuple(
            SpanReference(
                span_reading_order=int(span["span_reading_order"]),
                character_start=int(span["character_start"]),
                character_end=int(span["character_end"]),
            )
            for span in raw.get("spans") or ()
        ),
        source_text=str(raw.get("source_text", "")),
    )


def _require(raw: dict, key: str, corpus_id: str):
    if key not in raw or raw[key] is None:
        raise InvalidReferenceCorpusError(
            corpus_id, f"a required field '{key}' is missing"
        )

    return raw[key]


def _enum(enum_type, value, corpus_id: str):
    try:
        return enum_type(str(value))
    except ValueError as error:
        raise InvalidReferenceCorpusError(
            corpus_id, f"'{value}' is not a valid {enum_type.__name__}"
        ) from error


def _decimal(corpus_id: str, value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as error:
        raise InvalidReferenceCorpusError(
            corpus_id, f"'{value}' is not an exact decimal"
        ) from error
