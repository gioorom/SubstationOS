# ADR-0035: Human-Authored Document Assertions

## Status

Accepted. Introduced by the *Human-Authored Document Assertions*
milestone, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted.

**The decision is accepted; the implementation is deliberately deferred**
and is gated on a prerequisite this ADR names in §9.

**Every normative statement below describes the shape a future
implementation must take, and authorises none of it to be built now.**
Where a section instead describes the repository as it stands today -
§9's missing version handle, §11's live defect, the Debt section - it
says so. Where the text says
the context "is recorded in its own table", or that a capability "is
declared per route", or that a vocabulary "reaches the public schema",
read it as a constraint on that deferred work. Nothing here authorises a
table, a route, a vocabulary, a capability or a frontend control to be
created, and none was: this milestone changed no production code.

AF-01 §22 sorts a change into one of two categories: ordinary evolution,
or a change requiring an ADR that names the invariant it alters. This
change is **neither** - it alters no AF-01 invariant, and §22 has no
third category for it. It is recorded as an ADR because CLAUDE.md §11
requires one for a new bounded context, and because it admits a fifth
kind of statement into a system that has kept four such boundaries
carefully apart.

Answers the debt
[ADR-0034](0034-spreadsheet-canonical-representation.md) recorded against
itself - *"The first pressure on this ADR will be a request for a
`header_row` field. It must be refused here and answered by a reviewed,
versioned rule in a context of its own."* - and answers it **only in
part**. See §10 and the Rejected Alternatives.

Adds no governed vocabulary, no graph capability, and no engineering
semantics.

---

## Context

### The situation that forced the decision

The spreadsheet lineage now reaches production. A workbook is read into a
canonical representation that records worksheets, rows and cells at the
file's own coordinates, and refuses - in its model, its factory, its
reader port and its adapter, and under an executable test - to record
what any of it *means*.

A real cable register then presented a problem the pipeline cannot
answer. The workbook contains a table. Several rows could plausibly be
its header: a title block, a revision line, and a row of column captions.
The workbook's own metadata is self-contradictory on the point - its
autofilter names one row, its print titles name a range. A parser can
observe every cell and every coordinate. **Nothing it can observe
determines which row is authoritative.**

An engineer looking at the file knows immediately. The system has no way
to record that they know.

### What the system models today, and what it refuses to

Four kinds of statement bear on this decision, and the boundaries
between them are the platform's main asset. They are not a census of
every statement-bearing context - `proposed_claims` and
`engineering_index` hold candidates and leads, `engineering_reasoning`
derives conclusions, and `governed_knowledge_graph` projects what review
approved - but they are the four an authored statement could plausibly
be filed under:

| Kind | Says | Produced by | Where |
|---|---|---|---|
| **Source content** | the bytes, and a faithful reading of them | a versioned reader | `canonical_pdf`, `canonical_text`, `canonical_spreadsheet` |
| **Extracted evidence** | "these characters, at this location, matched this rule" | a versioned rule | `engineering_evidence`, `spreadsheet_evidence` |
| **System proposal** | "these observations may amount to this statement" | versioned policy | `engineering_entities`, `engineering_facts`, `engineering_semantics` |
| **Human review verdict** | "I approve / reject / must investigate *that* statement" | a named engineer | `human_review` |

Each is separated from the next by structure rather than by convention.
A review is the clearest case: it names its target by the target's own
deterministic key and carries no *artefact* payload - a free-text
reviewer comment aside, which §6 returns to - because, in the context's
own words, *"there is no field on a review into which a semantic statement,
a fact or an entity could be copied, so no review can quietly become a
second account of what the document says."*

The evidence contexts state the complementary rule twice, verbatim:
*"An observation whose source cannot be located is not evidence; it is an
assertion, and this system does not store assertions."*

That sentence is the honest starting point for this ADR. The statement
this milestone must represent **is** an assertion by that definition, and
the system has said, in two domain modules, that it does not store them.

### Why none of the four can absorb a fifth

Not one of these boundaries can be widened without deleting the property
that makes it worth having:

- A **review** has no typed field for an asserted value, and its
  snapshot
  requires nine mandatory pipeline-shaped columns - a semantic rule id, a
  resolution policy version, a support fingerprint among them - that a
  statement about workbook structure simply does not have. Storing one
  means writing invented values into `NOT NULL` columns, which is exactly
  the failure `spreadsheet_evidence` refused when it declined to reuse
  page-shaped provenance for a cell.
- **Evidence** requires a locator that lets a reader re-read the exact
  characters, and a versioned rule as its producer. A human statement has
  neither. Giving evidence a human author would also make an artefact's
  identity a function of a person, which would mean the same bytes
  processed under two logins produce two different artefacts.
- A **proposed claim** is mutable, has no author field at all, and
  requires cited evidence - its validator's own exception for the empty
  case reads *"it is an unsupported assertion."*
- **Source content** is a pure function of bytes and reader version. A
  human statement is a function of neither.

### The three properties that make this a different kind of statement

