"""
End-to-end proof that the full governed knowledge pipeline runs a
complete engineering workflow through the Engineering Engine, reaching
an ``EngineeringResponse`` from a deterministically classified
``EngineeringIntent`` (EPIC 4-5, Milestones 13-23A):

    ProposedClaim -> approval -> CanonicalFact -> GraphOperationBatch ->
    GraphExecution -> Project Knowledge Graph -> Graph Query ->
    Structured Retrieval Result -> Context Builder ContextPackage ->
    Prompt Builder PromptPackage -> neutral LLMRequest ->
    AnthropicPreparedRequest -> mocked Anthropic invocation ->
    LLMResponseEnvelope -> EngineeringResponse -> EngineeringSession ->
    Conversation -> ConversationTurn -> WorkingMemory ->
    EngineeringIntent -> document -> deterministic pipeline ->
    semantic statement -> Human Review approval -> governed promotion ->
    Governed Knowledge Graph -> Governed Structured Retrieval ->
    Engineering Engine (workflow selection, plan, execution) ->
    EngineeringResponse

**Two lineages, and the split is the point (EPIC 31.2).** Stages 4-11
still exercise the Canonical Facts projection and the retrieval built on
it, because both are still live API capabilities. The Engineering Engine
no longer reads either: its retrieval comes exclusively from governed
knowledge, so stage 19 promotes a reviewed statement and stage 20 proves
the engine answered from it.

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

import json
from datetime import datetime

from unittest.mock import AsyncMock

from tests._pdf_builder import single_page_pdf
from tests.infrastructure._anthropic_test_support import make_message

import io

from fastapi.testclient import TestClient


def test_full_pipeline_reaches_a_governed_engineering_response(
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
    ).json()["document"]

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

    # 6-9. The Canonical Facts graph lineage - **retired by EPIC 31.4**.
    #
    # These four stages used to stand here: Graph Builder produced a
    # `GraphOperationBatch` from the canonical fact, Graph Execution wrote
    # it into `project_graph_nodes`/`project_graph_relationships`, Graph
    # Query read it back, and legacy Structured Retrieval matched on its
    # property bags. All twenty routes are withdrawn and the seven tables
    # are dropped.
    #
    # What survives above is the part that was always human-authored: the
    # proposed claim, the review candidate, the approval, and the
    # canonical fact. What is gone is the graph-shaped projection computed
    # from them - and, with it, the second queryable engineering knowledge
    # store.
    #
    # The chain from here on is the governed one, and it is the only one.

    for method, path, body in (
        ("post", f"/graph-builder/build/project/{project['id']}", None),
        ("get", f"/projects/{project['id']}/graph/entities", None),
        (
            "post",
            f"/projects/{project['id']}/structured-retrieval/search",
            {"mode": "entity_lookup", "canonical_entity_id": "CABLE:C-295"},
        ),
        (
            "get",
            f"/projects/{project['id']}/knowledge-graph/nodes",
            None,
        ),
    ):
        call = getattr(api_client, method)
        retired = call(path) if body is None else call(path, json=body)

        assert retired.status_code == 404, path

    # 10. Governed Context Assembly - the governed results assembled into
    # a bounded, provenance-aware ContextPackage.
    #
    # Built in-process rather than through an endpoint: EPIC 31.3
    # withdrew `/projects/{id}/context-builder/build`, because a governed
    # context cannot honestly be assembled from a request body -
    # provenance a caller asserts is not provenance. This is the same
    # call the Engineering Engine makes, from retrieval it ran itself.
    from app.schemas.context_builder import ContextPackageRead
    from app.services import context_builder_service

    from tests._governed_context import asset_item, results_for

    governed_results = results_for(
        (
            asset_item(
                "node-c-295",
                "C-295",
                statement_key="statement-c-295",
                project_id=project["id"],
            ),
        ),
        project_id=project["id"],
    )
    context_package = context_builder_service.build_context_package(
        project_id=project["id"],
        results=governed_results,
        now=datetime(2026, 1, 1, 12, 0, 0),
    ).package

    package = json.loads(
        ContextPackageRead.from_domain(context_package).model_dump_json()
    )

    assert package["project_id"] == project["id"]
    assert len(package["selected_items"]) == 1

    selected = package["selected_items"][0]

    # The governed chain, intact on the wire: an item names the governed
    # object, the statement it was promoted from, and the review that
    # authorised it.
    assert selected["node"]["label"] == "C-295"
    assert selected["provenance"]["statement_key"] == "statement-c-295"
    assert selected["provenance"]["review_id"] > 0
    assert selected["provenance"]["reviewer_display_name"]
    assert selected["match"]["strategy"] == "exact_designation"

    # Ambiguity is stated rather than implied by ordering.
    assert selected["origin"]["outcome"] == "unique_match"

    assert package["coverage"]["overall_completeness"] == 1.0
    assert package["budget"]["exceeded"] is False
    assert package["warnings"] == []
    assert package["metadata"]["context_assembly_version"]

    # Deterministic: the same governed results always assemble into the
    # same ContextPackage.
    repeat_package = context_builder_service.build_context_package(
        project_id=project["id"],
        results=governed_results,
        now=datetime(2026, 1, 1, 12, 0, 0),
    ).package

    assert repeat_package == context_package

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
    # Twelve since EPIC 32.1. Every section the prompt vocabulary knows is
    # always present; the ones this prompt does not use are disabled. The
    # two comparison sides are disabled here (Milestone 24.2), and so is
    # derived_reasoning: this is the Prompt Builder API, which composes a
    # prompt from a context package and never reasons.
    assert len(prompt_package["sections"]) == 12
    disabled = {
        section["section_type"]
        for section in prompt_package["sections"]
        if not section["enabled"]
    }
    assert "derived_reasoning" in disabled
    assert prompt_package["retrieved_knowledge"]["enabled"] is True
    # The governed citation survives into the prompt: the item, the
    # statement it came from, and the review that authorised it.
    references = prompt_package["references"]
    assert [r["item_id"] for r in references] == [selected["item_id"]]
    assert references[0]["statement_key"] == "statement-c-295"
    assert references[0]["review_id"] == selected["provenance"]["review_id"]
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

    reference_ids = [
        r["item_id"] for r in llm_result["request"]["references"]
    ]
    assert selected["item_id"] in reference_ids

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

    # 17. Working Memory - deterministically rebuilt from the
    # Conversation and EngineeringSession above; never conversation
    # history, never project knowledge, never AI-edited. No open
    # question exists (the turn above was completed), so the entries
    # here come entirely from the attached EngineeringResponse's own
    # already-computed status/references/warnings - structural facts,
    # never semantic interpretation of message content.
    working_memory_response = api_client.post(
        f"/projects/{project['id']}/working-memory/build",
        json={
            "conversation": final_conversation,
            "engineering_session": final_session,
        },
    )
    assert working_memory_response.status_code == 200
    working_memory_body = working_memory_response.json()
    assert working_memory_body["validation"]["valid"] is True

    working_memory = working_memory_body["working_memory"]
    assert working_memory["working_memory_id"] == (
        f"{final_conversation['conversation_id']}:working-memory"
    )
    entry_types = {e["entry_type"] for e in working_memory["entries"]}
    assert "open_question" not in entry_types
    assert "recent_engineering_response" in entry_types
    assert working_memory["statistics"]["recent_engineering_response_count"] == 1

    # Deterministic: rebuilding from the same Conversation/EngineeringSession
    # always produces the same entries.
    rebuild_response = api_client.post(
        f"/projects/{project['id']}/working-memory/rebuild",
        json={
            "conversation": final_conversation,
            "engineering_session": final_session,
        },
    )
    assert rebuild_response.status_code == 200
    rebuilt_entry_types = [
        e["entry_type"] for e in rebuild_response.json()["working_memory"]["entries"]
    ]
    assert rebuilt_entry_types == [e["entry_type"] for e in working_memory["entries"]]

    # 18. Engineering Request Classification - the same user request
    # that opened the turn above, classified deterministically into a
    # structured EngineeringIntent a future orchestrator could use to
    # select a workflow. No LLM, no embeddings, no semantic model - a
    # fixed rule table over normalized text. Nothing here executes a
    # workflow, retrieves anything, or modifies the Conversation or
    # WorkingMemory built above.
    intent_response = api_client.post(
        f"/projects/{project['id']}/engineering-intents/classify",
        json={
            "engineering_session_id": final_session["session_id"],
            "conversation_id": final_conversation["conversation_id"],
            "turn_id": final_turn["turn_id"],
            "request_text": "What does cable C-295 feed?",
            "working_memory_has_open_question": any(
                e["entry_type"] == "open_question"
                for e in working_memory["entries"]
            ),
            "working_memory_active_response_count": (
                working_memory["statistics"]["recent_engineering_response_count"]
            ),
        },
    )
    assert intent_response.status_code == 200
    intent_body = intent_response.json()
    assert intent_body["validation"]["valid"] is True

    intent = intent_body["intent"]
    assert intent["project_id"] == project["id"]
    assert intent["engineering_intent_id"] == (
        f"{final_conversation['conversation_id']}:{final_turn['turn_id']}:"
        f"{intent['version']['classification_policy_version']}"
    )
    # "What does cable C-295 feed?" carries the interrogative "what" and
    # the domain term "cable" - a knowledge query about project facts.
    assert intent["intent_type"] == "knowledge_query"
    assert intent["evidence"]
    assert intent["statistics"]["matched_rule_count"] == len(intent["evidence"])

    # Deterministic: reclassifying the same request under the same
    # policy version yields the same identity and the same result.
    repeat_intent_response = api_client.post(
        f"/projects/{project['id']}/engineering-intents/classify",
        json={
            "engineering_session_id": final_session["session_id"],
            "conversation_id": final_conversation["conversation_id"],
            "turn_id": final_turn["turn_id"],
            "request_text": "What does cable C-295 feed?",
        },
    )
    repeat_intent = repeat_intent_response.json()["intent"]
    assert repeat_intent["engineering_intent_id"] == (
        intent["engineering_intent_id"]
    )
    assert repeat_intent["intent_type"] == intent["intent_type"]
    assert repeat_intent["evidence"] == intent["evidence"]

    # 19. Governed knowledge - the lineage the Engineering Engine
    # actually reads since EPIC 31.2. A real document, interpreted
    # deterministically, reviewed by a named engineer, and promoted:
    # nothing reaches the engine that an engineer has not approved.
    governed_document = api_client.post(
        "/documents/upload",
        files={
            "file": (
                "trasformatore.pdf",
                io.BytesIO(single_page_pdf("Trasformatore TR1 630 kVA")),
                "application/pdf",
            )
        },
        data={"scope": "project", "project_id": str(project["id"])},
    ).json()["document"]

    api_client.post(
        "/documents/ingestion/jobs", json={"document_id": governed_document["id"]}
    )
    for stage in (
        "canonical-representation",
        "canonical-text",
        "engineering-evidence",
        "engineering-entities",
        "engineering-facts",
        "engineering-semantics",
    ):
        api_client.post(f"/documents/{governed_document['id']}/{stage}")

    statements = api_client.get(
        f"/documents/{governed_document['id']}/engineering-semantics"
    ).json()["statements"]
    assert statements, "the fixture document produced no semantic statement"
    statement_key = statements[0]["statement_key"]

    review_response = api_client.post(
        f"/documents/{governed_document['id']}/engineering-semantics/"
        f"{statement_key}/reviews",
        json={"decision": "approved", "reason": "confirmed_by_source"},
    )
    assert review_response.status_code == 201

    promotion = api_client.post(
        "/knowledge-graph/promotions",
        params={"document_id": governed_document["id"]},
    )
    assert promotion.status_code == 201

    governed_assets = api_client.get(
        "/knowledge-graph/nodes", params={"kind": "engineering_asset"}
    ).json()["items"]
    assert governed_assets, "promotion produced no governed asset"
    governed_asset = governed_assets[0]

    # 20. Engineering Engine - the classified KNOWLEDGE_QUERY intent is
    # coordinated into a complete workflow: selection -> plan ->
    # validation -> execution, reusing Governed Structured Retrieval,
    # Context Builder, Prompt Builder, LLM Runtime, and Engineering
    # Response. The Anthropic client is still the fake one
    # monkeypatched at stage 13, so no live call occurs here either.
    import app.routers.engineering_engine as engine_router_module

    monkeypatch.setattr(
        engine_router_module,
        "build_anthropic_client",
        lambda **_kwargs: _FakeAnthropicClient(),
    )

    engine_response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json={
            "engineering_session_id": final_session["session_id"],
            "conversation_id": final_conversation["conversation_id"],
            "turn_id": final_turn["turn_id"],
            "request_text": "Qual è la potenza nominale del TR1?",
            "engineering_intent_id": intent["engineering_intent_id"],
            "intent_type": intent["intent_type"],
            "retrieval_lexical_terms": [governed_asset["label"]],
            "retrieval_include_neighborhood": True,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )
    assert engine_response.status_code == 200
    engine_body = engine_response.json()

    assert engine_body["status"] == "completed"
    assert engine_body["validation"]["valid"] is True
    assert engine_body["selection"]["workflow_id"] == "knowledge-query"

    # Every planned step ran, in order, and completed.
    assert len(engine_body["plan"]["steps"]) == 10
    assert all(
        step_result["status"] == "completed"
        for step_result in engine_body["execution"]["step_results"]
    )

    # The engine reached a real EngineeringResponse through the whole
    # governed pipeline - and the knowledge it answered from is the
    # governed asset promoted at stage 19, identified by its governed
    # node id rather than by a label.
    engine_engineering_response = engine_body["engineering_response"]
    assert engine_engineering_response is not None
    assert engine_engineering_response["direct_answer"]["body"] == [
        "End-to-end deterministic answer."
    ]
    reference_ids = [
        r["item_id"] for r in engine_engineering_response["references"]
    ]
    assert f"asset:{governed_asset['node_id']}" in reference_ids

    # Aggregate updates are prepared, never applied by the engine.
    assert engine_body["prepared_updates"]["conversation_update"][
        "disposition"
    ] == "prepared"
    assert engine_body["prepared_updates"]["session_update"][
        "disposition"
    ] == "prepared"

    # Planning is deterministic even though runtime output need not be.
    repeat_engine_response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json={
            "engineering_session_id": final_session["session_id"],
            "conversation_id": final_conversation["conversation_id"],
            "turn_id": final_turn["turn_id"],
            "request_text": "Qual è la potenza nominale del TR1?",
            "engineering_intent_id": intent["engineering_intent_id"],
            "intent_type": intent["intent_type"],
            "retrieval_lexical_terms": [governed_asset["label"]],
            "retrieval_include_neighborhood": True,
            "provider_id": "anthropic",
            "model_identifier": "model-under-test",
        },
    )
    assert repeat_engine_response.json()["plan"]["plan_id"] == (
        engine_body["plan"]["plan_id"]
    )

    # An unsupported intent runs nothing at all.
    unsupported_engine_response = api_client.post(
        f"/projects/{project['id']}/engineering-engine/execute",
        json={
            "engineering_session_id": final_session["session_id"],
            "conversation_id": final_conversation["conversation_id"],
            "turn_id": final_turn["turn_id"],
            "request_text": "Disegna uno schema funzionale",
            "engineering_intent_id": "conv-x:turn-x:1.0",
            "intent_type": "drawing_request",
        },
    )
    assert unsupported_engine_response.status_code == 200
    unsupported_body = unsupported_engine_response.json()
    assert unsupported_body["status"] == "unsupported"
    assert unsupported_body["plan"] is None
    assert unsupported_body["execution"] is None
    assert unsupported_body["engineering_response"] is None
