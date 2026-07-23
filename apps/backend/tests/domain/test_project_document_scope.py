from __future__ import annotations

from app.domain.project.project_document_scope import DocumentScope


def test_document_scope_has_project_and_canonical_library_members() -> None:
    assert DocumentScope.PROJECT.value == "project"
    assert DocumentScope.CANONICAL_LIBRARY.value == "canonical_library"


def test_document_scope_is_a_string_enum() -> None:
    assert DocumentScope.PROJECT == "project"