1. **Its author is a person, not a rule.** Every artefact the
   deterministic pipeline produces names a versioned rule as its
   producer, and most of those contexts are fenced by test against ever
   carrying a user - though not all of them are, and §8 records which
   are missed. The Engineering Index is the standing exception that
   proves the point: it carries neither a rule nor an author, and
   ADR-0002 classifies what it holds as a lead rather than knowledge.
2. **It is not reproducible from the source.** Re-running the pipeline
   over the same bytes reproduces every derived artefact byte for byte.
   It cannot reproduce a human's declaration, because nothing in the
   bytes entails it.
3. **Its whole value is that it survives a revision.** Every other
   artefact is content-addressed precisely so that it does *not* need to
   survive; it is rebuilt. An assertion that dies whenever the document
   is re-issued is worth very little in a revision-heavy discipline.

The third property is the one with no foundation under it, and §9 is
about that.

---

## Decision

### 1. A human-authored assertion is a fifth kind of statement, in a bounded context of its own

It is **not** a review, not evidence, not a proposed claim, and not
source content. It is recorded in a dedicated bounded context, with its
own aggregate, its own repository port, its own table and its own
fitness functions.

The repository's own idiom decides this. When a genuinely new kind of
statement appeared before - derived reasoning, in ADR-0029 - the answer
was *"a separate type, in a separate bounded context, in a separate
field, at every layer it appears"*, and a `derived: true` flag on an
existing type was rejected because *"a flag is a convention, and
conventions erode."*

**What it is:** a durable, attributed, append-only record that a named
engineer declared something about the structure of a specific version of
a specific source document, at a specific location in it.

**What it is not**, and each of these is a refusal with a reason:

- It is **not evidence**. Nothing observed it. It carries no `rule_id`,
  and it must be structurally incapable of carrying one.
- It is **not a verdict**. It does not judge an artefact the pipeline
  produced; it states something the pipeline did not produce.
- It is **not truth**. It is one named person's declaration, and the
  system records it as that and nothing more.
- It is **not an input to deterministic extraction**. See §7.
- It is **not a semantic claim**. It may say where a thing is. It may
  never say what a thing means. See §6.

### 2. The author is copied, never referenced, and never supplied by the caller

The author is taken from the authenticated identity and denormalised onto
the record: user id, display name, email, role. There is no foreign key
to `users`, following `human_review` and `projects`, so the record stays
readable after an account is renamed or disabled.

A caller-supplied author field is forbidden. ADR-0023 already rejected
one, in terms this ADR adopts unchanged: *"it is a field in which a
caller could claim to be somebody else."*

### 3. Its identity is its own, and is never an `ArtifactIdentity`

**An assertion is identified by a key derived from the whole of what was
declared - including who declared it and when - and never from the
statement alone.**

A key over document, locator, type and value would collapse two
engineers who declare the *same* thing about the same region into one
record, when they have made two declarations. It would also repeat on a lawful
assert / withdraw / re-assert sequence, whose first and third records
must stay distinct - which follows from §10's append-only rule rather
than being stated there: if two records shared a key, a withdrawal that
names its target by key could not say which one it retracts. The author and the instant are not
metadata bolted onto the statement; for a declaration they are part of
what was declared, and putting them in the preimage is what makes each
one distinct.

The instant must therefore be distinguishing, not decorative: the
implementing milestone states its granularity, and adds a tie-breaking
element if that granularity admits two records from one author about one
region within a single tick.

**That tie-breaker is constrained, and finding one is real work.** A
database-assigned sequence is out for the reason above: it is stable
only inside the database that issued it. A random nonce would survive
that test - carried on the record, any reader can recompute the key from
it - but it fails a different one: it is not part of what the engineer
declared, so it would make the identity of a declaration depend on a
value nobody stated. The honest position is that this ADR does not name
a tie-breaker, and the implementing milestone inherits an open design
question rather than a clerical one.

This is the opposite of the rule that governs a derived conclusion, and
deliberately so. A reasoning identity excludes wall-clock time because
two evaluations of unchanged knowledge *are* the same conclusion and a
timestamp would make them look like two. Two declarations made at
different moments are genuinely two declarations, and a key that hid
that would make a withdrawal indistinguishable from the assertion it
retracts. Same principle - the identity is a function of what the thing
actually is - applied to a different kind of thing.

**A database-assigned surrogate is not sufficient**, for a reason the
repository states about its own identities: an identity must produce the
same value *on any machine, in any process, forever*, and one nobody can
recompute is one nobody can compare. A surrogate is stable only within
the database that issued it, so a downstream stage that hashed one into
its derivation identity (§7) would be reproducible in one deployment and
not across two. A record still carries a surrogate primary key; that is
storage, not identity.

An assertion is therefore addressable and recomputable, and deliberately
**not** deduplicable. Anything derived downstream may hold a
deterministic identity whose upstream is the assertion key - at which
point the assertion is an immutable, recomputable input, and determinism
holds in the strong sense §7 claims.

