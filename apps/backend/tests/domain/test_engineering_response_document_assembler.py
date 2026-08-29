"""
Domain tests for the ``DETERMINISTIC_RETRIEVAL`` Engineering Response path
(Milestone 23B.1): an ``EngineeringResponse`` built from a document lookup,
with no provider, no prompt and no LLM anywhere.

Pure and fast: no I/O, no database, no AI provider.
"""

from __future__ import annotations

import pytest

from app.domain.engineering_index.document_retrieval_factory import (
    DocumentRetrievalRequestFactory,
)
from app.domain.engineering_index.document_retrieval_ranking import (
    build_document_retrieval_result,
)
from app.domain.engineering_response.engineering_response_composition import (
    ENGINEERING_RESPONSE_SECTION_ORDER,
)
from app.domain.engineering_response.engineering_response_document_assembler import (  # noqa: E501
    assemble_document_lookup_response,
)
from app.domain.engineering_response.engineering_response_document_factory import (  # noqa: E501
    EngineeringResponseDocumentLookupBuildRequestFactory,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    BlankRequestCorrelationIdError,
    InvalidProjectIdError,
    ProjectIdMismatchError,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseOrigin,
    EngineeringResponseStatus,
    EngineeringSectionType,
    EngineeringUncertaintyLevel,
    EngineeringWarningCategory,
)
from tests.domain._document_retrieval_support import NOW, entry, metadata


def _retrieval_result(
    *, identifiers=("T2",), entries=None, document_metadata=None, limit=20
):
    request = DocumentRetrievalRequestFactory.create(
        project_id=1, identifiers=identifiers, limit=limit
    )

    return build_document_retrieval_result(
        request=request,
        entries=tuple(entries if entries is not None else (entry(),)),
        document_metadata=tuple(
            document_metadata
            if document_metadata is not None
            else (metadata(),)
        ),
        retrieved_at=NOW,
    )


def _build(retrieval_result=None, *, project_id=1, correlation_id="corr-1"):
    request = EngineeringResponseDocumentLookupBuildRequestFactory.create(
        project_id=project_id,
        retrieval_result=(
            retrieval_result
            if retrieval_result is not None
            else _retrieval_result()
        ),
        request_correlation_id=correlation_id,
    )

    return assemble_document_lookup_response(request, now=NOW)


# --- Origin honesty -------------------------------------------------------


def test_the_response_declares_a_deterministic_retrieval_origin() -> None:
    result = _build()

    assert result.response.origin is (
        EngineeringResponseOrigin.DETERMINISTIC_RETRIEVAL
    )


def test_no_provider_model_or_runtime_is_named() -> None:
    """The central honesty guarantee of this milestone: a response nothing
    generated must not look like one a model generated."""

    response = _build().response

    assert response.metadata.provider_id is None
    assert response.metadata.configured_model_identifier is None
    assert response.metadata.returned_model_identifier is None
    assert response.version.runtime_version is None
    assert response.metadata.prompt_package_version is None
    assert response.metadata.prompt_builder_version is None
    assert response.metadata.context_assembly_version is None


def test_the_deterministic_capability_versions_are_recorded() -> None:
    response = _build().response

    assert response.version.document_retrieval_version is not None
    assert response.version.document_relevance_policy_version is not None


def test_the_correlation_id_is_carried_through() -> None:
    response = _build(correlation_id="engine:conv-1:turn-1").response

    assert response.metadata.request_correlation_id == "engine:conv-1:turn-1"


# --- The response is structurally valid, by the same rules ----------------


def test_the_built_response_passes_the_shared_structural_validation() -> None:
    result = _build()

    assert result.validation.valid is True
    assert result.validation.errors == ()


def test_the_section_shape_is_the_same_nine_sections_in_canonical_order() -> (
    None
):
    response = _build().response

    assert tuple(
        section.section_type for section in response.sections
    ) == ENGINEERING_RESPONSE_SECTION_ORDER


def test_statistics_are_consistent_with_the_assembled_content() -> None:
    response = _build().response

    assert response.statistics.section_count == len(response.sections)
    assert response.statistics.document_reference_count == len(
        response.document_references
    )
    assert response.statistics.warning_count == len(response.warnings)


# --- Document references --------------------------------------------------


def test_the_retrieved_documents_are_carried_as_document_references() -> None:
    response = _build().response

    assert len(response.document_references) == 1
    reference = response.document_references[0]
    assert reference.document_id == 10
    assert reference.title == "montante-T2-schema-funzionale.pdf"
    assert reference.revision == "02"
    assert reference.page_references == (3,)


