# ADR-0023: Human Review as append-only judgement, with identity-based revalidation

## Status

Accepted.

## Context

EPIC 30.4 introduces the Human Review bounded context: authenticated
engineers recording governed decisions over deterministic pipeline
artefacts. Two decisions in it are hard to reverse — changing either later
means a schema migration and a re-interpretation of every record already
written — and are therefore recorded here.

**First**, how a judgement is stored, and where "the current decision"
lives. The candidates were a mutable review record carrying a status
(the shape `review_workflow` already uses for Proposed Claims), and an
append-only history whose current decision is a projection.

**Second**, what happens to a recorded judgement when the pipeline runs
again. The pipeline is deterministic and re-runnable by design; a review
recorded on Tuesday must still mean something after Wednesday's re-run,
and it must not silently come to mean something it never meant.

The constraint over both: the platform's value rests on the pipeline
being deterministic. Nothing about human judgement may become an input to
it.

## Decision

### 1. Reviews are append-only; the current decision is a projection

One immutable record per judgement. An engineer who changes their mind
appends another; the earlier one is never modified, and the repository
port declares no `update` and no `delete`.

**The current decision is not stored.** It is the newest review for a
target, computed on every read. There is no `status`, `is_current`,
`superseded_at` or `current_decision` column, and architecture tests
assert their absence in both the ORM model and the migration.

A stored current decision would be a second account of a fact the ordered
history already states, and the day the two disagreed there would be no
way to tell which was true. `superseded` on a history entry is likewise
derived from position, never from a flag — writing one would mean
modifying an immutable record.

### 2. Revalidation is decided by artefact identity, not by comparison

`EngineeringSemanticStatement.statement_key` is already a SHA-256 over
the document, the exact fact source, the triple, and the rule and
contract versions. That property does the work:

- an identical re-run reproduces the **same key** — the review is still
  about the statement in front of the engineer, and nothing needs
  detecting;
- any change to bytes, entity resolution, fact construction, the semantic
  rule or the contract produces a **different key** — so a statement
  derived differently can never silently inherit a judgement passed on
  the old one.

"Does this review still apply?" therefore reduces to a lookup against the
document's current interpretation, with three outcomes:

| | |
|---|---|
| `applies` | The key is present. |
| `requires_revalidation` | A current interpretation exists and the key is absent — the pipeline moved on. |
| `orphaned` | No current interpretation exists to compare against. |

**A review is never discarded in any of them**, and there is deliberately
no state meaning "migrated to the new statement".

### 3. A review references artefacts; it never contains one

A review names its target by key and records a `ReviewSnapshot` — the
identity the artefact had at review time: checksum, rule id and version,
contract version, the three policy versions, and a fingerprint over the
supporting fact keys.

It records **no** statement type, subject, object, quantity or support
payload, and there is no field into which one could be written. There is
no foreign key on the table at all.

### 4. Three decisions, and reasons paired to them

`APPROVED`, `REJECTED`, `NEEDS_INVESTIGATION`, from a closed enum. A
required reason, from a closed catalogue, and a domain rule stating which
reasons may accompany which decision. A comment is required where the
reason alone explains nothing.

### 5. Events are values, not a published stream

`ReviewRecorded` and `ReviewSuperseded` describe writes and are recorded
in the audit trail. `ReviewBecameHistorical` and
`ReviewRequiresRevalidation` describe things that became true without
anybody doing them, and are derived on read.

## Consequences

**Positive**

- The complete history of engineering judgement is preserved and
  unforgeable; "what did we think in March?" is answerable.
- The current decision cannot drift from the history, because it does not
  exist independently of it.
- Revalidation needs no diffing, no heuristics and no background job: it
  is a key lookup, and it is correct by construction because the pipeline
  already computes the identity it depends on.
- A judgement is never silently carried onto an artefact derived under
  different rules — the failure that would attribute to an engineer an
  opinion about something they never saw.
- The pipeline stays completely unaware of review, so determinism is
  untouched.
- The contracts a future Knowledge Graph promotion needs already exist.

**Negative**

- Reading the current decision costs a query, and the document-wide
  summary costs one `count` per reviewed target. Acceptable at realistic
  volumes and the first thing to batch if it stops being.
- The review table only grows. That is inherent to an audit-grade record
  and is why history is paged.
- `requires_revalidation` puts work on engineers after every rule change:
  each affected judgement must be re-passed by a human. That is the
  cost of not guessing, and it is the intended cost.
- An engineer correcting a typo in their own comment must append a second
  review. Deliberate: an amendable record is not a record.

**Neutral**

- Comments are plain text. Markdown would require sanitising and a
  renderer, neither of which this milestone needs.
- Any authenticated engineer may review any statement. Project-scoped
  review permissions wait for a project-membership model.

## Rejected Alternatives

**A mutable review record with a status column**, as `review_workflow`
uses for Proposed Claims. Rejected because it makes the history
overwritable: changing a decision would lose the earlier one, and an
engineering record that cannot say what was thought last quarter is not
an engineering record. The existing context keeps its shape; it reviews a
different artefact under different requirements, and unifying them would
have forced one of the two into the wrong model.

**A stored `current_decision`, denormalised for read speed.** Rejected
as a second source of truth for a fact the history already states. The
read it saves is a single indexed query.

**Matching a review to a re-derived statement by subject, object and
type.** Rejected outright: it is the one inference no machine may make
here. It would attribute to a named engineer an opinion about an artefact
they never saw, and the resulting record would be indistinguishable from
one they actually passed.

**Automatically re-applying an approval when only a policy version
changed.** Rejected for the same reason in a milder form. "The rule
barely changed" is an engineering judgement, and this context exists
because engineering judgements need a person attached.

**Deleting or hiding reviews whose statements disappeared.** Rejected —
the EPIC required it not be done, and it is also wrong: a judgement that
vanishes when the pipeline changes is worse than useless, because its
absence is indistinguishable from nobody ever having reviewed.

**A workflow engine — assignment, states, transitions, approval
chains.** Rejected as scope this milestone explicitly excludes, and as a
model that would have replaced three honest decisions with a
configurable state machine nobody had a requirement for.

**A `reviewer` field in the request body.** Rejected: it is a field in
which a caller could claim to be somebody else. The actor is the
authenticated identity, exactly as EPIC 30.3 established for project
creation.

**Publishing review events to a subscriber.** Rejected because two of the
four events describe conditions that arise without any action, so
delivery would have to be triggered by something polling — which is what
computing them on read already does, without a queue.

## Related

- `docs/architecture/human_review.md`
- ADR-0004 (reviewed facts only in the queryable graph) — the same
  principle, now with a governed context able to record what "reviewed"
  means.
- ADR-0006 (AI as interpretation/presentation layer) — judgement,
  likewise, describes what the domain produced and never adds to it.
- ADR-0022 (session authentication) — the authenticated identity a review
  is attributed to.
