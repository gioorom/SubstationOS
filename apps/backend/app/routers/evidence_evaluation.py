"""
The Engineering Evidence Evaluation API (Milestone 28.2).

```
GET  /evidence-evaluation/corpora                          list corpora
POST /evidence-evaluation/corpora/{corpus_id}/evaluate     run an evaluation
GET  /evidence-evaluation/corpora/{corpus_id}/reports      the history
GET  /evidence-evaluation/reports/{report_id}              one report in full
GET  /evidence-evaluation/reports/{baseline}/compare/{candidate}
```

**Evaluation is a first-class product capability, not a test harness.**
Every new extraction rule is evaluated against the reference corpus
before it becomes part of the supported deterministic pipeline, and every
rule change is compared against the previous evaluation to see what it
broke - through these endpoints, by a person or by CI.

The composition root builds the corpus repository and the report
repository, and nothing else: there is no evidence repository here,
because an evaluation measures the *current rules* rather than what was
stored on some past day.

`201` when an evaluation was recorded - including one that scored badly,
which is a result and not an error. `404` for a corpus or report that
does not exist. Everything else returns `200` with a
`succeeded: false` result carrying the typed cause, so `422` keeps
meaning exactly one thing across this codebase.

No ORM model is exposed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.evidence_evaluation.evaluation_failures import (
    EvaluationFailureCode,
)
from app.infrastructure.evidence_evaluation.sqlalchemy_evaluation_report_repository import (  # noqa: E501
    SqlAlchemyEvaluationReportRepository,
)
from app.infrastructure.evidence_evaluation.yaml_reference_corpus_repository import (  # noqa: E501
    YamlReferenceCorpusRepository,
)
from app.schemas.evidence_evaluation import (
    EvaluationReportRead,
    EvaluationReportSummaryRead,
    EvaluationRunResultRead,
    RegressionReportRead,
)
from app.services import evidence_evaluation_service

router = APIRouter(
    prefix="/evidence-evaluation",
    tags=["Engineering Evidence Evaluation"],
)

_STATUS_FOR_FAILURE: dict[EvaluationFailureCode, int] = {
    EvaluationFailureCode.CORPUS_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    EvaluationFailureCode.REPORT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    EvaluationFailureCode.REPORT_PERSISTENCE_FAILURE: (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    ),
}


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/corpora",
    response_model=list[str],
    summary="Every reference corpus available in this repository",
)
def list_corpora() -> list[str]:
    return list(YamlReferenceCorpusRepository().list_corpora())


@router.post(
    "/corpora/{corpus_id}/evaluate",
    response_model=EvaluationRunResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate the extraction rules against a reference corpus "
    "and record the report",
)
def evaluate_corpus(
    corpus_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> EvaluationRunResultRead:
    result = evidence_evaluation_service.evaluate_corpus(
        YamlReferenceCorpusRepository(),
        SqlAlchemyEvaluationReportRepository(db),
        corpus_id=corpus_id,
    )

    if not result.succeeded:
        error_status = _STATUS_FOR_FAILURE.get(result.failure.code)

        if error_status is not None:
            raise HTTPException(
                status_code=error_status, detail=result.failure.message
            )

        response.status_code = status.HTTP_200_OK

    return EvaluationRunResultRead.from_domain(result)


@router.get(
    "/corpora/{corpus_id}/reports",
    response_model=list[EvaluationReportSummaryRead],
    summary="Every evaluation recorded for a corpus, newest first",
)
def list_reports(
    corpus_id: str,
    db: Session = Depends(get_db),
) -> list[EvaluationReportSummaryRead]:
    return [
        EvaluationReportSummaryRead.from_domain(stored)
        for stored in evidence_evaluation_service.list_reports(
            SqlAlchemyEvaluationReportRepository(db), corpus_id
        )
    ]


@router.get(
    "/reports/{report_id}",
    response_model=EvaluationReportRead,
    summary="One evaluation report, with per-document, per-type and "
    "per-rule metrics and every item's verdict",
)
def read_report(
    report_id: int,
    db: Session = Depends(get_db),
) -> EvaluationReportRead:
    stored = evidence_evaluation_service.get_report(
        SqlAlchemyEvaluationReportRepository(db), report_id
    )

    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evaluation report '{report_id}' exists.",
        )

    return EvaluationReportRead.from_domain(stored)


@router.get(
    "/reports/{baseline_report_id}/compare/{candidate_report_id}",
    response_model=RegressionReportRead,
    summary="Compare two evaluations and name the items that changed",
)
def compare_reports(
    baseline_report_id: int,
    candidate_report_id: int,
    db: Session = Depends(get_db),
) -> RegressionReportRead:
    result = evidence_evaluation_service.compare_reports(
        SqlAlchemyEvaluationReportRepository(db),
        baseline_report_id=baseline_report_id,
        candidate_report_id=candidate_report_id,
    )

    if not result.succeeded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.failure.message,
        )

    return RegressionReportRead.from_domain(result.regression)
