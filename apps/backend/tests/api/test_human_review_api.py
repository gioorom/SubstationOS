"""
The Human Review API, end to end.

Two things these tests exist to prove, above everything else:

1. **Recording a judgement changes no engineering artefact.** The
   semantic set before and after a review compares equal, byte for byte.
2. **A pipeline re-run never silently discards a review.** The
   re-run scenarios below drive real stages over real documents and
   assert what each transition does to a recorded judgement.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.identity.identity_roles import Role
from tests._pdf_builder import single_page_pdf
from tests.conftest import _make_user, authenticate

TRANSFORMER = "Trasformatore TR1 630 kVA"


def _upload(api_client: TestClient, content: bytes) -> int:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": ("schema.pdf", io.BytesIO(content), "application/pdf")
        },
        data={"scope": "canonical_library"},
    )

    assert response.status_code == 200

    return response.json()["document"]["id"]


def _run_pipeline(api_client: TestClient, document_id: int) -> None:
    api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document_id}
    )

    for stage in (
        "canonical-representation",
        "canonical-text",
        "engineering-evidence",
        "engineering-entities",
        "engineering-facts",
        "engineering-semantics",
    ):
        api_client.post(f"/documents/{document_id}/{stage}")


def _statements(api_client: TestClient, document_id: int) -> list[dict]:
    response = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    )

    assert response.status_code == 200

    return response.json()["statements"]


@pytest.fixture()
def reviewed_document(api_client: TestClient) -> tuple[int, str]:
    """A document with one interpreted statement, ready to review."""

    document_id = _upload(api_client, single_page_pdf(TRANSFORMER))
    _run_pipeline(api_client, document_id)

    statements = _statements(api_client, document_id)

    assert statements, "the fixture document produced no statement"

    return (document_id, statements[0]["statement_key"])


def _approve(
    api_client: TestClient,
    document_id: int,
    statement_key: str,
    **overrides,
):
    payload = {
        "decision": "approved",
        "reason": "confirmed_by_source",
        "comment": None,
    }
    payload.update(overrides)

    return api_client.post(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        json=payload,
    )


# --- Recording a judgement -----------------------------------------------


def test_an_engineer_can_record_a_judgement(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    response = _approve(api_client, document_id, statement_key)

    assert response.status_code == 201

    body = response.json()

    assert body["decision"] == "approved"
    assert body["target_key"] == statement_key
    assert body["reviewer"]["email"] == "engineer@substationos.test"


def test_the_reviewer_is_the_authenticated_identity(
    api_client: TestClient, reviewed_document
) -> None:
    """
    There is no field in the request body through which a caller could
    name somebody else - the same guarantee EPIC 30.3 gave project
    creation.
    """

    document_id, statement_key = reviewed_document

    response = api_client.post(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        json={
            "decision": "approved",
            "reason": "confirmed_by_source",
            "reviewer": {"user_id": 999, "display_name": "Somebody Else"},
        },
    )

    assert response.status_code == 201
    assert response.json()["reviewer"]["display_name"] == "Test Engineer"


def test_a_review_records_the_identity_the_statement_had(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    snapshot = _approve(api_client, document_id, statement_key).json()[
        "snapshot"
    ]

    assert snapshot["semantic_rule_id"]
    assert snapshot["semantic_rule_version"]
    assert snapshot["content_checksum"]
    assert snapshot["semantic_policy_version"]
    assert snapshot["support_fingerprint"]
    assert snapshot["support_count"] >= 1


def test_a_review_carries_no_engineering_payload(
    api_client: TestClient, reviewed_document
) -> None:
    """
    A review names an artefact; it never contains one. What the statement
    said is read from the semantic endpoints, which stay its single
    account.
    """

    document_id, statement_key = reviewed_document

    body = _approve(api_client, document_id, statement_key).json()

    for forbidden in (
        "statement_type",
        "subject_entity_key",
        "object_entity_key",
        "supporting_fact_keys",
        "value",
        "unit",
    ):
        assert forbidden not in str(body)


# --- The rule the whole EPIC turns on ------------------------------------


def test_recording_a_review_changes_no_engineering_artefact(
    api_client: TestClient, reviewed_document
) -> None:
    """
    **Engineering truth and engineering judgement stay separate.** The
    semantic set before and after a review compares equal.
    """

    document_id, statement_key = reviewed_document

    before = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()

    _approve(api_client, document_id, statement_key)
    _approve(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="incorrect_interpretation",
        comment="la potenza indicata non è quella nominale",
    )

    after = api_client.get(
        f"/documents/{document_id}/engineering-semantics"
    ).json()

    assert before == after


def test_a_reviewed_statement_can_still_be_re_interpreted(
    api_client: TestClient, reviewed_document
) -> None:
    """
    A review does not lock the pipeline. Re-running the semantic stage
    over reviewed statements is a normal thing to do and must produce the
    same artefacts it always would.
    """

    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    before = _statements(api_client, document_id)

    assert (
        api_client.post(
            f"/documents/{document_id}/engineering-semantics"
        ).status_code
        == 200
    )

    assert _statements(api_client, document_id) == before


# --- Append-only ---------------------------------------------------------


def test_a_second_judgement_appends_rather_than_replacing(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    first = _approve(api_client, document_id, statement_key).json()

    second = _approve(
        api_client,
        document_id,
        statement_key,
        decision="needs_investigation",
        reason="ambiguous_evidence",
        comment="due potenze sulla stessa riga",
    )

    # 201, not 200: a second judgement *creates* a second record.
    assert second.status_code == 201
    assert second.json()["review_id"] != first["review_id"]

    history = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews"
    ).json()

    assert history["pagination"]["total"] == 2


def test_an_earlier_judgement_is_never_modified(
    api_client: TestClient, reviewed_document
) -> None:
    """
    "What did we think in March?" is a question an engineering record has
    to be able to answer.
    """

    document_id, statement_key = reviewed_document

    first = _approve(api_client, document_id, statement_key).json()

    _approve(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="incorrect_interpretation",
        comment="rivisto",
    )

    history = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews"
    ).json()

    older = next(
        entry
        for entry in history["items"]
        if entry["review"]["review_id"] == first["review_id"]
    )

    assert older["review"] == first
    assert older["superseded"] is True


def test_there_is_no_way_to_edit_or_delete_a_review(
    api_client: TestClient,
) -> None:
    """
    The append-only guarantee, visible from outside: the collection has a
    `POST` and no member has a `PATCH` or a `DELETE`.
    """

    schema = api_client.app.openapi()

    review_paths = {
        path: set(operations)
        for path, operations in schema["paths"].items()
        if "review" in path
    }

    assert review_paths

    for path, methods in review_paths.items():
        assert "patch" not in methods, path
        assert "put" not in methods, path
        assert "delete" not in methods, path


# --- The current decision is a projection --------------------------------


def test_a_statement_nobody_reviewed_has_no_decision(
    api_client: TestClient, reviewed_document
) -> None:
    """
    Distinct from every decision, and never rendered as one.
    """

    document_id, statement_key = reviewed_document

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["current"] is None
    assert body["review_count"] == 0


def test_the_current_decision_is_the_newest_judgement(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)
    _approve(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="il disegno è superato",
    )

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["current"]["decision"] == "rejected"
    assert body["review_count"] == 2
    assert body["applicability"] == "applies"


def test_a_document_summary_answers_for_every_reviewed_statement(
    api_client: TestClient, reviewed_document
) -> None:
    """
    One request, so a Workspace listing statements does not make one per
    row. Unreviewed statements are absent rather than present with a null
    decision.
    """

    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/reviews"
    ).json()

    assert body["document_id"] == document_id
    assert len(body["items"]) == 1
    assert body["items"][0]["target_key"] == statement_key


# --- Pipeline re-runs ----------------------------------------------------


def test_a_re_run_that_changes_nothing_leaves_the_review_attached(
    api_client: TestClient, reviewed_document
) -> None:
    """
    `statement_key` is deterministic, so an identical re-run reproduces
    the identical key and there is nothing to detect.
    """

    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    for stage in ("engineering-facts", "engineering-semantics"):
        api_client.post(f"/documents/{document_id}/{stage}")

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["applicability"] == "applies"


def test_a_review_of_a_statement_that_no_longer_exists_survives(
    api_client: TestClient, db_session: Session, reviewed_document
) -> None:
    """
    The judgement is **marked**, not discarded, and stays fully readable
    with the identity it was passed under.
    """

    document_id, statement_key = reviewed_document

    recorded = _approve(api_client, document_id, statement_key).json()

    # Remove the statement the way a re-interpretation under new rules
    # would: the set stays, this key does not.
    from app.models.engineering_semantics import (
        EngineeringSemanticStatementRecord,
    )

    db_session.query(EngineeringSemanticStatementRecord).filter(
        EngineeringSemanticStatementRecord.statement_key == statement_key
    ).delete()
    db_session.commit()

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["applicability"] == "requires_revalidation"
    assert body["current"]["review_id"] == recorded["review_id"]
    assert body["current"]["decision"] == "approved"
    assert body["current"]["snapshot"]["semantic_rule_version"]


def test_a_review_is_orphaned_when_the_interpretation_is_gone(
    api_client: TestClient, db_session: Session, reviewed_document
) -> None:
    """
    Nothing to compare against - the semantic stage has not been run
    since, or its set was removed. Different from the pipeline having
    moved on, and reported differently.
    """

    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    from app.models.engineering_semantics import (
        EngineeringSemanticSetRecord,
    )

    db_session.query(EngineeringSemanticSetRecord).filter(
        EngineeringSemanticSetRecord.document_id == document_id
    ).delete()
    db_session.commit()

    body = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["applicability"] == "orphaned"
    assert body["current"] is not None


def test_a_statement_that_never_existed_cannot_be_reviewed(
    api_client: TestClient, reviewed_document
) -> None:
    """
    A review may only be recorded against something in the document's
    *current* interpretation. Reviewing a statement that is already gone
    would produce a judgement that was stale the moment it was written.
    """

    document_id, _ = reviewed_document

    response = _approve(api_client, document_id, "f" * 64)

    assert response.status_code == 404


def test_a_document_with_no_interpretation_cannot_be_reviewed(
    api_client: TestClient
) -> None:
    document_id = _upload(api_client, single_page_pdf(TRANSFORMER))

    assert _approve(api_client, document_id, "a" * 64).status_code == 404


# --- Policy at the boundary ----------------------------------------------


def test_a_rejection_without_an_explanation_is_refused(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    response = _approve(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="incorrect_interpretation",
        comment=None,
    )

    assert response.status_code == 422
    assert "comment" in response.json()["detail"]


def test_a_reason_that_does_not_fit_the_decision_is_refused(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    response = _approve(
        api_client,
        document_id,
        statement_key,
        decision="approved",
        reason="incorrect_interpretation",
    )

    assert response.status_code == 422


def test_the_vocabulary_is_served_rather_than_duplicated(
    api_client: TestClient,
) -> None:
    body = api_client.get("/engineering-reviews/vocabulary").json()

    assert set(body["decisions"]) == {
        "approved",
        "rejected",
        "needs_investigation",
    }
    assert "incorrect_interpretation" in body["reasons_by_decision"][
        "rejected"
    ]
    assert "incorrect_interpretation" not in body["reasons_by_decision"][
        "approved"
    ]
    assert set(body["decisions_requiring_comment"]) == {
        "rejected",
        "needs_investigation",
    }


# --- Authorization -------------------------------------------------------


def test_an_anonymous_caller_reaches_no_review_endpoint(
    anonymous_client: TestClient,
) -> None:
    for method, path in (
        ("GET", "/engineering-reviews/vocabulary"),
        ("GET", "/documents/1/engineering-semantics/reviews"),
        ("GET", "/documents/1/engineering-semantics/abc/current-review"),
        ("GET", "/documents/1/engineering-semantics/abc/reviews"),
        ("POST", "/documents/1/engineering-semantics/abc/reviews"),
    ):
        assert (
            anonymous_client.request(method, path).status_code == 401
        ), path


def test_an_administrator_may_also_review(
    administrator_client: TestClient, api_client: TestClient
) -> None:
    document_id = _upload(api_client, single_page_pdf(TRANSFORMER))
    _run_pipeline(api_client, document_id)

    statements = _statements(api_client, document_id)

    assert (
        _approve(
            administrator_client, document_id, statements[0]["statement_key"]
        ).status_code
        == 201
    )


def test_the_review_is_recorded_in_the_audit_trail(
    api_client: TestClient,
    administrator_client: TestClient,
    reviewed_document,
) -> None:
    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    events = administrator_client.get(
        "/audit/events",
        params={"action": "engineering_review_recorded"},
    ).json()["items"]

    assert len(events) == 1
    assert events[0]["actor"]["authenticated"] is True
    assert events[0]["resource_type"] == "semantic_statement"
    assert "approved" in events[0]["detail"]


def test_superseding_a_review_is_recorded_too(
    api_client: TestClient,
    administrator_client: TestClient,
    reviewed_document,
) -> None:
    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)
    _approve(
        api_client,
        document_id,
        statement_key,
        decision="rejected",
        reason="documentation_issue",
        comment="disegno superato",
    )

    events = administrator_client.get(
        "/audit/events",
        params={"action": "engineering_review_superseded"},
    ).json()["items"]

    assert len(events) == 1


# --- History paging ------------------------------------------------------


def test_history_is_paged_and_newest_first(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    for index in range(3):
        _approve(
            api_client,
            document_id,
            statement_key,
            decision="needs_investigation",
            reason="ambiguous_evidence",
            comment=f"osservazione {index}",
        )

    first_page = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        params={"page": 1, "page_size": 2},
    ).json()

    assert first_page["pagination"]["total"] == 3
    assert first_page["pagination"]["has_next"] is True
    assert len(first_page["items"]) == 2
    assert first_page["items"][0]["superseded"] is False

    ids = [entry["review"]["review_id"] for entry in first_page["items"]]

    assert ids == sorted(ids, reverse=True)


def test_nothing_on_a_later_page_is_the_current_review(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    for index in range(3):
        _approve(
            api_client,
            document_id,
            statement_key,
            decision="needs_investigation",
            reason="ambiguous_evidence",
            comment=f"osservazione {index}",
        )

    second_page = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews",
        params={"page": 2, "page_size": 2},
    ).json()

    assert all(entry["superseded"] for entry in second_page["items"])


def test_history_of_an_unreviewed_statement_is_empty_not_missing(
    api_client: TestClient, reviewed_document
) -> None:
    document_id, statement_key = reviewed_document

    response = api_client.get(
        f"/documents/{document_id}/engineering-semantics/"
        f"{statement_key}/reviews"
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


# --- Isolation between documents -----------------------------------------


def test_a_review_does_not_leak_across_documents(
    api_client: TestClient, reviewed_document
) -> None:
    """
    Statement keys are deterministic hashes, and two documents could in
    principle be handed the same key by a caller. The document is part of
    the target's identity, so one document's judgement is never another's.
    """

    document_id, statement_key = reviewed_document

    _approve(api_client, document_id, statement_key)

    other_id = _upload(api_client, single_page_pdf("Interruttore Q1 145 kV"))

    body = api_client.get(
        f"/documents/{other_id}/engineering-semantics/"
        f"{statement_key}/current-review"
    ).json()

    assert body["current"] is None
