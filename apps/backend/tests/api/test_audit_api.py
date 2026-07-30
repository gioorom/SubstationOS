"""
The audit trail.

What is recorded, what is deliberately not, and the one property this
whole EPIC turns on: **audit identity attaches to actions, never to
artefacts**. Two users running the same pipeline over the same document
must produce byte-identical engineering output and two distinguishable
audit events.
"""

from __future__ import annotations

import io
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.services import audit_service
from tests._pdf_builder import single_page_pdf
from tests.conftest import authenticate


def _events(client: TestClient, **query) -> list[dict]:
    response = client.get("/audit/events", params=query)

    assert response.status_code == 200

    return response.json()["items"]


# --- What gets recorded --------------------------------------------------


def test_creating_a_project_is_recorded(
    api_client: TestClient,
    administrator_client: TestClient,
) -> None:
    api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    )

    events = _events(
        administrator_client, action=AuditAction.PROJECT_CREATED.value
    )

    assert len(events) == 1
    assert events[0]["outcome"] == "succeeded"
    assert events[0]["resource_type"] == "project"
    assert events[0]["actor"]["authenticated"] is True
    assert "Test Engineer" in events[0]["actor"]["description"]


def test_uploading_a_document_is_recorded(
    api_client: TestClient, administrator_client: TestClient
) -> None:
    api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema.pdf",
                io.BytesIO(single_page_pdf()),
                "application/pdf",
            )
        },
        data={"scope": "canonical_library"},
    )

    events = _events(
        administrator_client, action=AuditAction.DOCUMENT_UPLOADED.value
    )

    assert len(events) == 1
    assert events[0]["resource_type"] == "document"
    assert events[0]["actor"]["authenticated"] is True


def test_a_failed_login_is_recorded_without_the_password(
    anonymous_client: TestClient, administrator_client: TestClient
) -> None:
    anonymous_client.post(
        "/auth/login",
        json={
            "email": "nobody@substationos.test",
            "password": "una password segreta",
        },
    )

    events = _events(
        administrator_client, action=AuditAction.LOGIN_FAILED.value
    )

    assert len(events) == 1

    recorded = str(events[0])

    assert "una password segreta" not in recorded
    assert events[0]["actor"]["authenticated"] is False
    assert "nobody@substationos.test" in events[0]["actor"]["description"]


def test_an_unauthenticated_actor_is_recorded_as_an_attempt(
    anonymous_client: TestClient, administrator_client: TestClient
) -> None:
    """
    The address someone typed at a login form is untrusted input. It says
    what was attempted; it never says who attempted it.
    """

    anonymous_client.post(
        "/auth/login",
        json={"email": "administrator@substationos.test", "password": "x" * 20},
    )

    events = _events(
        administrator_client, action=AuditAction.LOGIN_FAILED.value
    )

    assert events[0]["actor"]["user_id"] is None
    assert events[0]["actor"]["session_id"] is None
    assert "attempted" in events[0]["actor"]["description"]


def test_a_refused_deletion_is_recorded_as_denied(
    api_client: TestClient,
    administrator_client: TestClient,
    db_session: Session,
    secured_app,
    engineer,
) -> None:
    created = api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    ).json()

    # A second engineer, who does not own it.
    from app.domain.identity.identity_roles import Role
    from tests.conftest import _make_user

    other = _make_user(
        db_session,
        email="other@substationos.test",
        display_name="Other Engineer",
        role=Role.ENGINEER,
    )

    with TestClient(secured_app) as other_client:
        authenticate(other_client, db_session, other)

        refused = other_client.delete(f"/projects/{created['id']}")

    assert refused.status_code == 403

    events = _events(
        administrator_client, action=AuditAction.ACCESS_DENIED.value
    )

    assert len(events) == 1
    assert events[0]["outcome"] == "denied"


# --- What the trail carries ----------------------------------------------


def test_every_event_carries_actor_time_action_resource_and_outcome(
    api_client: TestClient, administrator_client: TestClient
) -> None:
    api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    )

    event = _events(administrator_client)[0]

    for field in (
        "actor",
        "occurred_at",
        "action",
        "resource_type",
        "outcome",
    ):
        assert event[field] is not None


def test_the_trail_is_newest_first(
    api_client: TestClient, administrator_client: TestClient
) -> None:
    for index in range(3):
        api_client.post(
            "/projects/",
            json={
                "name": f"Cabina {index}",
                "code": f"CP-{index}-2026",
                "customer": "Distributore Nazionale",
            },
        )

    events = _events(
        administrator_client, action=AuditAction.PROJECT_CREATED.value
    )

    assert [event["event_id"] for event in events] == sorted(
        (event["event_id"] for event in events), reverse=True
    )


