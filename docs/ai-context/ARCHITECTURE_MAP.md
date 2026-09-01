# Architecture Map

**CLASSIFICATION: DERIVED NAVIGATION AID.** Baseline `a304b11`, 2026-09-01.
See [README.md](README.md) for authority rules.

---

## The pipeline

```
              SOURCE DOCUMENT (immutable bytes + checksum)
                     |
  ===================|=========== DETERMINISTIC DERIVATION ==============
                     v              no LLM, no clock, no randomness
        Canonical Representation      [canonical_pdf]
                     v
        Canonical Text                [canonical_text]
                     v
        Evidence                      [engineering_evidence]   "I observed this, here"
                     v
        Entities                      [engineering_entities]   "these observations are one object"
                     v
        Engineering Facts             [engineering_facts]      "these entities are associated"
                     v
        Semantic Statements           [engineering_semantics]  "that association means this"
                     |
  ===================|=========== HUMAN JUDGEMENT ==========================
                     v
        Human Review                  [human_review]           append-only decisions
                     |
  ===================|=========== GOVERNED PROMOTION ========================
                     v
        Governed Knowledge Graph      [governed_knowledge_graph]
                     |                 sole runtime writer: knowledge_promotion_service
  ===================|=========== READ-ONLY PROJECTION =====================
                     v
        Governed Retrieval            [governed_retrieval]     queries, never infers
                     v
        Governed Context Assembly     [context_builder]        selects and budgets, no I/O
                     v
        Prompt Builder                [prompt_builder]
                     v
        Engineering Engine / Response [engineering_engine, engineering_response]
                     |
  ===================|=========== DERIVED REASONING =========================
                     v
        Engineering Reasoning         [engineering_reasoning]
                                       reads governed knowledge, concludes,
                                       persists NOTHING and promotes NOTHING
```

Verify the stages from `apps/backend/app/services/` (one service per stage) and
the boundaries from `apps/backend/tests/architecture/`.

---

## The separations that matter

Each is a real boundary in code, not a manner of speaking. Collapsing any of
them is the most likely way to break this architecture.

| Not the same as | Why |
|---|---|
| **Evidence** ≠ **Entity** | An observation is not a claim that two observations are one object. |
| **Entity** ≠ **Fact** | An object is not an association between objects. |
| **Fact** ≠ **Semantic Statement** | An association is not its meaning. |
| **Semantic Statement** ≠ **Review Decision** | Engineering truth is not engineering judgement. |
| **Approved statement** ≠ **the graph** | The graph is a rebuildable projection of approved statements (ADR-0024), not the source of truth. |
| **Retrieval** ≠ **inference** | Retrieval answers what is stored; it never derives. |
| **Context** ≠ **retrieval** | Context selects and budgets what retrieval returned; it performs no I/O. |
| **Reasoning conclusion** ≠ **governed knowledge** | Reasoning reads the graph and concludes. Nothing makes a conclusion governed. |

---

## Trust boundaries

**1. Source-derived provenance → deterministic derivation.**
Everything from Canonical Representation to Semantics is a pure function of its
upstream artifact and its own rule versions. No LLM may be reached — AF-DET-002
asserts this for the whole chain at once, naming each context explicitly.

**2. Deterministic truth → human judgement.**
Review reads semantics; the deterministic pipeline cannot read a review
(AF-TRUTH-002), and review writes no deterministic artefact (AF-TRUTH-001). The
boundary is symmetrical and enforced from both sides.

**3. Human judgement → governed knowledge.**
Exactly one application authority may author graph knowledge:
`knowledge_promotion_service`. It is the sole *runtime* writer — the write port
`GovernedGraphRepository` declares the capability, `SqlAlchemyGovernedGraphRepository`
implements it, and the router constructs the adapter without calling a write
method, so no API caller can bypass promotion. AF-KG-003 asserts this on the
capability across `app/services/` rather than on a filename; see
[BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) for the full chain.

**4. Governed knowledge → reading.**
The graph is reachable only as a projection (AF-KG-004). Retrieval is read-only;
context assembly does no I/O.

**5. Governed knowledge → derived reasoning.**
Reasoning consumes governed knowledge and produces conclusions that are **not
persisted** — there is no reasoning ORM model — and are not promoted. Any future
path from a conclusion to governed knowledge would be new architecture, not an
extension of this one.

---

## Artifact identity propagation

Every persisted deterministic artifact carries the identity of the computation
that produced it:

```
identity = H(identity contract, artifact kind, upstream identity,
             local derivation identity)
```

```
Source identity        = H(document, checksum, checksum algorithm)
        |
Canonical PDF          = upstream + representation contract + parser name/version
        |
Canonical Text         = upstream + segmentation contract
        |
Evidence Set           = upstream + extraction policy
        |
Entity Set             = upstream + resolution policy + entity model contract
        |
Fact Set               = upstream + fact policy + fact contract
        |
Semantic Set           = upstream + semantic policy + semantic contract
```

A stage names **only the versions it owns**. Everything above reaches it through
one upstream identity, so a change anywhere invalidates everything below it by
construction rather than by anyone copying a column. Reuse is a single identity
comparison, and the database uniqueness constraint encodes the same rule.

See [BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) § Artifact Identity for the
navigation entry points, and ADR-0032 (as amended) for the decision.

---

## What lives outside the engineering pipeline

Many packages sit outside the derivation chain — `project` (the root
aggregate everything is scoped to), the document lifecycle contexts, `identity`,
`ontology`, the session and conversation contexts, the answering path,
`evidence_evaluation`, the cross-cutting `audit` and `shared_kernel`, and the
still-active pre-governed-graph surfaces.

[BOUNDED_CONTEXTS.md](BOUNDED_CONTEXTS.md) § Inventory is the complete list,
with every package assigned exactly once; this paragraph is orientation, not an
enumeration.
