"""
OpenAPI completeness for the hardened endpoints (Milestone 30.1.3).

An endpoint that works but cannot be described is an endpoint no client
can be generated for and no reviewer can check. These tests assert the
document actually says what the API does.
"""

from __future__ import annotations

import pytest

from app.main import app


@pytest.fixture(scope="module")
def schema() -> dict:
    return app.openapi()


def _operation(schema: dict, method: str, path: str) -> dict:
    assert path in schema["paths"], f"{path} is not in the OpenAPI document"

    operations = schema["paths"][path]

    assert method in operations, f"{method.upper()} {path} is not described"

    return operations[method]


def _response_schema_name(operation: dict, status: str = "200") -> str:
    content = operation["responses"][status]["content"]
    reference = content["application/json"]["schema"]["$ref"]

    return reference.split("/")[-1]


def _parameters(operation: dict) -> dict[str, dict]:
    return {
        parameter["name"]: parameter
        for parameter in operation.get("parameters", [])
    }


# --- The endpoints exist and are described --------------------------------


def test_every_hardened_endpoint_is_in_the_document(schema: dict) -> None:
    for method, path in [
        ("get", "/documents/"),
        ("post", "/documents/upload"),
        ("get", "/documents/{document_id}"),
        ("get", "/documents/{document_id}/content"),
        ("get", "/projects/"),
    ]:
        _operation(schema, method, path)


def test_the_document_list_declares_its_response_model(
    schema: dict,
) -> None:
    """It declared none at all before this milestone, so its rows were
    whatever FastAPI could serialise off an ORM object."""

    operation = _operation(schema, "get", "/documents/")

    assert _response_schema_name(operation) == "DocumentListResponse"


def test_the_upload_declares_its_response_model(schema: dict) -> None:
    operation = _operation(schema, "post", "/documents/upload")

    assert _response_schema_name(operation) == "DocumentUploadResponse"


