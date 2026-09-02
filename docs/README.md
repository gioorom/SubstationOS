# Documentation index

There are 83 documents here. This page exists so you do not have to guess
which one answers your question.

Hand-written and deliberately short. It is not a generated listing — for a
machine-derived map of the repository, see
[`ai-context/`](ai-context/), which is regenerated rather than authored.

---

## Start here

| Document | Answers |
|---|---|
| [`../README.md`](../README.md) | What SubstationOS is, what it does today, how to run it |
| [`developer_setup.md`](developer_setup.md) | Local setup in detail, environment variables, an end-to-end walkthrough |
| [`architecture/knowledge_pipeline_overview.md`](architecture/knowledge_pipeline_overview.md) | The derivation pipeline end to end — read this before any stage document |
| [`../CLAUDE.md`](../CLAUDE.md) | The engineering manual: conventions, boundaries, what must never be done |

## The deterministic pipeline, stage by stage

In derivation order. Each stage is a pure function of the one above it.

| Stage | Document |
|---|---|
| Canonical text | [`architecture/engineering_evidence.md`](architecture/engineering_evidence.md) covers segmentation and extraction |
| Evidence | [`architecture/engineering_evidence.md`](architecture/engineering_evidence.md) |
| Entities | [`architecture/engineering_entities.md`](architecture/engineering_entities.md) |
| Facts | [`architecture/engineering_facts.md`](architecture/engineering_facts.md) |
| Semantics | [`architecture/engineering_semantics.md`](architecture/engineering_semantics.md) |

## Governance — how a statement becomes knowledge

| Document | Answers |
|---|---|
| [`architecture/human_review.md`](architecture/human_review.md) | The append-only review ledger, and why judgement never rewrites truth |
| [`architecture/promotion_rules.md`](architecture/promotion_rules.md) | What may enter the graph, and what is refused |
| [`architecture/knowledge_graph.md`](architecture/knowledge_graph.md) | The governed graph as a rebuildable projection |
| [`architecture/governed_structured_retrieval.md`](architecture/governed_structured_retrieval.md) | Reading governed knowledge without inferring |
| [`architecture/governed_context_assembly.md`](architecture/governed_context_assembly.md) | Selecting and budgeting context, with no I/O |
| [`architecture/engineering_reasoning.md`](architecture/engineering_reasoning.md) | Deterministic conclusions that are never persisted |

## Where the AI boundary is

| Document | Answers |
|---|---|
| [`architecture/llm_provider_abstraction.md`](architecture/llm_provider_abstraction.md) | The port a model sits behind |
| [`architecture/llm_invocation_runtime.md`](architecture/llm_invocation_runtime.md) | Timeouts, retries, and the disabled-by-default posture |
| [`architecture/engineering_engine.md`](architecture/engineering_engine.md) | The answering path, and what it may and may not do |

## Platform

| Document | Answers |
|---|---|
| [`architecture/security_architecture.md`](architecture/security_architecture.md) | Identity, session cookies, CSRF, authorization, audit |
| [`architecture/public_api.md`](architecture/public_api.md) | The HTTP contract |
| [`architecture/database_migrations.md`](architecture/database_migrations.md) | Schema ownership and migration conventions |
| [`architecture/frontend_architecture.md`](architecture/frontend_architecture.md) | The Next.js workspace |
| [`architecture/bakend_architecture.md`](architecture/bakend_architecture.md) | Backend layering *(filename is misspelled in the repository — known debt)* |
| [`architecture/operational_reliability.md`](architecture/operational_reliability.md) | Failure behaviour and operational concerns |
| [`architecture/performance_baseline.md`](architecture/performance_baseline.md) | Measured baselines |

## Decisions and constraints

| Document | Answers |
|---|---|
| [`architecture/adr/`](architecture/adr/) | 33 Architecture Decision Records, with a status index |
| [`architecture/architecture_freeze_af01.md`](architecture/architecture_freeze_af01.md) | Architecture Freeze v1.0 — the invariant register, and which test proves each one |
| [`architecture/ARCHITECTURE_FREEZE_V1_CHECKLIST.md`](architecture/ARCHITECTURE_FREEZE_V1_CHECKLIST.md) | The freeze checklist |
| [`project/PRODUCT_DEVELOPMENT_PLAN.md`](project/PRODUCT_DEVELOPMENT_PLAN.md) | Roadmap: status, EPICs, milestones |

The architecture invariants are **executable**. The register names each
invariant and the test function that proves it; the tests live in
`apps/backend/tests/architecture/`. If you want one thing to read that shows
how this project is built, read the freeze register and then open the tests
it names.

## Engineering data

Real engineering drawings are external inputs and are not repository content.
Where the reference corpus records real document text it records transcribed
lines, a page reference and a source handle — and those handles are
pseudonyms. See
[`architecture/adr/0033-pseudonymous-reference-corpus-provenance.md`](architecture/adr/0033-pseudonymous-reference-corpus-provenance.md)
for what was pseudonymised, what it costs, and what was rejected.

---

*Documents in `architecture/` describe one bounded context each and are named
after it, so a context you can name in the code has a document you can find by
the same name.*