It must **not** enter the `ArtifactIdentity` chain, and the reason is
that the primitive's guarantee inverts into data loss here.
`ArtifactIdentity` exists to answer a reuse question - ADR-0032 puts it
as *"does an artifact with this identity exist for this document?"* - and
that question has no sensible answer for a declaration. `RECOMPUTE`, one
of its five outcomes, is the clearest case: nothing can re-derive what a
person said. Worse, entering the chain would mean adopting its composition: an
identity derived from an upstream artefact plus the local contract
versions of the stage that produced it. An assertion has no such
derivation. It would have to nominate the workbook as its upstream -
stating that the declaration is a function of those bytes, which is
exactly what it is not - and a later run, finding that identity absent,
would be entitled to conclude the artefact should be **recomputed**.
Nothing can recompute what a person said.

An assertion is a **root**, like the source, not a derivation.

### 4. Its locator is closed, typed, and specific to one source family

A spreadsheet assertion carries a worksheet index **and** worksheet name,
and a rectangular region as first/last row and first/last column. Both
worksheet fields, because the evidence context already learned that
neither survives a revision honestly on its own.

**No generic cross-format locator is introduced.** ADR-0034 forked the
two source families at the root and forbade the spreadsheet family from
using the words `page`, `block`, `span` or `line`; a locator general
enough to address a PDF, a workbook and a drawing at once would re-merge
what that ADR deliberately split, and the only vocabulary general enough
to span them is a semantic one. There is also no canonical representation
of a drawing to address - so a "general" locator would be designed
against one family that has a use case for it, one that does not, and
one that does not exist.

**Three of the words this locator wants are already spoken for**, and by
the anti-pattern it is defined against: `sheet`, `cell_range` and
`region` are all kinds of the Engineering Index's opaque locator, and
`table_region` is on the prohibited-interpretation list. The repository's
own name for a rectangle over a worksheet is a used range, and that shape
- first and last row, first and last column - is the one to follow.

A free-text locator is forbidden. The Engineering Index already has one -
its `value` is opaque *by contract*, and ADR-0002 records that context as
holding unreviewed leads carrying no trust guarantee - and nothing
validates that `"A3:D4"` is well-formed, inside the worksheet, or even a
range.

**One region, not a region and a row.** A statement naming both a header
row and a region that contains it admits two readings of itself. The
record carries the region; any distinguished row within it is expressed
as an offset into that region and validated against it.

Nothing here determines which row that is. **A machine determining a
distinguished row and a person declaring one are different acts**, and
this ADR authorises only the second: somewhere to record what an engineer
said, with their name on it. Header determination - a rule that reads a
workbook and concludes - remains out of scope in every form.

### 5. Conflict is an outcome, never a tiebreak

Two engineers may assert different things about the same region. The
system **must not** silently select one.

Newest-wins is correct for `human_review`, because a judgement is
subjective and the latest one is the operative one. A statement about
where a header is, is not subjective - exactly one of the two engineers
is mistaken, and collapsing that into a clock comparison would hide an
engineering disagreement behind a timestamp.

The repository already has the right shape: a closed, three-valued match
outcome with `MULTIPLE_MATCHES` as a first-class result, computed before
any limit is applied so ambiguity cannot be truncated away. Conflict
between assertions is modelled the same way - **computed on read, never
stored**, and surfaced as a distinct outcome rather than resolved.

This forbids a `current_assertion_for(region)` accessor. A method whose
signature returns one answer has already decided there is one.

### 6. The assertion type names a position in a grid, never a role in a schema

The type vocabulary is a closed enum, and it is where engineering
semantics will try to enter - one plausible member at a time.

The rule is: **a member may name a position in a grid. It may never name
a role in a schema.** "The distinguished row of this region" is a
position. "The cable-identifier column" is a role, and a role is meaning.

This is the same move ADR-0031 made when it asserted derived vocabularies
disjoint from governed ones, rather than trusting a naming convention to
keep them apart.

This boundary needs a fitness function that reaches the new context, by
widening the existing scans to its directory, which §14 row 17b
requires. The existing prohibition names eight words - `header`, `header_row`,
`column_name`, `column_header`, `field_name`, `record`, `register_kind`
and `table_region`, the last of which is closest to this context's own
locator - and is scoped by directory to the four spreadsheet packages; a new
sibling context sits outside that scan, so the milestone's own
prohibition would be **unenforced exactly where it newly matters**.

The assertion carries no free-text field. `human_review` confined prose
to a comment that engineers and auditors read and that **no machine
consumer** does; an assertion with a `label`,
`note` or `description` is where "CABLE_ID means cable identifier" gets
typed.

### 7. An assertion is never an input to deterministic extraction

ADR-0023 states the constraint this ADR must not break: *"the platform's
value rests on the pipeline being deterministic. Nothing about human
judgement may become an input to it."*

An assertion is therefore an **overlay**, not a stage. Extraction runs
identically whether or not one exists: same source plus same extraction
implementation yields the same evidence, always.

**If a future stage consumes an assertion, it does so by naming it.**
That stage hashes the assertion's own identity into its local derivation
identity:

```
identity = H(contract, kind, canonical_representation_identity,
             (stage_policy_version, assertion_key))
```

Determinism survives exactly. The same bytes *and the same declared
assertion* always produce the same reading; changing the assertion
produces a **different artefact stored alongside the old one**, which in
turn returns `REQUIRES_REVALIDATION` for every downstream review. The
human declaration becomes an immutable, identified input rather than an
ambient influence.

This ADR authorises the shape of that composition. It does not authorise
the stage.

### 8. The assertion context is named in the freeze, and cannot reach an LLM

The new context is added to `DETERMINISTIC_CONTEXTS` - not because its
content is derived, but because that list means *"reaches no LLM"*, and
`human_review` is in it for the same reason.

This is not optional bookkeeping. **A domain directory absent from that
tuple is silently unconstrained** - no test turns red. The precedent is
recorded: `canonical_spreadsheet` was added to that list precisely
because its omission would have let a spreadsheet module import the LLM
runtime while passing every test in the repository.

Two further consequences:

- An assertion must be **structurally incapable of becoming a context
  item** for an LLM prompt. Context items are required to carry graph
  provenance - a statement key, a review id - and an assertion has
  neither. Forcing one would mean fabricating provenance.
- **No assertion prose reaches a model.** No human-authored text ever
  has: reviewer names, decisions, reasons and comments are all absent
  from prompt composition, and only an opaque review id travels.

The name of the new context is also added to the cross-cutting
truth-boundary invariant - **and that invariant's own scan set must be
extended at the same time, or the addition buys nothing here.** It scans
six pipeline contexts and names neither spreadsheet context, so the
extractor overwhelmingly most likely to import an assertion sits outside
it. Adding the assertion's name to a list that does not look at
`spreadsheet_evidence` would leave the guarantee stated and undelivered
for the one source family this decision is about.

### 9. An assertion pins a source version - and that version handle does not exist yet

This is the prerequisite, and it is the reason the implementation is
deferred.

The `documents` table has **no checksum, no version and no lineage**.
Every upload creates a new row with a new id, unconditionally.
Deduplication is refused as stated policy, not merely absent. There is no
`supersedes`, no `superseded_by`, no `previous_document_id`; the
`revision` column is free text and is never written by the upload path.

So document 17 revision A and document 18 revision B are, to this system,
two unrelated documents - and every assertion about 17 is permanently
orphaned the moment the file is re-issued.

**A durable human record cannot be built on an identity that is not
durable.** Either document lineage is introduced first, or this feature
is knowingly shipped with the property that an assertion dies with its
upload - and the second answer makes it nearly worthless for the
revision-heavy workflow that motivated it.

**Decision: a durable document version handle is a prerequisite
milestone.** Naming it carefully matters: `document_identity` is an
existing bounded context meaning *the identity of a document's bytes*,
which is precisely what already exists and is not the gap.
Assertions are not implemented until a document can say which document it
supersedes.

Separately, and regardless: **"current" means three different things**
that drift independently - the current assertion, the current document,
and the current representation. A reader-library upgrade produces a new
representation identity for byte-identical content. An assertion pinned
to the representation identity would be **falsely invalidated at scale**
the first time a dependency is bumped. An assertion therefore pins the
**content checksum**, and the implementing milestone must state which
events invalidate it, distinguishing *the bytes changed* from *the reader
changed* from *the representation contract was raised*.

The pin is resolved server-side. It is never accepted in a request body:
an existing invariant forbids a persisting route from accepting
caller-asserted provenance, and the content checksum is one of the fields
it names.

**There is no *stable* single-valued source to resolve it from today,
and that is part of the same prerequisite.** The registry does resolve
one - the checksum of a document's most recent ingestion job, ordered by
id, with no filter on whether that job succeeded - but "most recent
attempt" is not a version handle, and no table holds one checksum for a
document. Its ingestion jobs carry one each, and a document legitimately
accumulates several over its life - that table declines a uniqueness
constraint on `document_id` for exactly that reason. Every canonical
representation and derived set carries one too, and a document
accumulates those as well, one per distinct checksum. A document that has
never been ingested has none at all. "The checksum of document 17" is therefore
not yet a question with one answer. Document version identity must
provide one.

**An assertion never propagates to a successor version by itself.**
Invalidation and inheritance are different questions: invalidation asks
whether an existing assertion still stands, and inheritance asks whether
a new version acquires one. Carrying an assertion onto a re-issued
document is a fresh authored act by a named engineer who has looked at
the new revision - never an automatic consequence of lineage, and never
inferred from two documents sharing bytes. The system declines to
conclude that equal bytes mean the same document; it must equally decline
to conclude that a successor inherits a judgement nobody re-made.

### 10. Lifecycle is append-only, and derived rather than stored

An assertion is immutable once recorded. A revision is a new record; a
withdrawal is a new record that states the previous one no longer stands.
Neither is an edit and neither is a delete.

