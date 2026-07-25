"""
End-to-end proof that the full governed knowledge pipeline reaches a
Structured Retrieval result (EPIC 4, Milestone 13):

    ProposedClaim -> approval -> CanonicalFact -> GraphOperationBatch ->
    GraphExecution -> Project Knowledge Graph -> Graph Query ->
    Structured Retrieval Result

Every earlier stage already has its own dedicated test suite (domain,
service, and API tests per bounded context); this file exists purely
to prove the stages compose into one working chain through the real
API, not to re-test any single stage's internal behavior.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient


def test_full_pipeline_reaches_a_structured_retrieval_result(
    api_client: TestClient,
) -> None:
    # 1. Project
    project = api_client.post(
        "/projects/",
        json={
            "name": "Alpha Substation",
            "code": "E2E-001",
            "customer": "Acme Utilities",
        },
    ).json()

    # 2. Document
    document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "functional-schematic.pdf",
                io.BytesIO(b"%PDF-1.4"),
                "application/pdf",
            )
        },
        data={"scope": "project", "project_id": str(project["id"])},
    ).json()

    # 3. Engineering Index
    cable_entry = api_client.post(
        "/engineering-index/entries",
        json={
            "document_id": document["id"],
            "kind": "equipment",
            "identifier": "C-295",
        },
    ).json()

    # 4. Proposed Claims -> Review Workflow -> approval
    claim = api_client.post(
        "/proposed-claims",
        json={
            "claim_type": "relationship",
            "subject": "Cable 295",
            "predicate": "feeds",
            "object": "TR2",
            "engineering_index_entry_ids": [cable_entry["id"]],
        },
    ).json()
    review_candidate = api_client.post(
        "/review-candidates",
        json={"proposed_claim_id": claim["id"]},
    ).json()
    approved = api_client.post(
        f"/review-candidates/{review_candidate['id']}/approve",
        json={"reviewed_by": "engineer.smith"},
    ).json()
    assert approved["status"] == "approved"

    # 5. Canonicalization -> CanonicalFact
    fact_response = api_client.post(
        "/canonical-facts",
        json={"review_candidate_id": approved["id"]},
    )
    assert fact_response.status_code == 200
    fact = fact_response.json()["fact"]
    assert fact["claim_type"] == "relationship"

    # 6. Graph Builder -> GraphOperationBatch
    batch = api_client.post(
        f"/graph-builder/build/project/{project['id']}"
    ).json()
    assert batch["project_id"] == project["id"]

    # 7. Graph Execution -> Project Knowledge Graph state
    execution_response = api_client.post(
        f"/graph-executions/batches/{batch['id']}"
    )
    assert execution_response.status_code == 200
    execution = execution_response.json()["execution"]
    assert execution["status"] == "succeeded"

    # 8. Graph Query - the persisted state is readable through the
    # deterministic read model.
    graph_query_response = api_client.get(
        f"/projects/{project['id']}/graph/entities"
    )
    assert graph_query_response.status_code == 200
    assert len(graph_query_response.json()) == 2

    # 9. Structured Retrieval - the same governed state, reached
    # through structured criteria, with score, reasons, matches, and
    # honest provenance (this project's own GraphExecution id).
    retrieval_response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_lookup",
            "canonical_entity_id": "CABLE:C-295",
            "include_neighborhood": True,
            "neighborhood_depth": 1,
        },
    )
    assert retrieval_response.status_code == 200
    result = retrieval_response.json()

    assert result["candidates"]["returned_count"] == 1
    candidate = result["candidates"]["candidates"][0]

    assert candidate["primary_reference"]["canonical_id"] == "C-295"
    assert candidate["primary_reference"]["entity_type"] == "CABLE"
    assert candidate["score"]["total"] == 100.0
    assert candidate["score"]["components"][0]["category"] == (
        "exact_canonical_id_match"
    )
    assert candidate["reasons"]
    assert candidate["matches"] == [
        {
            "criterion_kind": "canonical_entity_id",
            "criterion_value": "CABLE:C-295",
        }
    ]
    assert candidate["graph_execution_ids"] == [execution["id"]]
    assert any(
        neighbor["canonical_id"] == "TR-02"
        for neighbor in candidate["related_entities"]
    )

    assert result["metadata"]["neighborhood_enrichment_applied"] is True
    assert result["metadata"]["candidate_count_before_dedup"] >= 1
    assert result["plan"]["required_operations"] == ["entity_by_id"]

    # Deterministic: the same request against the same graph state
    # always produces the same candidate identifiers and scores.
    repeat_response = api_client.post(
        f"/projects/{project['id']}/structured-retrieval/search",
        json={
            "mode": "entity_lookup",
            "canonical_entity_id": "CABLE:C-295",
            "include_neighborhood": True,
            "neighborhood_depth": 1,
        },
    )
    repeat_candidate = repeat_response.json()["candidates"]["candidates"][0]
    assert repeat_candidate["candidate_id"] == candidate["candidate_id"]
    assert repeat_candidate["score"]["total"] == candidate["score"]["total"]