def test_graph_evidence_references_stay_empty() -> None:
    """This workflow retrieves documents, not graph facts. Reporting
    documents as graph evidence would conflate two different kinds of
    provenance."""

    response = _build().response

    assert response.references == ()
    assert response.statistics.reference_count == 0


def test_the_direct_answer_lists_each_document_with_existing_metadata() -> None:
    response = _build().response

    body = response.direct_answer.body
    assert len(body) == 1
    assert "document_id=10" in body[0]
    assert "title=montante-T2-schema-funzionale.pdf" in body[0]
    assert "type=pdf" in body[0]
    assert "revision=02" in body[0]
    assert "pages=3" in body[0]


def test_the_references_section_lists_each_recorded_mention() -> None:
    response = _build(
        _retrieval_result(
            entries=(
                entry(entry_id=1, page=3),
                entry(entry_id=2, page=8),
            )
        )
    ).response

    references_section = next(
        section
        for section in response.sections
        if section.section_type is EngineeringSectionType.REFERENCES
    )
    assert len(references_section.body) == 2
    assert references_section.enabled is True


def test_no_section_is_populated_by_guessing() -> None:
    """Summary, technical explanation, assumptions and next actions have
    no honest deterministic source, so they stay empty - exactly as they
    do on the LLM path."""

    response = _build().response
    guessable = {
        EngineeringSectionType.SUMMARY,
        EngineeringSectionType.TECHNICAL_EXPLANATION,
        EngineeringSectionType.ASSUMPTIONS,
        EngineeringSectionType.NEXT_ACTIONS,
    }

    for section in response.sections:
        if section.section_type in guessable:
            assert section.body == ()
            assert section.enabled is False


def test_the_limitations_section_states_that_contents_were_not_read() -> None:
    response = _build().response

    limitations = next(
        section
        for section in response.sections
        if section.section_type is EngineeringSectionType.LIMITATIONS
    )
    assert any("does not read" in line for line in limitations.body)


# --- Status and uncertainty -----------------------------------------------


def test_a_fully_resolved_lookup_is_complete_with_low_uncertainty() -> None:
    response = _build().response

    assert response.status is EngineeringResponseStatus.COMPLETE
    assert response.overall_uncertainty is EngineeringUncertaintyLevel.LOW


def test_no_matching_document_is_an_empty_response_not_a_failure() -> None:
    response = _build(
        _retrieval_result(identifiers=("99Z",), entries=(), document_metadata=())
    ).response

    assert response.status is EngineeringResponseStatus.EMPTY
    assert response.document_references == ()
    assert response.overall_uncertainty is EngineeringUncertaintyLevel.HIGH
    assert any(
        warning.category is EngineeringWarningCategory.INSUFFICIENT_EVIDENCE
        for warning in response.warnings
    )


def test_a_truncated_lookup_is_partial_and_says_so() -> None:
    entries = tuple(
        entry(entry_id=index, document_id=index, identifier="T2")
        for index in range(1, 5)
    )
    response = _build(
        _retrieval_result(entries=entries, document_metadata=(), limit=2)
    ).response

    assert response.status is EngineeringResponseStatus.PARTIAL
    assert any(
        warning.category is EngineeringWarningCategory.LIMITED_RESPONSE
        for warning in response.warnings
    )


def test_missing_document_metadata_is_partial_and_warned_about() -> None:
    response = _build(_retrieval_result(document_metadata=())).response

    assert response.status is EngineeringResponseStatus.PARTIAL
    assert any(
        warning.category is EngineeringWarningCategory.PARTIAL_CONTEXT
        for warning in response.warnings
    )
    assert response.overall_uncertainty is EngineeringUncertaintyLevel.MEDIUM


# --- Determinism ----------------------------------------------------------


def test_the_same_lookup_and_now_always_produce_the_same_response() -> None:
    retrieval_result = _retrieval_result()

    assert _build(retrieval_result) == _build(retrieval_result)


# --- Factory invariants ---------------------------------------------------


def test_a_non_positive_project_id_is_rejected() -> None:
    with pytest.raises(InvalidProjectIdError):
        _build(project_id=0)


def test_a_project_id_that_disagrees_with_the_lookup_is_rejected() -> None:
    with pytest.raises(ProjectIdMismatchError):
        _build(project_id=2)


def test_a_blank_correlation_id_is_rejected() -> None:
    with pytest.raises(BlankRequestCorrelationIdError):
        _build(correlation_id="   ")
