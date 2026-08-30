"""
API tests for Engineering Evidence Evaluation (Milestone 28.2).

Evaluation is a first-class product capability, so these test it as one:
list the corpora, run an evaluation, read the report, compare two runs.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

REFERENCE_CORPUS = "substation_reference"


def _evaluate(api_client: TestClient, corpus_id: str = REFERENCE_CORPUS):
    return api_client.post(
        f"/evidence-evaluation/corpora/{corpus_id}/evaluate"
    )


# --- Corpora ------------------------------------------------------------------


def test_the_reference_corpus_is_listed(api_client: TestClient) -> None:
    response = api_client.get("/evidence-evaluation/corpora")

    assert response.status_code == 200
    assert REFERENCE_CORPUS in response.json()


# --- Running an evaluation ------------------------------------------------------


def test_evaluating_the_reference_corpus_returns_201(
    api_client: TestClient,
) -> None:
    response = _evaluate(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["report"]["corpus_id"] == REFERENCE_CORPUS
    assert body["report"]["corpus_version"] == "1.0"


def test_the_report_carries_exact_metrics(api_client: TestClient) -> None:
    """Serialised as strings, not floats - two runs must render the same
    numbers."""

    metrics = _evaluate(api_client).json()["report"]["metrics"]

    assert metrics["true_positives"] == 18
    assert metrics["false_positives"] == 0
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == "1.000000"
    assert metrics["recall"] == "0.947368"
    assert metrics["f1"] == "0.972973"


def test_the_report_breaks_metrics_down_by_type_and_rule(
    api_client: TestClient,
) -> None:
    report = _evaluate(api_client).json()["report"]

    assert (
        report["metrics_by_evidence_type"]["designation"][
            "false_negatives"
        ]
        == 1
    )
    assert "designation_generic@1.0" in report["metrics_by_rule"]
    assert {
        document["document_ref"] for document in report["documents"]
    } == {
        "bay_data_sheet",
        "cable_schedule",
        "descriptive_prose",
        "ambiguous_ratings",
        "designation_variants",
    }


def test_the_report_records_every_rule_version(
    api_client: TestClient,
) -> None:
    report = _evaluate(api_client).json()["report"]
    versions = {
        entry["rule_id"]: entry["rule_version"]
        for entry in report["rule_versions"]
    }

    assert versions["designation_generic"] == "1.0"
    assert len(versions) == 6


def test_the_failing_item_is_named_in_the_report(
    api_client: TestClient,
) -> None:
    """A report that only gave a number would not tell anybody what to
    fix."""

    report = _evaluate(api_client).json()["report"]
    misses = [
        result
        for document in report["documents"]
        for result in document["results"]
        if result["outcome"] != "true_positive"
    ]

    assert [result["observed_text"] for result in misses] == ["TR-1"]
    assert misses[0]["outcome"] == "false_negative"
    assert misses[0]["rule_id"] == "designation_generic"
    assert misses[0]["line_index"] == 1


def test_an_undefined_metric_is_null_not_zero(
    api_client: TestClient,
) -> None:
    """The prose document predicts nothing and expects nothing, so its
    precision is a question that was never asked."""

    report = _evaluate(api_client).json()["report"]
    prose = next(
        document
        for document in report["documents"]
        if document["document_ref"] == "descriptive_prose"
    )

    assert prose["metrics"]["precision"] is None
    assert prose["metrics"]["recall"] is None
    assert prose["metrics"]["f1"] is None


# --- Reading and listing --------------------------------------------------------


def test_a_report_can_be_read_back(api_client: TestClient) -> None:
    report_id = _evaluate(api_client).json()["report"]["report_id"]

    response = api_client.get(f"/evidence-evaluation/reports/{report_id}")

    assert response.status_code == 200
    assert response.json()["report_id"] == report_id
    assert response.json()["documents"]


def test_the_history_of_a_corpus_is_listed_newest_first(
    api_client: TestClient,
) -> None:
    _evaluate(api_client)
    latest = _evaluate(api_client).json()["report"]["report_id"]

    response = api_client.get(
        f"/evidence-evaluation/corpora/{REFERENCE_CORPUS}/reports"
    )

    assert response.status_code == 200
    assert [entry["report_id"] for entry in response.json()][0] == latest
    assert len(response.json()) == 2


def test_an_unknown_report_returns_404(api_client: TestClient) -> None:
    assert (
        api_client.get("/evidence-evaluation/reports/9999").status_code
        == 404
    )


def test_an_unknown_corpus_returns_404(api_client: TestClient) -> None:
    assert _evaluate(api_client, "no_such_corpus").status_code == 404


# --- Comparing ------------------------------------------------------------------


def test_two_evaluations_can_be_compared(api_client: TestClient) -> None:
    baseline = _evaluate(api_client).json()["report"]["report_id"]
    candidate = _evaluate(api_client).json()["report"]["report_id"]

    response = api_client.get(
        f"/evidence-evaluation/reports/{baseline}/compare/{candidate}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comparable"] is True
    assert body["has_regression"] is False
    assert body["regressions"] == []


def test_a_comparison_reports_the_metric_deltas(
    api_client: TestClient,
) -> None:
    baseline = _evaluate(api_client).json()["report"]["report_id"]
    candidate = _evaluate(api_client).json()["report"]["report_id"]

    body = api_client.get(
        f"/evidence-evaluation/reports/{baseline}/compare/{candidate}"
    ).json()
    deltas = {entry["name"]: entry for entry in body["metric_deltas"]}

    assert set(deltas) == {"precision", "recall", "f1"}
    assert deltas["recall"]["baseline"] == "0.947368"
    assert deltas["recall"]["delta"] == "0.000000"
    assert deltas["recall"]["decreased"] is False


def test_comparing_against_a_missing_report_returns_404(
    api_client: TestClient,
) -> None:
    baseline = _evaluate(api_client).json()["report"]["report_id"]

    response = api_client.get(
        f"/evidence-evaluation/reports/{baseline}/compare/9999"
    )

    assert response.status_code == 404


# --- No ORM is exposed ------------------------------------------------------------


def test_no_orm_model_is_exposed(api_client: TestClient) -> None:
    report_id = _evaluate(api_client).json()["report"]["report_id"]

    body = api_client.get(
        f"/evidence-evaluation/reports/{report_id}"
    ).json()

    assert "id" not in body
    for document in body["documents"]:
        assert "id" not in document
        assert "report_id" not in document
        for result in document["results"]:
            assert "id" not in result
            assert "document_evaluation_id" not in result
