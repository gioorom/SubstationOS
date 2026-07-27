# ADR-0019: Engineering Request Classification

## Status

Accepted.

## Context

By Milestone 21 (Working Memory Foundation, ADR-0018), a
`Conversation` holds structured engineering dialogue and a
deterministic `WorkingMemory` provides the bounded context needed to
keep reasoning. Nothing yet answers the question a future orchestrator
must answer before doing anything else: **what category of engineering
workflow is this request asking for?**

Answering it badly has two distinct failure modes this milestone
guards against. Building a generic chatbot intent detector would import
a whole discipline of psychological-intent modelling this product has
no need for and no way to validate. Building an LLM-based classifier
would make the very first routing decision in the pipeline
non-deterministic, unexplainable, and dependent on a provider - the
exact properties every prior milestone in this pipeline has worked to
avoid at its own layer.

## Decision

### 1. This is request classification, not intent detection

The bounded context is named `engineering_intent` for roadmap
continuity, but its documented responsibility is **Engineering Request
Classification**: mapping an explicit request to one of a small,
operational set of workflow categories. It makes no claim about what
the user wants psychologically, believes, or is trying to achieve
beyond the words actually written. Every piece of documentation,
docstring, and code comment in this context states its behaviour in
those terms - never "understanding" or "reasoning about" a request.

### 2. The first classifier is deterministic, and LLM classification is excluded

Classification is a fixed, versioned table of explicit rules
(`engineering_intent_rules.py`) evaluated against deterministically
normalized text (`engineering_intent_normalization.py`), resolved by an
explicit precedence policy (`engineering_intent_policy.py`). No LLM, no
embeddings, no vector similarity, no external NLP service, no provider
SDK is involved - enforced by a dedicated architecture test that also
forbids `numpy`/`sklearn`/`torch`/`transformers`/`spacy`/`faiss` and
friends, not just provider SDKs.

Three reasons:

- **This is a routing decision, not an answer.** Every downstream
  workflow this classifier selects is itself already governed,
  reviewed, and traceable. Making the *routing* probabilistic would
  introduce non-determinism at the one point in the pipeline where a
  wrong turn silently sends a correct question down the wrong workflow.