There is no `status` column, no `is_current` and no `superseded_at`.
Current-ness is a projection over an append-only history, and
applicability is computed on every read - the shape `human_review`
already uses, chosen there precisely so there is no column that can drift
from the truth.

Three outcomes must remain distinguishable: **never asserted**,
**asserted and withdrawn with nothing in its place**, and **asserted and
superseded**. The middle one is not the absence of a record.

**A warning about the word `superseded`.** In `human_review` it is
*derived from position*: the newest review supersedes the rest, by
definition. §5 forbids exactly that rule here. An implementer who reuses
the review projection's idiom because the word matches would reintroduce
the tiebreak this decision exists to prevent. Here supersession is an
**authored act by the original author**, never a consequence of arrival
order.

**Withdrawal and supersession act only on the author's own assertion.**
An engineer may retract or revise what they declared. They may not
retract or revise what somebody else declared - because that would
reintroduce the tiebreak §5 forbids, merely moving it from a clock
comparison to a second human record while producing the identical effect:
one engineer's statement quietly stops being current.

A second engineer who disagrees therefore does the only honest thing
available: they record their own assertion. The pair is a conflict, and
§5 requires it to be surfaced as one.

**Resolving a conflict is a separate governed act, and it is not decided
here.** Naming it is deliberate: this ADR would otherwise have to invent
an authority - a lead engineer, a project owner - that the platform's
role model does not currently have. The cost is recorded below.

**Project lifecycle must not govern assertion lifecycle.** The reviews
table carries no `project_id` at all; adding one to assertions for
listing convenience would let a project's soft-delete hide an engineering
judgement. Record-management lifecycle and engineering judgement
lifecycle are different things.

Two honest qualifications. The reviews table's silence on `project_id` is
not documented as deliberate - the context enumerates three deliberate
absences and this is not among them - so it is read here as a precedent
worth following, not as an intent inherited. And the platform does
already let project lifecycle gate engineering writes elsewhere: adding
an index entry, a proposed claim or a document is refused when the
project is not mutable. **Whether authoring an assertion against an
archived project is refused is therefore a real question, and it is
decided here: it is not.** A judgement about a document's structure is
not a change to the project's contents, and an archived project's
documents remain readable.

### 11. An available action is never derived from a state value

This rule exists because the platform already has a live defect of
exactly this shape, and an assertion lifecycle would inherit it more
acutely.

Two different questions collapse onto one predicate today: *may I change
what this record contains* and *may this record move to state S next*.
They coincide often enough for the conflation to survive review, and
**neither reaches a client**: the state value does, the mutability set
is hand-transcribed on the far side unchecked, and the transition table
is not transcribed at all - the client has two ad-hoc conditionals and
nothing whatever for the one transition a new project actually needs. A client that must decide which action to offer has
exactly one lifecycle input available - the state - and reconstructs from
it the answer to the wrong question.

An assertion is worse exposed, because append-only makes the first
question's answer *always no*. A mutability set would gate nothing, or
gate everything.

Therefore: either the assertion resource **publishes the moves that are
legal for that record**, server-computed in the same idiom as review
applicability, and the client renders what it is told; or the client's
re-implementation of the transition table is pinned by a contract test
against the backend's. Deriving an action from a state value is not an
option.

Correspondingly, a mutability set and a transition table are never given
names that can be mistaken for one another, and one is never exported
while the other is withheld.

### 12. Authorization is a new capability, not a new role

Authoring an assertion requires its own capability, declared per route,
granted to the engineer role. The precedent is direct: recording a review
was split from using the platform precisely so that reading and
authoring could diverge.

Assertion creation is audited with its own action in the closed audit
vocabulary, following the two-record pattern the review context already
uses - the domain record is the system of record, and the audit event is
a parallel trail of the *action*. Audit is never the system of record for
a domain fact: its port is append-only by contract and commits
independently of the transaction that produced the action.

### 13. Any lifecycle or type vocabulary is a named enum in the public schema

A vocabulary a client must transcribe reaches the OpenAPI document as a
**named component schema**, which means it is declared as a string enum
and used directly as a field type.

A `Literal` alias becomes an inline anonymous enum with no name; a plain
`str` with the vocabulary narrated in a field description reaches the
document not at all. Both are invisible to the contract test that
compares frontend vocabularies against backend ones - not merely
unchecked, but *uncheckable without changing the test's mechanism*. Eight closed
frontend vocabularies are in that position today, plus one bare code
constant.

**Two different gaps are easy to confuse here, and the fix differs.** A
vocabulary that reaches the document as a named enum but is simply absent
from the contract test's case list is *checkable but unchecked*, and is
fixed by adding a line to that list. A vocabulary that reaches the
document unnamed or not at all cannot be checked until the backend
declares it differently. The second is the one this decision forbids.

### 14. The test contract a future implementation must satisfy

This decision is only worth recording if the implementation can be held
to it. The following tests are **required**, not suggested. Each names
the layer it belongs to, the invariant it asserts, and - the part that
matters most - **what a failure would mean**, because a test whose
failure nobody can interpret is a test nobody will fix correctly.

