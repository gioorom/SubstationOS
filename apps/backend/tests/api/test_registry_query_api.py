"""
Server-side pagination, filtering, search and sorting (Milestone 30.1.3).

Before this milestone both list endpoints returned the whole table and
the client filtered it. These tests specify the contract that replaced
that, and hold it to the two properties that make it worth having:
**the total is the whole result set, not the page**, and **the order is
deterministic**.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
)


def _project(
    api_client: TestClient,
    *,
    code: str,
    name: str = "Cabina Primaria",
    customer: str = "Distributore Nazionale",
    location: str | None = None,
    status: str = "planning",
) -> dict:
    payload = {
        "name": name,
        "code": code,
        "customer": customer,
        "status": status,
    }

    if location is not None:
        payload["location"] = location

    response = api_client.post("/projects/", json=payload)

    assert response.status_code == 201

    return response.json()


def _upload(
    api_client: TestClient,
    *,
    filename: str,
    project_id: int | None = None,
    content: bytes = b"%PDF-1.7 test",
    mime_type: str = "application/pdf",
) -> dict:
    data = (
        {"scope": "project", "project_id": str(project_id)}
        if project_id is not None
        else {"scope": "canonical_library"}
    )

    response = api_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), mime_type)},
        data=data,
    )

    assert response.status_code == 200

    return response.json()["document"]


# --- Pagination ------------------------------------------------------------


def test_a_project_list_is_a_typed_envelope(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001")

    body = api_client.get("/projects/").json()

    assert set(body) == {"items", "pagination"}
    assert set(body["pagination"]) == {
        "page",
        "page_size",
        "total",
        "total_pages",
        "has_next",
        "has_previous",
    }


def test_a_document_list_is_a_typed_envelope(
    api_client: TestClient,
) -> None:
    _upload(api_client, filename="a.pdf")

    body = api_client.get("/documents/").json()

    assert set(body) == {"items", "pagination"}


def test_project_pagination_reports_the_full_total(
    api_client: TestClient,
) -> None:
    for index in range(7):
        _project(api_client, code=f"CP-{index:03d}")

    body = api_client.get(
        "/projects/", params={"page": 1, "page_size": 3}
    ).json()

    assert len(body["items"]) == 3

    # The total is the whole result set - a client cannot tell whether it
    # has seen everything without it.
    assert body["pagination"]["total"] == 7
    assert body["pagination"]["total_pages"] == 3
    assert body["pagination"]["has_next"] is True
    assert body["pagination"]["has_previous"] is False


def test_project_pagination_walks_without_repeating_or_skipping(
    api_client: TestClient,
) -> None:
    for index in range(7):
        _project(api_client, code=f"CP-{index:03d}")

    seen: list[str] = []

    for page in (1, 2, 3):
        body = api_client.get(
            "/projects/", params={"page": page, "page_size": 3}
        ).json()

        seen.extend(item["code"] for item in body["items"])

    assert len(seen) == 7
    assert len(set(seen)) == 7


def test_the_last_page_reports_no_next(api_client: TestClient) -> None:
    for index in range(4):
        _project(api_client, code=f"CP-{index:03d}")

    body = api_client.get(
        "/projects/", params={"page": 2, "page_size": 3}
    ).json()

    assert len(body["items"]) == 1
    assert body["pagination"]["has_next"] is False
    assert body["pagination"]["has_previous"] is True


def test_a_page_beyond_the_end_is_empty_not_an_error(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001")

    response = api_client.get(
        "/projects/", params={"page": 99, "page_size": 10}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pagination"]["total"] == 1


def test_document_pagination_reports_the_full_total(
    api_client: TestClient,
) -> None:
    for index in range(5):
        _upload(api_client, filename=f"doc-{index}.pdf")

    body = api_client.get(
        "/documents/", params={"page": 1, "page_size": 2}
    ).json()

    assert len(body["items"]) == 2
    assert body["pagination"]["total"] == 5


def test_the_default_page_size_is_the_documented_one(
    api_client: TestClient,
) -> None:
    body = api_client.get("/projects/").json()

    assert body["pagination"]["page_size"] == DEFAULT_PAGE_SIZE


def test_a_page_size_above_the_maximum_is_refused(
    api_client: TestClient,
) -> None:
    """
    Refused rather than clamped: a caller who asked for 10 000 and
    silently received 100 would believe it had read the whole registry.
    """

    for path in ("/projects/", "/documents/"):
        response = api_client.get(
            path, params={"page_size": MAX_PAGE_SIZE + 1}
        )

        assert response.status_code == 422


def test_a_zero_or_negative_page_is_refused(
    api_client: TestClient,
) -> None:
    for params in ({"page": 0}, {"page": -1}, {"page_size": 0}):
        assert (
            api_client.get("/projects/", params=params).status_code == 422
        )


# --- Project filtering -----------------------------------------------------


def test_projects_filter_by_delivery_status(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-PLAN", status="planning")
    _project(api_client, code="CP-ENERGIZED", status="energized")

    body = api_client.get(
        "/projects/", params={"status": "energized"}
    ).json()

    assert [item["code"] for item in body["items"]] == ["CP-ENERGIZED"]
    assert body["pagination"]["total"] == 1


def test_projects_filter_by_lifecycle_state(
    api_client: TestClient,
) -> None:
    kept = _project(api_client, code="CP-ACTIVE")
    archived = _project(api_client, code="CP-ARCHIVED")

    api_client.post(f"/projects/{kept['id']}/activate")
    api_client.post(f"/projects/{archived['id']}/activate")
    api_client.post(f"/projects/{archived['id']}/archive")

    body = api_client.get(
        "/projects/", params={"lifecycle_state": "archived"}
    ).json()

    assert [item["code"] for item in body["items"]] == ["CP-ARCHIVED"]


def test_lifecycle_state_and_status_are_independent_filters(
    api_client: TestClient,
) -> None:
    """
    A project can be energized *and* archived - the substation is live
    and the file is closed. Merging the two concepts would make that
    ordinary state unrepresentable.
    """

    project = _project(api_client, code="CP-BOTH", status="energized")

    api_client.post(f"/projects/{project['id']}/activate")
    api_client.post(f"/projects/{project['id']}/archive")

    both = api_client.get(
        "/projects/",
        params={"status": "energized", "lifecycle_state": "archived"},
    ).json()

    assert [item["code"] for item in both["items"]] == ["CP-BOTH"]

    # And each filter alone still finds it.
    assert (
        api_client.get("/projects/", params={"status": "energized"})
        .json()["pagination"]["total"]
        == 1
    )


def test_deleted_projects_stay_hidden_unless_asked_for(
    api_client: TestClient,
) -> None:
    removed = _project(api_client, code="CP-GONE")

    api_client.post(f"/projects/{removed['id']}/activate")
    api_client.post(f"/projects/{removed['id']}/archive")
    api_client.delete(f"/projects/{removed['id']}")

    hidden = api_client.get("/projects/").json()
    assert hidden["pagination"]["total"] == 0

    shown = api_client.get(
        "/projects/", params={"include_deleted": True}
    ).json()
    assert shown["pagination"]["total"] == 1


def test_asking_for_deleted_lifecycle_without_include_deleted_finds_none(
    api_client: TestClient,
) -> None:
    """Visibility is a separate decision from the lifecycle filter, and
    the filter never silently overrides the default."""

    removed = _project(api_client, code="CP-GONE")

    api_client.post(f"/projects/{removed['id']}/activate")
    api_client.post(f"/projects/{removed['id']}/archive")
    api_client.delete(f"/projects/{removed['id']}")

    body = api_client.get(
        "/projects/", params={"lifecycle_state": "deleted"}
    ).json()

    assert body["items"] == []


# --- Project search --------------------------------------------------------


def test_project_search_matches_the_documented_fields(
    api_client: TestClient,
) -> None:
    _project(
        api_client,
        code="CP-GAMMA",
        name="Cabina Gamma",
        customer="Distributore Nazionale",
        location="Bari",
    )
    _project(
        api_client,
        code="CP-NORD",
        name="Cabina Nord",
        customer="Operatore Rete",
        location="Milano",
    )

    for term, expected in [
        ("Gamma", "CP-GAMMA"),  # name
        ("CP-NORD", "CP-NORD"),  # code
        ("Operatore Rete", "CP-NORD"),  # customer
        ("Bari", "CP-GAMMA"),  # location
    ]:
        body = api_client.get("/projects/", params={"search": term}).json()

        assert [item["code"] for item in body["items"]] == [expected], term


def test_project_search_does_not_read_the_description(
    api_client: TestClient,
) -> None:
    """
    Long free prose is deliberately excluded: including it would make a
    search for "CP-01" match every project whose description mentions
    one.
    """

    api_client.post(
        "/projects/",
        json={
            "name": "Cabina Nord",
            "code": "CP-NORD",
            "customer": "Operatore Rete",
            "description": "Sostituisce la vecchia CP-GAMMA.",
        },
    )

    body = api_client.get(
        "/projects/", params={"search": "CP-GAMMA"}
    ).json()

    assert body["items"] == []


def test_search_is_case_insensitive_and_partial(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001", name="Cabina Gamma")

    # "amm" is an infix of "Gamma" - the point of the third term is that
    # a match need not start at a word boundary.
    for term in ("gamma", "GAMMA", "amm"):
        body = api_client.get("/projects/", params={"search": term}).json()

        assert len(body["items"]) == 1, term


def test_search_is_trimmed_but_internal_whitespace_is_significant(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001", name="Cabina Gamma")

    trimmed = api_client.get(
        "/projects/", params={"search": "  Gamma  "}
    ).json()
    assert len(trimmed["items"]) == 1

    # Collapsing internal whitespace would be a normalisation nobody
    # asked for.
    collapsed = api_client.get(
        "/projects/", params={"search": "CabinaGamma"}
    ).json()
    assert collapsed["items"] == []


def test_an_empty_search_is_the_absence_of_one(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001")

    body = api_client.get("/projects/", params={"search": "   "}).json()

    assert body["pagination"]["total"] == 1


def test_a_search_term_cannot_inject_a_wildcard(
    api_client: TestClient,
) -> None:
    """``%`` is data, not a pattern: searching for it must not match
    everything."""

    _project(api_client, code="CP-001", name="Cabina Gamma")
    _project(api_client, code="CP-002", name="Cabina 100% carico")

    body = api_client.get("/projects/", params={"search": "100%"}).json()

    assert [item["code"] for item in body["items"]] == ["CP-002"]


def test_a_search_term_cannot_inject_sql(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-001")

    body = api_client.get(
        "/projects/", params={"search": "'; DROP TABLE projects; --"}
    ).json()

    assert body["items"] == []

    # The table is still there.
    assert api_client.get("/projects/").json()["pagination"]["total"] == 1


# --- Document filtering ----------------------------------------------------


def test_documents_filter_by_project(api_client: TestClient) -> None:
    first = _project(api_client, code="CP-001")
    second = _project(api_client, code="CP-002")

    _upload(api_client, filename="a.pdf", project_id=first["id"])
    _upload(api_client, filename="b.pdf", project_id=second["id"])

    body = api_client.get(
        "/documents/", params={"project_id": first["id"]}
    ).json()

    assert [item["filename"] for item in body["items"]] == ["a.pdf"]


def test_documents_filter_by_scope(api_client: TestClient) -> None:
    project = _project(api_client, code="CP-001")

    _upload(api_client, filename="owned.pdf", project_id=project["id"])
    _upload(api_client, filename="library.pdf")

    body = api_client.get(
        "/documents/", params={"scope": "canonical_library"}
    ).json()

    assert [item["filename"] for item in body["items"]] == ["library.pdf"]


def test_documents_filter_by_format(api_client: TestClient) -> None:
    _upload(api_client, filename="schema.pdf")
    _upload(
        api_client,
        filename="photo.png",
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 40,
        mime_type="image/png",
    )

    body = api_client.get(
        "/documents/", params={"file_format": "image"}
    ).json()

    assert [item["filename"] for item in body["items"]] == ["photo.png"]


def test_document_search_matches_filename_and_project_name(
    api_client: TestClient,
) -> None:
    project = _project(api_client, code="CP-001", name="Cabina Gamma")

    _upload(api_client, filename="elenco-cavi.pdf", project_id=project["id"])
    _upload(api_client, filename="altro.pdf")

    by_filename = api_client.get(
        "/documents/", params={"search": "cavi"}
    ).json()
    assert [item["filename"] for item in by_filename["items"]] == [
        "elenco-cavi.pdf"
    ]

    by_project = api_client.get(
        "/documents/", params={"search": "Gamma"}
    ).json()
    assert [item["filename"] for item in by_project["items"]] == [
        "elenco-cavi.pdf"
    ]


def test_document_filters_combine_as_and(api_client: TestClient) -> None:
    project = _project(api_client, code="CP-001")

    _upload(api_client, filename="cavi.pdf", project_id=project["id"])
    _upload(api_client, filename="cavi-library.pdf")

    body = api_client.get(
        "/documents/",
        params={"project_id": project["id"], "search": "cavi"},
    ).json()

    assert [item["filename"] for item in body["items"]] == ["cavi.pdf"]


# --- Sorting ---------------------------------------------------------------


def test_projects_sort_by_a_governed_field_in_both_directions(
    api_client: TestClient,
) -> None:
    _project(api_client, code="CP-B", name="Beta")
    _project(api_client, code="CP-A", name="Alpha")
    _project(api_client, code="CP-C", name="Gamma")

    ascending = api_client.get(
        "/projects/", params={"sort_by": "name", "direction": "asc"}
    ).json()
    assert [item["name"] for item in ascending["items"]] == [
        "Alpha",
        "Beta",
        "Gamma",
    ]

    descending = api_client.get(
        "/projects/", params={"sort_by": "name", "direction": "desc"}
    ).json()
    assert [item["name"] for item in descending["items"]] == [
        "Gamma",
        "Beta",
        "Alpha",
    ]


def test_documents_sort_by_filename(api_client: TestClient) -> None:
    _upload(api_client, filename="c.pdf")
    _upload(api_client, filename="a.pdf")
    _upload(api_client, filename="b.pdf")

    body = api_client.get(
        "/documents/",
        params={"sort_by": "filename", "direction": "asc"},
    ).json()

    assert [item["filename"] for item in body["items"]] == [
        "a.pdf",
        "b.pdf",
        "c.pdf",
    ]


def test_sorting_is_deterministic_when_the_key_ties(
    api_client: TestClient,
) -> None:
    """
    Every project below has the same name, so the sort key is useless.
    Without a tie-breaker, paging over it could show one row twice and
    skip another; `id` breaks the tie.
    """

    for index in range(6):
        _project(api_client, code=f"CP-{index:03d}", name="Identica")

    first = api_client.get(
        "/projects/", params={"sort_by": "name", "direction": "asc"}
    ).json()
    second = api_client.get(
        "/projects/", params={"sort_by": "name", "direction": "asc"}
    ).json()

    assert [item["code"] for item in first["items"]] == [
        item["code"] for item in second["items"]
    ]


def test_an_unsupported_sort_field_is_refused(
    api_client: TestClient,
) -> None:
    """The vocabulary is closed: a column name never travels."""

    for path, field in [
        ("/projects/", "password"),
        ("/projects/", "id; DROP TABLE projects"),
        ("/documents/", "file_path"),
    ]:
        response = api_client.get(path, params={"sort_by": field})

        assert response.status_code == 422, (path, field)


def test_an_unsupported_sort_direction_is_refused(
    api_client: TestClient,
) -> None:
    assert (
        api_client.get(
            "/projects/", params={"direction": "sideways"}
        ).status_code
        == 422
    )


def test_an_unsupported_filter_value_is_refused(
    api_client: TestClient,
) -> None:
    for path, params in [
        ("/projects/", {"status": "not_a_status"}),
        ("/projects/", {"lifecycle_state": "not_a_state"}),
        ("/documents/", {"scope": "not_a_scope"}),
        ("/documents/", {"file_format": "not_a_format"}),
    ]:
        assert api_client.get(path, params=params).status_code == 422
