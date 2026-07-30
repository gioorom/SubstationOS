# Human Review (EPIC 30.4)

> **Route:** the review panel inside `/documents/{id}/workspace`
> **Rule:** engineering truth and engineering judgement stay separate,
> forever.

---

## 1. What this context is for

The deterministic pipeline produces engineering knowledge. It says
`TR1 HAS_RATED_POWER 630 kVA` because a versioned rule mapped an
association onto that meaning — and until this milestone, that was the
end of the story. Nobody could record that they had checked it.

Human Review adds the missing half:

```
Document → Pipeline → Semantic Statement → Human Review → Engineering Decision → Knowledge Graph (future)
```

**Human Review never becomes part of the pipeline.** It reads pipeline
output; the pipeline does not read it, cannot read it, and an
architecture test fails if any engineering domain module tries.

## 2. The core principle

| | Engineering truth | Engineering judgement |
|---|---|---|
| Produced by | A versioned rule | A named person |
| Property | Deterministic | Attributable |
| Storage | Immutable artefacts | Append-only records |
| Answers | *What does the document say?* | *Do we accept it?* |

A review **references** an immutable artefact by key. It never contains
one, never rewrites one, and there is no field anywhere in this context
into which a semantic statement, a fact, an entity or a piece of evidence
could be copied. That is structural, not conventional: a value with
nowhere to go cannot be written by accident.

Three tests hold this in place:

- no engineering domain module imports `app.domain.human_review`;
- no review module references an engineering ORM record;
- the semantic set before and after a review compares **equal**.

## 3. This is not the legacy `review_workflow`

`app/domain/review_workflow` already exists and reviews **Proposed
Claims** on the legacy Knowledge Graph path (Milestone 10.1). It is a
different context reviewing a different artefact, and the two are not
merged, not renamed and not related.

| | `review_workflow` (10.1) | `human_review` (30.4) |
|---|---|---|
| Reviews | Proposed Claims | Semantic Statements |
| Model | Mutable candidate with a status | Append-only judgements |
| Current state | A stored `status` column | A projection over history |
| Feeds | The legacy graph path | The future governed graph |

## 4. The domain

```
app/domain/human_review/
  review_target.py         what is reviewed - a type, a key, a document
  review_vocabulary.py     3 decisions, 9 reasons, and which pair with which
  review_models.py         Review, ReviewComment, ReviewerIdentity
  review_snapshot.py       the identity the artefact had at review time
  review_policy.py         what makes a review admissible
  review_applicability.py  whether a judgement still describes the pipeline
  review_projection.py     the current decision, computed
  review_events.py         the four domain events
  review_repository.py     the port - append and read, no update, no delete
```

### Decisions

`APPROVED`, `REJECTED`, `NEEDS_INVESTIGATION`. Three, no custom states,
no workflow engine. `NEEDS_INVESTIGATION` is neither a half-approval nor
a soft rejection — it is a reviewer recording that they looked and could
not yet decide, which is a real engineering outcome and the one a
workflow engine would have turned into a queue.

### Reasons

A closed catalogue, **required on every review**, so "why does this
pipeline get rejected?" is answerable in aggregate rather than by reading
prose.

Reasons are paired with decisions:

| Decision | Admissible reasons |
|---|---|
| Approved | confirmed by source, consistent with design, engineering exception, other |
| Rejected | incorrect interpretation, insufficient evidence, pipeline limitation, documentation issue, other |
| Needs investigation | ambiguous evidence, insufficient evidence, pipeline limitation, documentation issue, other |

"Approved because the interpretation is incorrect" is a sentence the
trail must not be able to contain, so the pairing is enforced at
construction and served to clients from
`GET /engineering-reviews/vocabulary` rather than duplicated in each one.

### Comments

Required for `REJECTED`, `NEEDS_INVESTIGATION` and any `OTHER` — the
cases where the reason alone explains nothing. An approval under a
catalogued reason may stand alone: requiring prose for the common,
uncontroversial case is how a review process becomes something engineers
work around.