Fixtures are synthetic throughout. A workbook shaped like the motivating
one - a title block, a revision line, a row of captions, a row of data -
is sufficient for every case below, and no real project document is ever
committed.

| # | Test | Layer | Invariant | A failure means |
|---|---|---|---|---|
| 1 | An assertion records who, when, which document, which version, which location, which type, which value | domain | every provenance element is present and non-optional | the record cannot answer "why does the system believe this", which is the whole reason it exists |
| 2 | An assertion names its document exactly | domain | the document identifier is mandatory and is not inferred | an assertion could float free of any document |
| 3 | An assertion pins the source version it was made against | domain | the version pin is mandatory | an assertion silently re-targets when the file changes |
| 4 | A locator names worksheet index **and** name, and a well-formed region | domain | both worksheet fields present; region bounds ordered and positive | sheet reordering retargets an assertion while preserving its key |
| 4b | Two engineers declaring the **same** thing about the same region produce two records with different keys | domain | the key is derived from author and instant as well as statement | two independent declarations collapse into one, and a disagreement that was never resolved reads as agreement |
| 4c | The same record yields the same key when recomputed in another process | domain | the preimage contains nothing ambient - no surrogate, no wall clock read at hash time | the key is stable only inside one database, so a downstream stage that hashes it is reproducible in one deployment and not across two |
| 4d | Two assertions by the **same** author about the same region within one tick of the stated granularity are either impossible or distinguishable | domain | the stated granularity either makes the collision unreachable, or the two records remain distinct - neither is discarded, and neither is chosen over the other | the one collision §3 names as unclosed is closed silently, or not at all, and nobody notices which |
| 5 | The author is taken from the authenticated identity | service | a caller-supplied author is **refused**, not merely ignored - note that no schema in this repository currently sets `extra="forbid"`, so this does not come free by following `human_review` | a caller can claim to be somebody else |
| 6 | The instant is injected, never read from the ambient clock | service | the same inputs and the same clock produce the same record | the record is not reproducible, and tests become time-dependent |
| 7 | The type vocabulary is closed and cannot be extended at a call site | architecture | the enum's members are pinned by an explicit list | engineering semantics enter one plausible member at a time |
| 8 | The asserted value is typed, and no free-text field exists | architecture | no `label`, `note`, `description` or equivalent column | prose becomes the place meaning is smuggled in |
| 9 | Supersession appends; it never edits | domain + persistence | the prior record is byte-identical afterwards | history is destroyed and the trail cannot be reconstructed |
| 10 | Withdrawal appends, and is distinguishable from never-asserted | domain | three outcomes remain distinct | a retracted statement reads as though it was never made, or as though it still stands |
| 11 | Withdrawal and supersession act only on the author's own assertion | service | another author's attempt is refused | the tiebreak §5 forbids returns through a side door |
| 12 | Two contradicting assertions both remain readable, and the pair reports a conflict | domain | conflict is computed on read and never resolved | an engineering disagreement is hidden behind a timestamp |
| 13 | A re-uploaded document does not inherit assertions | service | assertions do not propagate across document identities | a judgement is attributed to a document nobody examined |
| 14 | An assertion whose pinned version is not current reports a distinct state and does not resolve | domain | staleness is a state, not an absence | a stale assertion is served as though it were current |
| 15 | An assertion cannot be constructed as, or converted into, evidence | architecture | no import path, no shared type, no shared table | the fifth kind of statement collapses back into the second |
| 16 | Extraction output is unchanged by the presence of any assertion | integration | byte-identical evidence with and without assertions present | human judgement has become an input to the deterministic pipeline |
| 17 | The assertion context is named in the deterministic-context list and in the truth-boundary invariant's forbidden set, and that invariant's scan set is widened to cover both contexts of the spreadsheet family | architecture | the context is named where a name is required, and the scan reaches the families that would import it | the boundary is silently unconstrained - no test turns red |
| 17b | The interpretation-name and engineering-name scans are widened to cover the assertion context's directory | architecture | a type member named for a role rather than a position fails a test | §6's rule is prose only, and the existing scan stops at four spreadsheet packages - so the one fence between this context and an ontology does not reach it |
| 17c | An assertion cannot be constructed as, or converted into, a context item for a prompt | architecture | no import path from the assertion context into context assembly or prompt building, and no adapter between the two | §8 claims this is structurally impossible; today it rests on `GovernedProvenanceView` requiring two fields an assertion lacks, and §3 makes one of them - a key - something an assertion now has |
| 18 | Whatever lifecycle or type vocabulary a client must transcribe reaches the public schema as a named enum | contract | the generated document declares it by name | the frontend transcription becomes uncheckable, joining the eight vocabularies already in that position |
| 19 | Authoring requires its own capability, and every route declares it | security | an actor without the capability is refused | authoring is available to any authenticated user, as it is today on fifteen routers |
| 20 | Every authoring act produces an audit event | integration | the domain record and the audit event both exist | the action is invisible in the trail even though the record is visible |
| 21 | Project lifecycle does not gate assertion authorship or readability | service | an archived project's documents still accept and return assertions | record administration silently governs engineering judgement |