def test_the_upload_declares_its_multipart_request(schema: dict) -> None:
    operation = _operation(schema, "post", "/documents/upload")

    content = operation["requestBody"]["content"]

    assert "multipart/form-data" in content

    body = content["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
    properties = schema["components"]["schemas"][body]["properties"]

    assert set(properties) >= {"file", "project_id", "scope"}


def test_the_detail_endpoint_declares_its_response_model(
    schema: dict,
) -> None:
    operation = _operation(schema, "get", "/documents/{document_id}")

    assert _response_schema_name(operation) == "DocumentDetailRead"


def test_the_download_declares_a_binary_response(schema: dict) -> None:
    operation = _operation(schema, "get", "/documents/{document_id}/content")

    content = operation["responses"]["200"]["content"]

    assert "application/octet-stream" in content
    assert content["application/octet-stream"]["schema"]["format"] == (
        "binary"
    )


def test_the_download_documents_its_failure_statuses(schema: dict) -> None:
    operation = _operation(schema, "get", "/documents/{document_id}/content")

    assert "404" in operation["responses"]
    assert "500" in operation["responses"]


def test_the_project_list_declares_its_response_model(
    schema: dict,
) -> None:
    operation = _operation(schema, "get", "/projects/")

    assert _response_schema_name(operation) == "ProjectListResponse"


# --- Pagination, filters and sorting are described ------------------------


@pytest.mark.parametrize("path", ["/documents/", "/projects/"])
def test_pagination_parameters_are_described(
    schema: dict, path: str
) -> None:
    parameters = _parameters(_operation(schema, "get", path))

    assert "page" in parameters
    assert "page_size" in parameters

    # The maximum is in the document, not only in the code.
    assert parameters["page_size"]["schema"]["maximum"] == 100
    assert parameters["page_size"]["schema"]["minimum"] == 1


@pytest.mark.parametrize("path", ["/documents/", "/projects/"])
def test_sorting_parameters_are_described_as_closed_enums(
    schema: dict, path: str
) -> None:
    parameters = _parameters(_operation(schema, "get", path))

    for name in ("sort_by", "direction"):
        assert name in parameters, (path, name)

        declared = parameters[name]["schema"]
        reference = declared.get("$ref") or declared.get("allOf", [{}])[0].get(
            "$ref"
        )

        assert reference is not None, (path, name)

        enum_name = reference.split("/")[-1]

        assert "enum" in schema["components"]["schemas"][enum_name], (
            path,
            name,
        )


def test_document_filters_are_described(schema: dict) -> None:
    parameters = _parameters(_operation(schema, "get", "/documents/"))

    assert set(parameters) >= {
        "project_id",
        "scope",
        "file_format",
        "category",
        "search",
    }


def test_project_filters_are_described(schema: dict) -> None:
    parameters = _parameters(_operation(schema, "get", "/projects/"))

    assert set(parameters) >= {
        "status",
        "lifecycle_state",
        "search",
        "include_deleted",
    }


def test_the_search_parameter_documents_its_matching_rule(
    schema: dict,
) -> None:
    """Deterministic behaviour that is not written down is not a
    contract."""

    for path in ("/documents/", "/projects/"):
        parameters = _parameters(_operation(schema, "get", path))
        description = parameters["search"]["description"].lower()

        assert "case-insensitive" in description
        assert "partial" in description
        assert "trimmed" in description


# --- No storage detail is in the document ---------------------------------


def test_no_public_document_schema_declares_a_storage_field(
    schema: dict,
) -> None:
    for name in (
        "DocumentSummaryRead",
        "DocumentDetailRead",
        "DocumentListResponse",
        "DocumentUploadResponse",
    ):
        properties = schema["components"]["schemas"][name].get(
            "properties", {}
        )

        for field in properties:
            assert "path" not in field.lower(), (name, field)
            assert "storage" not in field.lower(), (name, field)


def test_no_schema_anywhere_declares_a_storage_property(
    schema: dict,
) -> None:
    """
    Checked across **every** component, not only the document ones: a
    storage field could reappear on an ingestion snapshot or a future
    schema just as easily.

    Property names, not free prose - the schemas' own descriptions
    discuss ``file_path`` precisely because it was removed, and a test
    that banned the word would forbid explaining the decision.
    """

    offenders = []

    for name, component in schema["components"]["schemas"].items():
        for field in component.get("properties", {}):
            lowered = field.lower()

            if "file_path" in lowered or "storage_reference" in lowered:
                offenders.append(f"{name}.{field}")

    assert offenders == []


def test_no_example_or_default_leaks_the_storage_root(
    schema: dict,
) -> None:
    """A description is prose; an example is data, and an example
    carrying a real path would be a leak."""

    import json

    def walk(node, key_path: str = "") -> list[str]:
        found: list[str] = []

        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"example", "examples", "default", "const"}:
                    rendered = json.dumps(value).lower()

                    if "/storage/" in rendered or "\\storage\\" in rendered:
                        found.append(f"{key_path}.{key}")

                found.extend(walk(value, f"{key_path}.{key}"))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                found.extend(walk(value, f"{key_path}[{index}]"))

        return found

    assert walk(schema) == []


# --- Project status and lifecycle stay distinct ---------------------------


def test_project_status_and_lifecycle_state_are_separate_schemas(
    schema: dict,
) -> None:
    """A project can be energized and archived at once; one enum could
    not express that."""

    statuses = schema["components"]["schemas"]["ProjectStatus"]["enum"]
    lifecycle = schema["components"]["schemas"]["ProjectLifecycleState"][
        "enum"
    ]

    assert set(statuses) == {
        "planning",
        "engineering",
        "construction",
        "commissioning",
        "energized",
        "closed",
    }
    assert set(lifecycle) == {"draft", "active", "archived", "deleted"}
    assert not set(statuses) & set(lifecycle)