**Plain text, not markdown.** That is a decision rather than an omission:
rendering user-authored markup means sanitising it, and a review comment
is read by engineers and by an audit, neither of whom needs a heading. It
is rendered as a React text node, and a test asserts no element is
produced from its content.

## 5. Immutability, and the current decision

**Reviews are immutable. The history is append-only.** There is no
method that changes a decision, the port declares no `update` and no
`delete`, and the API exposes no `PATCH` and no `DELETE` — a test walks
the OpenAPI document to prove it.

An engineer who changes their mind records **another** review. The first
stays exactly as written, because *"what did we think in March?"* is a
question an engineering record has to be able to answer.

Consequently:

> **The current decision is never stored.** It is the newest review for a
> target, computed on read.

A stored `current_decision` column would be a second account of the same
fact, and the day it disagreed with the history there would be no way to
tell which was true. There is no such column, no `is_current`, no
`superseded_at` and no `status` — and architecture tests assert their
absence in both the ORM model and the migration.

`superseded` on a history entry is derived from position in the
newest-first ordering, never from a flag.

## 6. The snapshot

A review recorded today has to be readable in five years, after the
document has been re-ingested twice and the rules have moved on three
versions. The snapshot records **enough identity to explain what was
reviewed** — and deliberately not the artefact graph:

| Recorded | Why |
|---|---|
| `content_checksum` | Which bytes |
| `semantic_rule_id` / `_version` | Which rule assigned the meaning |
| `semantic_contract_version` | Which contract it was expressed under |
| `resolution_policy_version` | How evidence became entities |
| `fact_policy_version` | How entities became facts |
| `semantic_policy_version` | How facts became meaning |
| `support_fingerprint`, `support_count` | The support chain, as identity |

**Not recorded:** statement type, subject, object, quantity, support
payload. What the statement *said* is read from the pipeline, which stays
its single account. A snapshot holding those would be a copy of
engineering knowledge living outside the pipeline that produced it, and
the first time the two disagreed nobody would know which was
authoritative.

## 7. Pipeline re-runs — the lifecycle

This was the milestone's hardest question, and the answer is **derived
from identity the pipeline already produces**, not invented.

### The property everything rests on

`EngineeringSemanticStatement.statement_key` is a SHA-256 over the
document, the exact fact source, the triple, and the rule and contract
versions. Therefore:

- **nothing changed** → the re-run reproduces the *same* key;
- **anything changed** — bytes, entity resolution, fact construction,
  semantic rule, contract — → the key is *different*.

So "does this review still apply?" is a **lookup**, and a review is never
matched to a statement by resemblance.

### The three states

```
                    record a review
                          │
                          ▼
                       APPLIES ────────────── the key is in the current set
                          │
        pipeline re-runs  │
                          ▼
           ┌──────────────┴───────────────┐
   key still present               key absent
           │                              │
        APPLIES              ┌────────────┴────────────┐
                    a current set exists      no current set exists
                    (different identity)              │
                             │                        │
                 REQUIRES_REVALIDATION            ORPHANED
```

| State | Means | What an engineer does |
|---|---|---|
| `applies` | The reviewed statement is in the current interpretation, under the identity it was reviewed under. | Nothing. |
| `requires_revalidation` | The document was re-interpreted under different bytes or rules. The judgement may still hold — and only a human may say so. | Review the current statement. |
| `orphaned` | There is no current interpretation to compare against: the semantic stage has not run since, or its set is gone. | Re-run the pipeline, then look again. |

### What is deliberately *not* modelled

There is no "the review was migrated to the new statement" state. Moving
a judgement onto an artefact derived under different rules is exactly the
inference no machine may make here: it would silently attribute to an
engineer an opinion about something they never saw.

**A review is never discarded in any state.** `requires_revalidation`
marks it; the record stays readable, with the identity it was passed
under, forever.

### Every transition, tested