- **Explainability is cheap here and expensive there.** A rule table
  can say exactly why it fired ("the token `confronta` at position 0
  matched rule `comparison.verb`"). An LLM classifier can only be
  asked to *narrate* why, which is not the same thing and is not
  verifiable.
- **Replaceability, not permanence.** The domain contract
  (`EngineeringIntent`, `EngineeringIntentClassificationInput`,
  `EngineeringIntentClassificationResult`) is deliberately independent
  of *how* classification happens. A future statistical or hybrid
  classifier can replace `engineering_intent_classifier.py` entirely
  without changing a single consumer - see SS8.

### 3. Evidence is first-class

Every rule that fires produces an `EngineeringIntentEvidence` carrying
which rule matched, what text matched, at what token position, toward
which candidate type, and how strongly - plus a stable, machine-readable
`description_code`, never AI-generated prose. **No hidden reasoning and
no chain-of-thought is ever stored.** This makes every classification
reproducible and auditable: given the same request and policy version,
the same evidence appears in the same deterministic order
(`(token_index, matched_rule_id)`).

### 4. Confidence is categorical, never a fabricated probability

`EngineeringIntentConfidence` is `HIGH`/`MEDIUM`/`LOW`/`UNRESOLVED`,
derived from an explicit documented policy (`derive_confidence`):
`HIGH` when exactly one type has a strong match; `MEDIUM` when the
signal is weak or contested; `LOW` for the general-engineering
fallback; `UNRESOLVED` for ambiguous and unsupported results. A
floating-point probability would imply a statistical model that does
not exist here - inventing one would be fabricating certainty, exactly
what ADR-0015 already rejected for Engineering Response's own
uncertainty model.

### 5. Ambiguity is a valid result, not a failure to decide

When two or more **materially distinct operations** (drawing,
verification, comparison, navigation) each have a strong match,
precedence alone would silently discard a genuinely requested
operation. The classifier returns `AMBIGUOUS_REQUEST` with every
competing candidate reported as a secondary type and all evidence
retained - "Confronta e modifica lo schema" and "Disegna uno schema e
poi verificalo" both resolve this way. Reading-oriented types
(document lookup, explanation, knowledge query) are deliberately
excluded from this rule: they overlap constantly in natural phrasing,
and forcing ambiguity on every "spiegami quale..." would make the
classifier useless. **The classifier prefers explicit uncertainty over
false certainty.**

### 6. EngineeringIntent is not executable

It is a classification result: it executes no workflow, retrieves no
documents, queries no graph, invokes no LLM, and never modifies
`Conversation` or `WorkingMemory`. `secondary_intent_types` are
*explanatory metadata* recording other workflows the request signalled
- never executable sub-tasks. Real multi-step planning and request
decomposition belong to a future orchestration milestone.

### 7. This context depends on no other bounded context

`EngineeringIntentClassificationInput` carries plain identifiers, the
request text, a caller-supplied timestamp, and two already-extracted
structural Working Memory signals (a boolean and a count) - never a
`Conversation`, `WorkingMemory`, or `EngineeringResponse` object. This
gives `app/domain/engineering_intent/**` the **smallest dependency
surface in the entire pipeline: zero other domain contexts**, verified
by its own architecture test. It also enforces the milestone's own rule
that Working Memory may be used for structural context only, never as a
route into hidden semantic inference: the classifier structurally
*cannot* read memory contents, because it never receives them.

### 8. How a future classifier replaces this one

The replacement seam is `classify_engineering_request` in
`engineering_intent_classifier.py`. A future implementation must
produce the same `EngineeringIntentClassificationResult` shape and keep
the same guarantees the validator already enforces (deterministic
identity, evidence supporting the selected type, precedence respected,
confidence consistent with the policy). A statistical classifier that
cannot produce reproducible evidence would fail
`validate_engineering_intent` - deliberately: any replacement must
remain explainable, or it is not a valid classifier for this pipeline.

### 9. How the Engineering Assistant will consume the result

Milestone 23 will read `intent_type` to select a workflow,
`confidence`/`AMBIGUOUS_REQUEST` to decide whether to proceed or ask a
clarifying question, `secondary_intent_types` to mention what else it
noticed, and `evidence` to explain its own routing decision to the
engineer. It will never re-derive the classification itself.

## Consequences

**Easier:**

- The pipeline's first routing decision is fully reproducible,
  auditable, and free of provider dependency - a classification can be
  explained to an engineer by pointing at the exact matched token.
- Rules are data: adding a signal is a table edit plus a test, not a
  change to control flow.
- Milestone 23 receives a stable, small contract and never needs to
  know how classification happened.

**Harder / deferred:**

- Rule tables need maintenance as real request phrasing is observed;
  novel phrasing falls to `GENERAL_ENGINEERING_REQUEST` or
  `UNSUPPORTED_REQUEST` rather than being guessed at. This is the
  intended trade-off, but it does mean vocabulary coverage is an
  ongoing, explicit task.
- The domain vocabulary is deliberately limited to SubstationOS's
  current scope (primary substations, HV/MV, transformers, switchgear,
  protection, measurement, cables, equipment, bays/montanti, drawings,
  project documentation). A request using engineering terms outside
  that list classifies as `UNSUPPORTED_REQUEST` - correct today,
  something to revisit when EPIC 8's multi-domain expansion arrives.
- No persistence: a classification's lifetime is one request/response
  chain, the same posture Milestones 19-21 take.

## Rejected Alternatives

- **Use an LLM to classify the request.** Rejected explicitly by this
  milestone's own framing and on the merits - see Decision SS2.
- **Model this as generic chatbot intent detection with a large
  taxonomy.** Rejected: dozens of intent types that no workflow
  consumes are unmaintainable and untestable. The taxonomy is
  deliberately small and every type maps to a workflow an orchestrator
  could actually select.
- **Force a single classification always, resolving every conflict by
  precedence.** Rejected: it would silently discard a materially
  distinct requested operation ("Confronta **e modifica** lo schema"),
  which is worse than admitting ambiguity - see Decision SS5.
- **Emit a floating-point confidence score.** Rejected: no statistical
  model exists here to produce one honestly - see Decision SS4.
- **Accept a `WorkingMemory` object as classifier input.** Rejected:
  it would create a dependency on another bounded context purely to
  read two structural facts, and would open the door to future hidden
  semantic inference over memory contents. Passing the two
  already-extracted signals keeps the dependency surface at zero.
- **Generate `EngineeringIntentId` randomly.** Rejected: reclassifying
  identical input under the same policy version must yield the same
  identity, which a random id makes impossible to state - the same
  reasoning ADR-0018 applied to `WorkingMemoryId`.
- **Substring matching instead of whole-token matching.** Rejected: it
  produces false matches from words containing rule tokens ("aprile"
  firing the "apri" navigation rule, "vsat" firing "vs"). Whole-token
  matching over normalized text costs nothing and eliminates the class
  of error entirely.
