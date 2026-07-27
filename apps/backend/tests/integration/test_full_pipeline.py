"""
End-to-end proof that the full governed knowledge pipeline reaches a
``Conversation`` (inside an ``EngineeringSession``) whose turn
references a structured, traceable ``EngineeringResponse`` (EPIC 4-5,
Milestones 13-20):

    ProposedClaim -> approval -> CanonicalFact -> GraphOperationBatch ->
    GraphExecution -> Project Knowledge Graph -> Graph Query ->
    Structured Retrieval Result -> Context Builder ContextPackage ->
    Prompt Builder PromptPackage -> neutral LLMRequest ->
    AnthropicPreparedRequest -> mocked Anthropic invocation ->
    LLMResponseEnvelope -> EngineeringResponse -> EngineeringSession ->
    Conversation -> ConversationTurn

Every earlier stage already has its own dedicated test suite (domain,
service, and API tests per bounded context); this file exists purely
to prove the stages compose into one working chain through the real
API, not to re-test any single stage's internal behavior. **No real
network I/O occurs anywhere in this test** - the final stage
monkeypatches the Anthropic client factory with a fake, in-memory SDK
client (never a live call), the same technique
``tests/api/test_llm_invocation_api.py`` uses on its own.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from tests.infrastructure._anthropic_test_support import make_message

import io

from fastapi.testclient import TestClient


def test_full_pipeline_reaches_a_structured_retrieval_result(
    api_client: TestClient, monkeypatch
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

    # 10. Context Builder - the same ranked, explainable candidates,
    # assembled into a bounded, provenance-aware ContextPackage. Context
    # Builder never calls Structured Retrieval itself; it consumes
    # exactly the KnowledgeCandidateCollection the prior call returned.
    context_response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={"candidates": result["candidates"]},
    )
    assert context_response.status_code == 200
    context_result = context_response.json()

    package = context_result["package"]
    assert package["project_id"] == project["id"]
    assert len(package["selected_candidates"]) == 1
    selected = package["selected_candidates"][0]
    assert selected["candidate_id"] == candidate["candidate_id"]
    assert selected["score"]["total"] == candidate["score"]["total"]
    assert selected["graph_execution_ids"] == [execution["id"]]

    assert package["coverage"]["overall_completeness"] == 1.0
    assert package["budget"]["exceeded"] is False
    assert package["warnings"] == []
    assert package["metadata"]["context_builder_version"]

    # Deterministic: the same collection always assembles into the same
    # ContextPackage.
    repeat_context_response = api_client.post(
        f"/projects/{project['id']}/context-builder/build",
        json={"candidates": result["candidates"]},
    )
    repeat_selected = repeat_context_response.json()["package"][
        "selected_candidates"
    ][0]
    assert repeat_selected["candidate_id"] == selected["candidate_id"]

    # 11. Prompt Builder - the same ContextPackage, composed into a
    # bounded, deterministic, provider-independent PromptPackage. Prompt
    # Builder never calls Context Builder itself; it consumes exactly
    # the ContextPackage the prior call returned.
    prompt_response = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build",
        json={"context_package": package},
    )
    assert prompt_response.status_code == 200
    prompt_result = prompt_response.json()

    prompt_package = prompt_result["package"]
    assert prompt_package["project_id"] == project["id"]
    assert len(prompt_package["sections"]) == 9
    assert prompt_package["retrieved_knowledge"]["enabled"] is True
    reference_ids = [r["candidate_id"] for r in prompt_package["references"]]
    assert selected["candidate_id"] in reference_ids
    assert len(prompt_package["constraints"]) == 5
    assert len(prompt_package["instructions"]) == 3
    assert prompt_result["validation"]["valid"] is True

    # Deterministic: the same ContextPackage always composes into the
    # same PromptPackage sections.
    repeat_prompt_response = api_client.post(
        f"/projects/{project['id']}/prompt-builder/build",
        json={"context_package": package},
    )
    assert (
        repeat_prompt_response.json()["package"]["sections"]
        == prompt_package["sections"]
    )

    # 12. LLM Provider Abstraction Layer - the same PromptPackage,
    # translated into a provider-neutral LLMRequest and then into a
    # local AnthropicPreparedRequest. Never calls Anthropic, never
    # sends anything over the network - only pure request preparation.
    llm_response = api_client.post(
        f"/projects/{project['id']}/llm/prepare-request",
        json={
            "prompt_package": prompt_package,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )
    assert llm_response.status_code == 200
    llm_result = llm_response.json()

    assert llm_result["request"]["project_id"] == project["id"]
    assert llm_result["request"]["model_selection"]["model_identifier"] == (
        "model-under-test"
    )
    assert llm_result["prepared_request"]["provider_id"] == "anthropic"
    assert llm_result["prepared_request"]["model"] == "model-under-test"
    assert llm_result["capability_validation"]["valid"] is True

    reference_ids = [r["candidate_id"] for r in llm_result["request"]["references"]]
    assert selected["candidate_id"] in reference_ids

    # 13. LLM Invocation Runtime - the same PromptPackage, actually
    # invoked through the full runtime (validation, mapping, adapter
    # resolution, retry/timeout policy, response normalization) with a
    # mocked Anthropic client standing in for the real SDK - never a
    # live network call.
    monkeypatch.setenv("LLM_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-e2e-test-key")

    class _FakeMessagesResource:
        def __init__(self) -> None:
            self.create = AsyncMock(
                side_effect=lambda **kwargs: make_message(
                    text="End-to-end deterministic answer.",
                    model="model-under-test",
                )
            )

    class _FakeAnthropicClient:
        def __init__(self) -> None:
            self.messages = _FakeMessagesResource()

    import app.routers.llm_provider as llm_provider_router_module

    monkeypatch.setattr(
        llm_provider_router_module,
        "build_anthropic_client",
        lambda **_kwargs: _FakeAnthropicClient(),
    )

    invoke_response = api_client.post(
        f"/projects/{project['id']}/llm/invoke",
        json={
            "prompt_package": prompt_package,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )
    assert invoke_response.status_code == 200
    invocation_result = invoke_response.json()

    assert invocation_result["status"] == "succeeded"
    assert invocation_result["terminal_error"] is None
    envelope = invocation_result["envelope"]
    assert envelope["provider_id"] == "anthropic"
    assert envelope["configured_model_identifier"] == "model-under-test"
    assert envelope["content"][0]["text"] == "End-to-end deterministic answer."
    assert envelope["finish_reason"] == "completed"
    assert len(envelope["attempts"]) == 1
    assert invocation_result["validation"]["valid"] is True

    # 14. Engineering Response - the same LLMResponseEnvelope, normalized
    # into a structured, traceable EngineeringResponse. Engineering
    # Response never calls the LLM Invocation Runtime itself; it
    # consumes exactly the envelope the prior call returned, alongside
    # the ContextPackage/PromptPackage already built above. No AI
    # invocation happens in this stage.
    engineering_response_response = api_client.post(
        f"/projects/{project['id']}/engineering-response/build",
        json={
            "context_package": package,
            "prompt_package": prompt_package,
            "llm_response_envelope": envelope,
        },
    )
    assert engineering_response_response.status_code == 200
    engineering_response_result = engineering_response_response.json()

    engineering_response = engineering_response_result["response"]
    assert engineering_response["project_id"] == project["id"]
    assert engineering_response["status"] == "complete"
    assert len(engineering_response["sections"]) == 9
    assert engineering_response["direct_answer"]["body"] == [
        "End-to-end deterministic answer."
    ]
    assert engineering_response["direct_answer"]["enabled"] is True
    assert engineering_response["overall_uncertainty"] in {
        "low",
        "medium",
        "high",
        "unknown",
    }
    assert engineering_response_result["validation"]["valid"] is True

    # Deterministic: the same envelope always builds the same
    # EngineeringResponse.
    repeat_engineering_response = api_client.post(
        f"/projects/{project['id']}/engineering-response/build",
        json={
            "context_package": package,
            "prompt_package": prompt_package,
            "llm_response_envelope": envelope,
        },
    )
    assert (
        repeat_engineering_response.json()["response"]["sections"]
        == engineering_response["sections"]
    )

    # 15. Engineering Session - the root aggregate that will own every
    # future conversation, tool, and agent. Creating a session, moving
    # it to ACTIVE, and appending the EngineeringResponse produced above
    # never invokes an AI provider or Context Builder/Prompt Builder/the
    # LLM Invocation Runtime itself - pure, in-memory domain operations.
    session_response = api_client.post(
        f"/projects/{project['id']}/engineering-session",
        json={"title": "End-to-end session"},
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["session"]["state"]["status"] == "created"
    assert session_body["validation"]["valid"] is True

    activate_response = api_client.post(
        f"/projects/{project['id']}/engineering-session/change-state",
        json={
            "session": session_body["session"],
            "target_status": "active",
        },
    )
    assert activate_response.status_code == 200
    active_session = activate_response.json()["session"]
    assert active_session["state"]["status"] == "active"

    append_session_response = api_client.post(
        f"/projects/{project['id']}/engineering-session/append-response",
        json={
            "session": active_session,
            "response": engineering_response,
        },
    )
    assert append_session_response.status_code == 200
    append_session_body = append_session_response.json()
    assert append_session_body["validation"]["valid"] is True

    final_session = append_session_body["session"]
    assert final_session["statistics"]["response_count"] == 1
    assert final_session["engineering_responses"][0]["direct_answer"]["body"] == [
        "End-to-end deterministic answer."
    ]

    # 16. Conversation - structured engineering dialogue belonging to
    # the EngineeringSession above (referenced by session_id, never
    # embedded). Starting a turn, adding a user message, attaching the
    # same EngineeringResponse, adding an assistant message, and
    # completing the turn never invokes an AI provider or any earlier
    # pipeline stage - pure, in-memory domain operations.
    conversation_response = api_client.post(
        f"/projects/{project['id']}/conversation",
        json={"session_id": final_session["session_id"]},
    )
    assert conversation_response.status_code == 200
    conversation_body = conversation_response.json()
    assert conversation_body["conversation"]["status"] == "active"
    assert conversation_body["validation"]["valid"] is True

    conversation = conversation_body["conversation"]
    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/start-turn",
        json={"conversation": conversation},
    ).json()["conversation"]
    assert len(conversation["turns"]) == 1

    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/add-message",
        json={
            "conversation": conversation,
            "role": "user",
            "text": "What does cable C-295 feed?",
        },
    ).json()["conversation"]

    attach_response_body = api_client.post(
        f"/projects/{project['id']}/conversation/attach-response",
        json={
            "conversation": conversation,
            "response": engineering_response,
        },
    )
    assert attach_response_body.status_code == 200
    attach_body = attach_response_body.json()
    assert attach_body["validation"]["valid"] is True
    conversation = attach_body["conversation"]

    conversation = api_client.post(
        f"/projects/{project['id']}/conversation/add-message",
        json={
            "conversation": conversation,
            "role": "assistant",
            "text": "It feeds TR2.",
        },
    ).json()["conversation"]

    complete_turn_body = api_client.post(
        f"/projects/{project['id']}/conversation/complete-turn",
        json={"conversation": conversation},
    )
    assert complete_turn_body.status_code == 200
    final_conversation_body = complete_turn_body.json()
    assert final_conversation_body["validation"]["valid"] is True

    final_conversation = final_conversation_body["conversation"]
    assert final_conversation["statistics"]["message_count"] == 2
    assert final_conversation["statistics"]["engineering_response_count"] == 1
    final_turn = final_conversation["turns"][0]
    assert final_turn["status"] == "completed"
    assert final_turn["engineering_responses"][0]["direct_answer"]["body"] == [
        "End-to-end deterministic answer."
    ]