Tests 15, 16 and 17 are the ones that keep this decision honest over
time. The rest can be re-derived from the model; those three are the
only defence against the boundary eroding quietly.

---

## Consequences

### Good

- The fifth kind of statement is representable, and is representable
  **without** weakening any of the four boundaries that already exist. A
  human declaration and a parser observation cannot be confused, because
  no field exists in which one could become the other - the same
  mechanism that separates a review from a semantic statement.
- The question *"who said this, when, about which version of which
  document, at which location, and is it still current?"* becomes
  answerable in one record for the first time. A human author is not
  unprecedented - `GraphProvenance` already carries the reviewer who
  authorised a promotion - but that names the person who *judged* a
  statement the pipeline produced. What no model does is both at once: record a person as
  the *origin* of a statement **and** carry the location in a source
  that the statement is about. Locators are plentiful; authored origins
  are not; the two never meet on one record.
- Engineering disagreement becomes visible rather than resolved by
  timestamp.
- Determinism is preserved in the strong sense. Extraction remains a pure
  function of bytes and versioned rules; a consuming stage that honours
  an assertion remains a pure function of bytes, rules **and a named,
  identified declaration**.
- The prohibition on engineering semantics becomes executable at the new
  boundary, where it is currently unenforced.

### Costs and risks

- **The feature is gated on a prerequisite that is larger than it is.**
  Document version identity touches the upload path, the registry and
  every consumer of `document_id`. This ADR makes that dependency
  explicit rather than discovering it during implementation.
- **A per-sheet manual declaration does not generalise.** A versioned
  rule can be evaluated against the reference corpus, improved once for
  every workbook, and measured. An assertion is unversionable,
  unmeasurable, and helps exactly one document. This is a real cost and
  the Rejected Alternatives confront it.
- **The type enum is a standing invitation.** Every future request will
  arrive as "just one more member", and the path from a position to a
  role is short. The fitness function in §6 is the only thing between
  this context and an ontology.
- **"This system does not store assertions" becomes false** where it is
  printed in two domain modules. Those sentences are scoped to the
  evidence contexts and remain true there, but they must be amended to
  say so, or code and documentation disagree on arrival.
- **Denormalised author details are immutable copies**, so no
  account-level erasure path reaches them. This is already true of
  reviews and audit events; assertions extend the exposure.
- **An assertion by a departed author cannot be retired.** Withdrawal is
  author-only (§10) and there is no edit and no delete, so a wrong
  assertion from someone who has left stands until conflict resolution
  exists as a governed act. A second engineer can contradict it visibly;
  nobody can remove it. This is the price of refusing a silent tiebreak,
  and it is preferred to the alternative - but it is a real cost and it
  will be felt.
- **Sparse rows make existence-checking ambiguous.** A blank row is never
  materialised, so "this row is not in the representation" and "this row
  is visibly blank" are the same observation. A validator must not reject
  a legitimate assertion on that basis.

### Debt recorded, not paid

- **Document lineage does not exist.** Named here as a prerequisite; not
  designed here.
- **Nothing reads a canonical workbook back over the API.** There is no
  spreadsheet router. An assertion interface has nothing to point at and
  no read path against which to validate a locator. Whatever milestone
  ships assertions must also ship that read.
- **The consuming stage is not designed.** §7 fixes how such a stage
  composes its identity; it does not authorise one, and header
  determination remains out of scope.
- **A fourth live defect is described in §11** - the conflation of
  content mutability with transition legality, which today leaves a
  newly created project offering one lifecycle control, guaranteed to
  fail. It is named there as the rationale for §11's rule rather than
  handed off, so it is not counted among the three below.
- **Three pre-existing defects were found during this investigation and
  are not fixed here**, being unrelated to the decision: a
  caller-supplied reviewer name that becomes a stored fact's chain of
  custody; fifteen routers carrying no authorization dependency at all;
  and an
  evidence validator that checks coordinates without checking that the
  text at them is the text recorded. The third is a missing backstop
  against an extractor defect rather than a way in - that route accepts
  no caller-supplied evidence. They are reported to the milestone that
  found them.
- **Two fitness-function scope gaps.** The engineering-identity fence
  predates ADR-0034 and does not name the spreadsheet contexts; the
  truth-boundary invariant likewise. Neither is breached today. Both
  would let a future breach pass every test in the repository.

---

## Rejected Alternatives

### Extend `human_review` with a new target type or decision

Rejected, and it is the alternative that most deserves a precise
refusal, because it is the obvious move.

A review's snapshot requires nine mandatory pipeline-shaped columns, all
`NOT NULL`, none of which a structural statement has. Storing one means
writing invented values into columns that exist to be trustworthy - the
precise failure the spreadsheet evidence context refused when it declined
to reuse page-shaped provenance for a cell. The decision vocabulary is
closed at three members and guarded by test, so withdrawal cannot be
expressed. The target is a single opaque key with no room for a
locator, and its one type member names what kind of *artefact* is
reviewed rather than what kind of statement is being made - so two
assertion kinds about one region would collide. And the
existence check that makes a review meaningful has no referent for a
structural locator.