def test_the_trail_can_be_filtered_by_actor(
    api_client: TestClient, administrator_client: TestClient, engineer
) -> None:
    api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": "CP-GAMMA-2026",
            "customer": "Distributore Nazionale",
        },
    )

    events = _events(administrator_client, user_id=engineer.user_id)

    assert events
    assert all(
        event["actor"]["user_id"] == engineer.user_id for event in events
    )


def test_an_unbounded_read_is_refused_rather_than_clamped(
    administrator_client: TestClient,
) -> None:
    assert (
        administrator_client.get("/audit/events", params={"limit": 100000})
    ).status_code == 422


def test_there_is_no_way_to_write_an_audit_event_over_the_api(
    administrator_client: TestClient,
) -> None:
    """
    An API that let a client post an audit event would be an API for
    writing fiction into the record.
    """

    schema = administrator_client.app.openapi()
    audit_paths = {
        path: operations
        for path, operations in schema["paths"].items()
        if path.startswith("/audit")
    }

    assert audit_paths
    assert all(
        set(operations) <= {"get"} for operations in audit_paths.values()
    )


def test_an_audit_write_that_fails_does_not_fail_the_action(
    db_session: Session,
) -> None:
    """
    Deliberate and uncomfortable: a login that worked, refused at the last
    moment because the trail could not be appended to, is worse than a
    login that worked and is missing from the trail.
    """

    class BrokenRepository(SqlAlchemyAuditRepository):
        def record(self, event):
            raise RuntimeError("the audit table is unwritable")

    recorded = audit_service.record_anonymous(
        BrokenRepository(db_session),
        action=AuditAction.LOGIN_FAILED,
        outcome=AuditOutcome.DENIED,
        resource=AuditResource("authentication"),
        now=datetime.utcnow(),
    )

    assert recorded is None


# --- The rule the EPIC turns on ------------------------------------------


def test_the_pipeline_produces_identical_artefacts_under_two_users(
    api_client: TestClient,
    secured_app,
    db_session: Session,
) -> None:
    """
    **Audit identity belongs to actions, not artefacts.**

    An entity, a fact and a statement are functions of the document's
    bytes and the versioned rules that read them. If any of them carried
    a user, running the pipeline twice under two logins would produce two
    different answers and the platform would stop being deterministic.
    """

    document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema.pdf",
                io.BytesIO(single_page_pdf("Trasformatore TR1 630 kVA")),
                "application/pdf",
            )
        },
        data={"scope": "canonical_library"},
    ).json()["document"]

    document_id = document["id"]

    api_client.post("/documents/ingestion/jobs", json={"document_id": document_id})
    api_client.post(f"/documents/{document_id}/canonical-representation")
    api_client.post(f"/documents/{document_id}/canonical-text")
    api_client.post(f"/documents/{document_id}/engineering-evidence")
    api_client.post(f"/documents/{document_id}/engineering-entities")

    first = api_client.get(
        f"/documents/{document_id}/engineering-entities"
    ).json()

    # A different person, re-running the same stage over the same bytes.
    from app.domain.identity.identity_roles import Role
    from tests.conftest import _make_user

    other = _make_user(
        db_session,
        email="second@substationos.test",
        display_name="Second Engineer",
        role=Role.ENGINEER,
    )

    with TestClient(secured_app) as other_client:
        authenticate(other_client, db_session, other)

        other_client.post(
            f"/documents/{document_id}/engineering-entities"
        )

        second = other_client.get(
            f"/documents/{document_id}/engineering-entities"
        ).json()

    assert first == second


def test_no_engineering_artefact_response_names_a_user(
    api_client: TestClient,
) -> None:
    document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "schema.pdf",
                io.BytesIO(single_page_pdf("Trasformatore TR1 630 kVA")),
                "application/pdf",
            )
        },
        data={"scope": "canonical_library"},
    ).json()["document"]

    document_id = document["id"]

    api_client.post("/documents/ingestion/jobs", json={"document_id": document_id})
    api_client.post(f"/documents/{document_id}/canonical-representation")
    api_client.post(f"/documents/{document_id}/canonical-text")
    api_client.post(f"/documents/{document_id}/engineering-evidence")

    body = api_client.get(
        f"/documents/{document_id}/engineering-evidence"
    ).text

    for leak in ("user_id", "engineer@substationos.test", "Test Engineer"):
        assert leak not in body