| Scenario | Result |
|---|---|
| Identical re-run | `applies` — same key reproduced |
| Semantic rule version bumped | `requires_revalidation` |
| Document re-ingested (new checksum) | `requires_revalidation` |
| Statement disappeared (became ambiguous) | `requires_revalidation` |
| New statements appeared alongside | `applies` — matched by key, not by count |
| Semantic set deleted / never re-run | `orphaned` |
| Key matched, support differed | `snapshot_intact: false` — an integrity finding |

That last row should be impossible, since `statement_key` hashes the fact
source. It is checked precisely because it should be: if it ever happens,
the identity of an engineering artefact has stopped meaning what it
claims, and that must surface loudly rather than be trusted quietly.

## 8. Events

Four, and they belong to Human Review — nothing in the pipeline emits,
consumes or knows about them.

| Event | Kind | When |
|---|---|---|
| `ReviewRecorded` | Happened | A judgement was appended |
| `ReviewSuperseded` | Happened | A newer judgement became effective |
| `ReviewBecameHistorical` | Became true | The target is orphaned |
| `ReviewRequiresRevalidation` | Became true | The pipeline moved on |

The first two are recorded in the audit trail at the moment they happen.
The last two describe something that became true **without anybody doing
it** — a pipeline re-run never visits this context — so they are derived
observations, computed on read from `review_applicability.evaluate`.

Modelling them as published events would mean a subscriber, a queue and a
delivery guarantee: a workflow engine, which this milestone must not
build. Modelling them as values means the distinctions stay nameable,
testable and renderable, with nothing to keep in sync.

## 9. API

Resource-oriented, not RPC. There is no `/approve`, no `/reject` and no
`/supersede`: a judgement is a **member appended to a collection**, and
the decision is a field of that member.

```
GET  /engineering-reviews/vocabulary                          decisions and their reasons
GET  /documents/{id}/engineering-semantics/reviews            every current decision
GET  /documents/{id}/engineering-semantics/{key}/reviews      one statement's history (paged)
POST /documents/{id}/engineering-semantics/{key}/reviews      append a judgement
GET  /documents/{id}/engineering-semantics/{key}/current-review   the effective decision
```

- `POST` answers **201 always**, even when an earlier review exists: a
  second judgement *creates* a second record, and a `200` would suggest
  otherwise.
- `current-review` is a separate resource rather than a field on the
  history: it answers a different question, it is what the Workspace
  polls, and its own URL keeps "the effective decision" from ever looking
  like something a client could write.
- The document-wide summary exists so a Workspace listing two hundred
  statements does not make two hundred more requests. Unreviewed
  statements are **absent**, not present with a null decision — "never
  reviewed" is the absence of a judgement, and a row asserting it would
  be a judgement.
- History is **paged**, because it only grows.

### Statuses

| Status | Meaning |
|---|---|
| `201` | Judgement appended |
| `401` | No session (every review route is authenticated) |
| `403` | Signed in, and not permitted to record reviews |
| `404` | The statement is not in the document's current interpretation |
| `422` | The review does not satisfy the policy |

Reading a review of a statement that has since disappeared is **not** a
`404`: that is the case the snapshot exists for, and the projection
reports `requires_revalidation` or `orphaned`.

## 10. Authorization and audit

A new capability, `RECORD_ENGINEERING_REVIEW`, granted to `engineer` and
`administrator`. Reading reviews needs only `USE_ENGINEERING_PLATFORM` —
the separation is what lets a future auditor role read every judgement
without passing one, with no route changing.

No new role was invented. Reviewing the pipeline is what an engineer on
this platform is *for*; a separate "reviewer" role would be a second role
every engineer would have to be granted on day one.

**The reviewer is the authenticated identity.** There is no field in the
request body through which a caller could name somebody else — the same
guarantee EPIC 30.3 gave project creation, and a test submits a forged
`reviewer` and asserts it is ignored.

The reviewer's name, address and role are **copied** onto the review
rather than joined from `users`, so the record stays readable after an
account is renamed, re-roled or disabled. There is no foreign key on this
table at all — not to `users`, and not to the semantic tables, because a
re-run replaces a semantic set and a constraint would either block the
pipeline or cascade a historical judgement into nothing.