Most fundamentally: **a review names something the pipeline produced and
judges it; an assertion states something the pipeline did not produce.**
Merging them collapses, from the human side, the distinction the truth
boundary maintains from the machine side.

### Attach the assertion to existing provenance

Rejected outright, though **not** on the strength of the existing
fitness functions. The two fences that forbid a user column and an
identity import name seven contexts and six model files, and neither
spreadsheet context is among them - so attaching an author to *workbook*
provenance, the only provenance a workbook assertion would plausibly
attach to, would fail no test in the repository today. That gap is
recorded above; it is not the reason this is refused.

The consequence beneath the tests is the one that matters: a canonical
representation and an evidence set are pure functions of bytes and
versioned rules, and two runs must compare equal. A human field either
breaks that equality or makes the artefact's identity a lie. Running the
pipeline twice under two logins would produce two different artefacts.

This is also the only alternative with a **live** path from a human
statement to apparent machine evidence: the Engineering Index is
caller-writable, has no capability gate and no author field, and its
entries are rendered to the user as the evidence that justified
retrieving a document - with nothing distinguishing a typed entry from an
extracted one.

### A document-generic assertion context spanning all source families

Rejected as specified; adopted only in its single-family form.

A locator general enough to address a PDF page, a worksheet region and a
drawing at once must be either an opaque string that validates nothing,
or a union of page-shaped and cell-shaped fields with half of them null -
and the second is the invented-values failure again. It also re-merges
the two source families that ADR-0034 forked at the root and that the
spreadsheet context's own boundary tests keep apart.

The name `DocumentAnnotation` is independently rejected: *annotation*
already means corpus ground truth in the evidence-evaluation context, and
a second meaning would make the word ambiguous permanently.

### A repository-resident, version-controlled declaration file

Rejected for this requirement; recorded because it is the system's only
*existing* model of a human saying what a document contains, and it is
genuinely better in two respects - it is reviewed as code, and a semantic
leak would be caught in review.

It fails on three counts that this requirement cannot give up: nothing
writes it at runtime, it records no author, and it cannot represent two
people disagreeing. It remains the right answer for curated declarations
that apply across documents; it is the wrong answer for a per-document
statement made by a named engineer about an uploaded file.

### Do nothing, and answer the header question with a versioned rule

Rejected as a *complete* answer, and partially adopted.

ADR-0034 asked for a rule, not a declaration, and the argument is
strong: a rule is versionable, measurable against the reference corpus,
improvable once for every workbook, and carries no human into the
pipeline. A manual per-sheet declaration is none of those things, and
putting the platform's structural understanding in a text box is a real
regression against that ambition.

It is rejected as a complete answer for one reason, and the motivating
workbook is the evidence: **the file gives two contradictory answers
about itself.** Its autofilter names one row; its print titles name a
range. A rule can be wrong; a rule cannot be right here, because the
document does not contain the information the rule would need. As
ADR-0034 itself put it, *"a guess that cannot be checked will be wrong
silently, on one sheet in fifty"*, and *"a wrong answer is worse than a
visible error in this domain."*

The honest sequence is therefore **rule first, assertion as the recorded
override where the rule abstains** - and an abstention is a legitimate
outcome, not a failure. This ADR defines what that override is and how it
is recorded. It does not authorise the rule, the
stage, or any machine determination of a header. A person declaring
which row plays a distinguished role is the thing this ADR is for; a
rule concluding it is the thing still out of scope.

---

## References

- [ADR-0002](0002-engineering-index-vs-project-knowledge-graph.md) - the index as
  an unreviewed lead, and why an uninterpreted locator carries no trust.
- [ADR-0023](0023-human-review-append-only-judgement.md) - append-only
  judgement; the caller-supplied reviewer field rejected; *"nothing about
  human judgement may become an input to"* the deterministic pipeline.
- [ADR-0029](0029-deterministic-engineering-reasoning-foundation.md) - a
  new kind of statement gets a separate type in a separate context, never
  a flag.
- [ADR-0031](0031-deterministic-shared-structural-location-reasoning.md) -
  derived vocabularies asserted disjoint from governed ones.
- [ADR-0032](0032-upstream-identity-in-derived-set-reuse.md) - composed
  identity, and identity copied from upstream rather than caller-supplied.
- [ADR-0033](0033-pseudonymous-reference-corpus-provenance.md) - a
  provenance field's name must honestly describe what it holds.
- [ADR-0034](0034-spreadsheet-canonical-representation.md) - the
  spreadsheet fork; *"there is nowhere to record a header"*, and the debt
  this ADR answers in part.
- [Architecture Freeze AF-01](../architecture_freeze_af01.md) - the
  deterministic-context list, the truth boundary, and the provenance
  invariants this decision is constrained by.
