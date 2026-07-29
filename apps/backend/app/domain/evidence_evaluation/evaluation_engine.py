"""
The evaluation engine (Milestone 28.2) - the pure function that turns a
corpus and its canonical texts into a report.

```
ReferenceCorpus + canonical texts
   -> for each reference document
       -> execute the deterministic extractor
       -> match against the annotations
   -> EvaluationReport
```

Pure and deterministic. Canonical text is handed in already materialised
- building it is the corpus repository's job - so this function performs
no I/O and its determinism is verifiable by comparing two runs for
equality.

**It never modifies engineering evidence.** It runs the extractor over
reference documents that are not rows in the documents table, and returns
a report. Nothing here writes an evidence set, and nothing here reads
one: an evaluation against stored evidence would be measuring what was
stored, not what the current rules produce.
"""

from __future__ import annotations

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)
from app.domain.engineering_evidence.evidence_extractor import (
    extract_evidence,
)
from app.domain.engineering_evidence.evidence_policy import (
    EXTRACTION_POLICY_VERSION,
)
from app.domain.engineering_evidence.evidence_rules import EXTRACTION_RULES
from app.domain.evidence_evaluation.corpus_models import ReferenceCorpus
from app.domain.evidence_evaluation.evaluation_matcher import (
    evaluate_document,
)
from app.domain.evidence_evaluation.evaluation_models import (
    EvaluationReport,
    ProvenanceMatchPolicy,
)
from app.domain.evidence_evaluation.evaluation_policy import (
    DEFAULT_PROVENANCE_POLICY,
)


def run_evaluation(
    corpus: ReferenceCorpus,
    canonical_texts: dict[str, CanonicalTextDocument],
    *,
    provenance_policy: ProvenanceMatchPolicy = DEFAULT_PROVENANCE_POLICY,
    extraction_policy_version: str = EXTRACTION_POLICY_VERSION,
) -> EvaluationReport:
    """
    Evaluate every document in ``corpus``.

    ``canonical_texts`` maps each ``document_ref`` to its materialised
    canonical text. A document with no entry is skipped rather than
    scored: reporting it as all-false-negatives would blame the rules for
    a corpus that could not be loaded.
    """

    documents = tuple(
        evaluate_document(
            document,
            extract_evidence(
                canonical_texts[document.document_ref],
                extraction_policy_version=extraction_policy_version,
            ).evidence,
            provenance_policy=provenance_policy,
        )
        for document in corpus.documents
        if document.document_ref in canonical_texts
    )

    return EvaluationReport(
        corpus_id=corpus.corpus_id,
        corpus_version=corpus.corpus_version,
        extraction_policy_version=extraction_policy_version,
        provenance_policy=provenance_policy,
        rule_versions=current_rule_versions(),
        documents=documents,
    )


def current_rule_versions() -> tuple[tuple[str, str], ...]:
    """
    Every rule in the catalogue and its version, at evaluation time.

    Recorded on the report so that "which rule changed?" is answerable
    from two reports alone, without anybody having to reconstruct what
    the catalogue looked like on the day.
    """

    return tuple(
        sorted((rule.rule_id, rule.rule_version) for rule in EXTRACTION_RULES)
    )