Two audit actions are added: `engineering_review_recorded` and
`engineering_review_superseded`. A review is already an attributable
immutable record, so the audit trail is not its only account — it is
there because *"what did this person do on Tuesday?"* is asked of the
trail, and a governed engineering decision is exactly that kind of
action.

## 11. Workspace integration

The Workspace stays read-first. Selecting a semantic statement shows its
meaning, its support chain and its identity as before; the review panel
is a **dedicated region beneath them**, and it is the one place in the
screen where an engineer acts.

The statement list carries two badges per row, and they say different
things:

- the **pipeline** badge — `interpreted` / `ambiguous`, what the rules
  produced;
- the **review** badge — `Approvato` / `Respinto` / `Da approfondire` /
  `Mai revisionato`, what an engineer decided.

Collapsing them into one would be exactly the confusion this milestone
exists to prevent.

### Language

Never `Corretto` / `Errato`, never ✓ / ✗ — a frontend test fails on all
four. The engineer reviews the pipeline; the pipeline is not "right" or
"wrong". `approved` is **not green** either, for the same reason
`interpreted` is not: green reads as *correct*, and an approval is one
engineer's judgement about one interpretation.

### The states the UI keeps apart

`loading`, `never reviewed`, `approved`, `rejected`, `needs
investigation`, `requires revalidation`, `orphaned`, `permission denied`,
`failed`. None is rendered as another, and each has a test.

Partial failure is handled: a history that fails to load leaves the
current decision on screen, because an engineer looking at a rejected
statement needs to see the rejection even if the timeline beneath it is
unavailable.

## 12. Preparing the Knowledge Graph

Human Review is intended to become the **only** source from which future
graph-promotion decisions are taken:

```
deterministic semantics  +  governed review decisions  →  Knowledge Graph
```

The contracts that milestone will need already exist and are stable:
`TargetReviewProjection` answers *what was decided*,
`ReviewApplicability` answers *does it still apply*, and `ReviewSnapshot`
answers *to what exactly*. A promotion rule can be written as "every
statement whose current decision is `approved` and whose applicability is
`applies`" without this context changing.

**Nothing of the graph is implemented here**, and no promotion happens.

## 13. Known limits

- **Review targets are semantic statements only.** `ReviewTargetType` is
  generic and has one member; evidence, entities, facts and documents are
  not reviewable, and adding their members "ready for later" would be
  values no endpoint accepts and no projection understands.
- **No review assignment, voting, approval chains or notifications.**
  Explicit non-goals — every one is a workflow engine in miniature.
- **The document-wide summary is unpaged.** Bounded in practice by the
  number of reviewed statements in one document; if that stops holding,
  the answer is paging on that endpoint.
- **`review_count` costs one query per reviewed target** in the
  document-wide summary. Fine at realistic counts, and the first thing to
  batch if it stops being.
- **Comments are plain text.** Markdown would need sanitising and a
  renderer; see §4.
- **Authorization is per-role, not per-project**, inherited from EPIC
  30.3: any authenticated engineer may review any statement in any
  project.

---

## Files

| Concern | Location |
|---|---|
| Domain | `apps/backend/app/domain/human_review/` |
| Persistence | `apps/backend/app/models/human_review.py`, `app/infrastructure/human_review/` |
| Application service | `apps/backend/app/services/human_review_service.py` |
| API | `apps/backend/app/routers/human_review.py`, `app/schemas/human_review.py` |
| Migration | `migrations/versions/c92f4d1a7b60_add_engineering_reviews.py` |
| Frontend | `apps/frontend/components/workspace/Review*.tsx`, `hooks/useStatementReview.ts`, `hooks/useDocumentReviews.ts` |
| Tests | `tests/domain/test_human_review_domain.py`, `tests/api/test_human_review_api.py`, `tests/architecture/test_human_review_boundaries.py`, `apps/frontend/tests/review.test.tsx` |
