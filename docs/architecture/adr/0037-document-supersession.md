# ADR-0037: Document Supersession

## Status

Accepted. Introduced by the *Document Supersession* milestone, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted. No fitness function is deleted and none
is loosened.

**The decision is accepted; the implementation is deliberately deferred.**
No supersession context, table, port, route, capability, audit action,
vocabulary or frontend control is authorised here, and none was created.
Every normative statement below describes the shape a future
implementation must take. Where a section instead describes the
repository as it stands - §3, §16, §17, §24, the Debt Register - it says
so.

**This milestone did change production code**, for one reason: a
document was destructible, and a decision about which document supersedes
which is worthless if either endpoint can be deleted out from under it.
Two model modules were modified, one Alembic migration was added - which
runs against real databases and is production code, not a test - and one
test module was added. §24 records all four. Beyond those, this ADR
itself, and its row in the ADR index, nothing in the tree was touched.

AF-01 §22 sorts a change into one of two categories: ordinary evolution,
or a change requiring an ADR that names the invariant it alters. This
change is **neither** - it alters no AF-01 invariant, and §22 has no
third category for it. It is recorded as an ADR because CLAUDE.md §11
requires one for a new bounded context, and because it answers a question
two accepted ADRs deferred in writing.

**This ADR discharges the prerequisite ADR-0035 §9 named** - *"Assertions
are not implemented until a document can say which document it
supersedes"* - by deciding **what such a statement is and who may make
it**. It does not build one. ADR-0036 §27 states the position precisely:
after that milestone *"a document still cannot say that"*. It still
cannot after this one. What changes is that the design is settled, and
the next milestone implements a decision rather than inventing one under
delivery pressure.

**It answers ADR-0036 §5's deferred question**, which was recorded
there as *"unresolved rather than settled by default"*: whether document
lineage is machine-established or human-declared. The answer is
human-declared, and §6 develops the argument from the repository rather
than from preference.

Adds no governed vocabulary, no graph capability, and no engineering
semantics.

**On evidence.** Every claim below about the repository as it stands is
cited to `path:line` and was read before it was written. Line numbers are
to the working tree at commit `2849433` plus the two repairs §24
describes. Where this ADR reasons past what the code states, it says so.
The two are deliberately not blended.

---

## 1. Context

### What forced the decision

Two accepted ADRs stop at the same sentence.

ADR-0035 accepted a fifth kind of statement - a named engineer declaring
something about the structure of a specific version of a specific
document - and deferred its implementation on one prerequisite, stated in
its §9: *"A durable human record cannot be built on an identity that is
not durable."* It named two halves of that prerequisite. ADR-0036
delivered the first: a document now records its own content identity at
creation (`app/models/document.py:167-181`), so
`(document_id, content_checksum)` is a pair a reader can resolve. The
second half it declined:

> **Recorded as deferred, not answered:** whether document lineage is
> machine-established or human-declared. Until it is answered, two
> uploads of the same drawing are two documents (§12), and nothing
> concludes otherwise.
>
> - ADR-0036 §5

So an assertion can now pin a version durably, and still *"dies with its
document when the file is re-issued as a new upload, because nothing
relates the two"* (ADR-0036 §27). The third property ADR-0035 named as
making this a different kind of statement - *"its whole value is that it
survives a revision"* - remains unfounded.

### The situation in the field

A substation drawing is re-issued. Revision B arrives as a new upload and
becomes a new `documents` row with a new id, unconditionally
(ADR-0036 §12). The engineer who declared where revision A's header sat
looks at revision B and finds nothing carried across - correctly, because
ADR-0035 §9 forbids inheritance - but also finds no way to say that the
two are the same drawing at two moments. To the platform they are two
unrelated files that happen to have similar names.

Nothing in the repository can state the relation. ADR-0036 §1 measured
it: a search for `supersedes`, `superseded_by` and `previous_document_id`
returns hits only in human review's own vocabulary and in the tests that
forbid those names on `documents`. That measurement still holds. The
column list in `app/models/document.py:91-181` contains no such field,
and `tests/architecture/test_document_version_identity_architecture.py:308`
is a test whose whole purpose is to keep it that way until this question
is answered.

This ADR answers it.

---

## 2. Problem

Stated exactly:

> A logical document is re-issued. The platform holds two `documents`
> rows, each with its own content identity, each with its own derived
> artefacts, and **nothing that can say the second one replaces the
> first**. Every mechanical signal that might establish the relation is
> already refused somewhere in this repository, and the only remaining
> source - a person - has no place to put the statement.

Four consequences follow, and each is independently a defect.

1. **A human assertion cannot survive a revision**, which is the property
   ADR-0035 §9 named as making it worth building at all.
2. **An engineer reading revision A has no signal that revision B
   exists.** The platform holds the information and cannot express it.
3. **Nothing distinguishes a re-issue from a duplicate from the same
   drawing filed twice.** The content identity context says this
   explicitly about itself: the question is *"about the documents, not
   their bytes - and answering it here would be inventing a policy nobody
   has stated"* (`app/domain/document_identity/content_identity.py:15-21`).
4. **A future milestone will invent the semantics under delivery
   pressure**, and the most convenient invention - a `superseded_by`
   column - is the one §11 shows cannot represent the common case.

There is also a *non*-problem this ADR must resist solving. Whether two
documents describe the same equipment is cross-document engineering
identity, and it is refused in four places. §4 marks it out of scope by
name.

---

## 3. Existing architecture

What already exists, and what it constrains.

### The document row, after ADR-0036

`documents` carries `id`, `project_id`, `filename`, `file_path`,
`file_format`, `category`, `revision`, `project_name`, `scope`,
`uploaded_at`, and the three identity columns ADR-0036 added -
`content_checksum`, `content_checksum_algorithm`, `content_size_bytes`,
all nullable (`app/models/document.py:91-181`). There is no relation
between two documents of any kind, in either direction.

`id` is now `AUTOINCREMENT` on SQLite and the project relationship no
longer cascades; §24 records why.

### Append-only judgement, and its supersession model

`app/domain/human_review/` is the repository's existing append-only
statement context, and it is the nearest precedent. Eleven modules, a
port with `append` and four reads and no update or delete (AF-01 §8), a
closed three-valued decision vocabulary, and a projection that derives
currentness rather than storing it:

> ``superseded`` is derived from position, not stored: every review
> except the newest has been superseded by definition. A stored flag
> [...]
>
> - `app/domain/human_review/review_projection.py:115-122`, applied at
>   `:146` as `superseded=index > 0`

That is exactly the idiom §12 forbids here, for exactly the reason
ADR-0035 §10 gave when it flagged the word as a hazard. §9 returns to it,
because the collision is in the vocabulary as well as in the logic.

### The identity primitive, and what it is for

`app/domain/artifact_identity/` composes every deterministic identity as
`H(contract, kind, upstream, local)`. ADR-0035 §3 established that a
human declaration must **not** enter that chain, because `RECOMPUTE` -
one of the reuse outcomes - has no meaning for something nothing can
re-derive. That reasoning is adopted here unchanged and §8 restates its
consequence for a supersession statement.

### The typed-failure / exception line

The Document Identity context draws a line this ADR reuses in §10:

> A **failure reason** (``ContentIdentityFailureReason``) describes
> something true about a document [...]
> An **exception** here describes a caller that asked for something
> incoherent [...] That is not a fact about any document, and returning
> it as a failure reason would invite the caller to persist it as though
> a document were at fault.
>
> - `app/domain/document_identity/document_identity_exceptions.py:4-18`

### Retrieval's refusal to merge

`app/services/governed_retrieval_service.py` states, in its own module
docstring, the property §16 is about:

> **No merging across documents.** Two governed assets that share a
> label are two answers, and the outcome says ``MULTIPLE_MATCHES``.
> Deciding they are the same transformer is cross-document entity
> resolution, which no governed rule performs.
>
> - `app/services/governed_retrieval_service.py:36-39`

### Capability and audit vocabularies

Both are closed enums. `Capability` has six members
(`app/domain/identity/identity_roles.py:40-74`); `AuditAction` has
fifteen (`app/domain/audit/audit_models.py:30-66`), and **one of them is
already called `ENGINEERING_REVIEW_SUPERSEDED`** (`:59`). §9 and §19
treat that as a naming constraint rather than a coincidence.

---

## 4. Terminology

Ten terms, kept apart on purpose. Conflating any two of them is the
failure mode this ADR exists to prevent. The first three already exist;
the rest are introduced, refused, or marked out of scope here.

| Term | Definition | Identity basis | Author | Deterministic | Lifecycle | Conflict model | Evidence | Currentness |
|---|---|---|---|---|---|---|---|---|
| **Content identity** | the identity of one exact sequence of stored bytes | SHA-256 over the authoritative source bytes | none - a versioned rule | yes, fully | written once at creation, never updated | none possible: two runs over one file agree or the file changed | `app/domain/document_identity/content_identity.py:81-119`; ADR-0036 §7 | not a currentness concept at all |
| **Document version** | one logical document as it stood for one exact content identity | the pair `(document_id, content_checksum)` | none | yes | immutable; a new version is a new pair | none | ADR-0036 §6; `app/models/document.py:167-181` | **no ordering exists** - ADR-0036 §13 |
| **Source-family lineage** (the collision) | which source family a document belongs to: the PDF family or the spreadsheet family | the classified `file_format`, via `lineage_for_format` | none - a versioned rule | yes | recomputed per pipeline run; nothing persists it | none | `app/services/document_pipeline_service.py:124-156`; ADR-0034 §1 | not a currentness concept |
| **Supersession** | a named engineer's statement that one document version re-issues another | its own key, over both endpoints **and** the author **and** the instant (§8) | a named person | **no** - nothing in the bytes entails it | append-only; a withdrawal is a new record (§13) | **computed on read, never stored, never resolved** (§12) | this ADR; nothing implements it | derived per read, and may be a fork, a cycle or a contradiction |
| **Replacement** | what would happen to derived artefacts if a document were operationally replaced | n/a - an operation, not a record | n/a | n/a | defined, built nowhere | n/a | ADR-0036 §14 | n/a |
| **Predecessor / successor** | the two endpoints of one supersession statement | each is a document version: `(document_id, content_checksum)` | inherited from the statement | no | fixed at the statement; never re-pointed | a version may be the endpoint of many statements (§11) | this ADR §7 | neither endpoint becomes "current" or "stale" by being one |
| **Derivation** | an artefact a versioned rule produced from specific bytes | `H(contract, kind, upstream, local)` | none - a rule and its version | yes | replace-on-rerun | none | `app/domain/artifact_identity/artifact_identity_models.py:14-15`; AF-01 §7 | superseded by re-derivation, never by a statement (§15) |
| **Duplicate** | two documents whose bytes are equal | not modelled - equal checksums conclude nothing | n/a | n/a | n/a | n/a | ADR-0036 §16; `content_identity.py:15-21` | **refused**: no deduplication, no upload-time lookup, no `reused` field |
| **Related document** | two documents an engineer would describe as connected for any reason other than one re-issuing the other | **none - OUT OF SCOPE** | n/a | n/a | n/a | n/a | see below | n/a |

**`related document` is out of scope, and the reason is structural.**
Strip away re-issue, filing and equal bytes and the only honest remaining
reason two documents are "related" is that they describe the same
equipment. That is cross-document engineering identity, and this
repository refuses it in four places:

- AF-01 §21 lists *"no cross-document entity resolution"* as a stated
  limit, and adds that AF-AMB-001 *"depends on it being absent"*.
- AF-01 §13: *"Identity is never derived from a label. `TR1` in two
  documents is two `entity_key`s, therefore two `node_id`s, therefore two
  answers."*
- `app/services/governed_retrieval_service.py:36-39` refuses the merge by
  name in its own contract.
- ADR-0036 §26 lists it among the non-goals, as does §26 of this ADR.

A `related_document` relation would be the place that refusal is
reintroduced as a convenience, one plausible pair at a time. It is named
here so that adding one is a visible edit to this table rather than a
field somebody thought was obviously useful.

**The term collision, recorded as a code/documentation disagreement.**
ADR-0036 §4 introduces *lineage* as *"the relation 'this document
supersedes that one'"*, and states that it *"does not exist in the
repository"*. The word does exist in the repository, and means something
else. `DocumentLineage`
(`app/services/document_pipeline_service.py:124-134`) is a live enum
whose own docstring reads *"Which source family a document belongs to
(ADR-0034 §1)"*, with members `CANONICAL_PDF` and
`CANONICAL_SPREADSHEET`. Measured - counting **case-insensitive
substring occurrences**, not matching lines, over tracked `*.py` files
only: the identifiers `DocumentLineage` and `document_lineage` occur
**15 times across 4 files** (`app/routers/documents.py`,
`app/services/document_pipeline_service.py`, and two test modules); the
substring `lineage` occurs **68 times across 13 modules** under `app/`
and 77 times under `tests/`, always in the source-family sense. The
convention matters, because counting matching lines instead gives 60 and
75 - a line carrying the word twice is one line and two occurrences, and
an earlier draft of this ADR reported the line figures as occurrences.
It is fitness-guarded:
`tests/architecture/test_document_pipeline_boundaries.py:504`
(`test_every_lineage_has_a_stage_to_report_a_storage_fault_at`) pins the
enum's coverage.

Under CLAUDE.md §11, code and documentation disagreeing is a bug to be
fixed in the same change. **It is fixed here in the only way available to
a document**: by not adopting the word. ADR-0036 §4's second bullet
should be read as naming the concept this ADR calls **supersession**, and
this table is where the two senses are kept apart. §9 is why the word is
not simply reclaimed.

---

## 5. Who may establish supersession

**Decision: a supersession statement is made by a named, authenticated
engineer, and by nothing else. The platform never concludes it.**

The statement is a declaration in ADR-0035's sense - *"a durable,
attributed, append-only record"* whose author *"is a person, not a
rule"*. It therefore inherits that ADR's whole shape, and §7, §8, §12,
§13 and §18 are that inheritance applied to two document versions instead
of one worksheet region.

Two consequences, stated now because they govern every later section:

- **There is no rule, policy or heuristic that produces a supersession
  statement.** Not at upload, not during ingestion, not in a maintenance
  pass, not as a suggestion a user confirms. §6 is the argument.
- **The author is server-resolved from the authenticated identity and
  denormalised onto the record**, exactly as ADR-0035 §2 requires and for
  the reason ADR-0023 gave: a caller-supplied author is *"a field in
  which a caller could claim to be somebody else."* No request schema
  carries an author field, and supplying one is refused rather than
  ignored.

---

## 6. Why machine establishment is refused

The argument is not that machine establishment is distasteful. It is that
**every mechanical signal available has already been refused in this
repository, individually, for reasons that do not weaken when they are
combined** - and that the repository already applies a test which sorts
this statement onto the declared side.

### The four available signals, and where each is already refused

**Byte equality.** Refused three times, in three different contexts:

- `app/domain/document_identity/content_identity.py:15-21`: *"Identity is
  not deduplication. [...] Whether a repeated upload is a duplicate, a
  legitimate re-issue under a new revision, or the same drawing filed
  against two projects is a question about the documents, not their bytes
  - and answering it here would be inventing a policy nobody has
  stated."*
- `app/domain/document_ingestion/ingestion_models.py:107-108`: *"Identity
  is not deduplication: identical checksums are recorded and nothing is
  concluded from them."*
- ADR-0035 §9: an assertion is *"never inferred from two documents
  sharing bytes"*, and *"the system declines to conclude that equal bytes
  mean the same document"*.

Note what byte equality would establish even if it were permitted: that
two documents are the **same**, which is the one case that is
definitionally *not* a re-issue. Revision B differs from revision A. The
signal is not merely forbidden; it points the wrong way.

**Upload chronology.** Refused by ADR-0036 §13, in terms that leave
nothing to salvage:

> `uploaded_at` remains what it is: **upload chronology**. It says when a
> row was created. It does not say that the file uploaded later is the
> later revision of the same drawing - which is routinely false in
> practice, because documents arrive out of order.

**Filename.** Refused where the checksum rule is declared, and the
refusal is about this exact question:

> a checksum that depended on the filename would answer a question nobody
> asked.
>
> - `app/domain/document_identity/content_identity.py:6-8`

ADR-0036 §10 extends it: the original uploaded filename is excluded from
the identity preimage because *"the same file re-uploaded under a
corrected name would become a different version"*. A filename-similarity
rule would make the inverse mistake - two unrelated drawings from one CAD
template would become a revision history.

**The `revision` column.** It cannot carry this, because nothing writes
it. `revision` is `String(50)`, `nullable=False`, default `"00"`
(`app/models/document.py:125-129`). The upload path constructs a
`Document` without it. It is public on the API
(`app/schemas/document.py:53`) and reaches engineer-facing composed
answers, and `docs/architecture/document_management.md:29` describes it
as *"The document's own revision, as supplied"* - which is false: nothing
supplies it, and every document in the system reads `"00"`. ADR-0036's
Debt Register records this as item (a); the Debt Register below restates
it because a supersession design is exactly where somebody would reach
for it.

Ordering by a field that is constant is not ordering.

### The decisive test, which the repository already applies twice

The four refusals above are individually sufficient, but they are a list
and a list invites the reply "then combine them". The repository supplies
a sharper instrument, and it has already used it on both sides of this
exact line:

> **A derived identity must EXCLUDE the author and the instant. A
> declared statement must INCLUDE them in its identity preimage.**

- ADR-0036 §10 excludes `uploaded_at` because *"a wall-clock reading is
  not a property of the bytes"*, and excludes the uploader because *"it
  would make an artifact's identity a function of a person"* - which
  would mean *"running the pipeline twice under two logins would produce
  two different artefacts"*.
- ADR-0035 §3 includes both, because for a declaration *"the author and
  the instant are not metadata bolted onto the statement; for a
  declaration they are part of what was declared, and putting them in the
  preimage is what makes each one distinct."*

Apply it. Could a supersession statement be produced by a versioned rule
reading bytes? No: §6's first subsection shows the bytes do not contain
the information, and each of the three other signals is refused in the
repository's own words. Is it the same statement when two engineers make
it? No - §12 requires two records, because two engineers disagreeing
about which drawing supersedes which is an engineering disagreement, not
a duplicate row.

So the author and the instant belong in the preimage, and the statement
sorts onto the declared side. **That sort fixes every other property in
this ADR**: it is why identity includes the author (§8), why the
lifecycle is append-only (§13), why conflict is an outcome rather than a
resolution (§12), why withdrawal is author-restricted (§13), why the
context needs its own capability (§18) and its own audit action (§19),
and why it can never be an input to the deterministic pipeline (§15,
§20).

### What is refused alongside it

- **No suggestion.** A "we think B supersedes A, confirm?" control is
  machine establishment with a human's name attached. It moves the
  mistake into a record that says a person decided it.
- **No import.** A lineage relation read from a client's document
  management system is caller-asserted provenance about a governed
  relation, and is refused on the same ground AF-PROV-002 refuses a
  caller-supplied checksum.
- **No backfill.** There is no historical supersession to recover.
  Nothing ever recorded one.

---

## 7. The statement, and what it pins

**Decision: a supersession statement names two document versions - a
predecessor and a successor - and pins both. It carries its author, its
instant, and nothing else.**

### Its shape

| Element | Rule |
|---|---|
| predecessor | `(document_id, content_checksum)` - both halves, mandatory |
| successor | `(document_id, content_checksum)` - both halves, mandatory |
| author | user id, display name, email, role - **copied**, never a foreign key, never caller-supplied (§5) |
| instant | injected, never read from the ambient clock; distinguishing, not decorative (§8) |
| key | derived from the four elements above per §8, and **recorded on the record** so a reader can compare and a withdrawal can name it (§13) without recomputing it; never caller-supplied |
| anything else | **nothing** |

**"Nothing else" governs the supersession statement, not every record in
the context.** A withdrawal is a record of a different kind - it names a
statement, not two documents - and §13 decides what it is and where it
lives. No column on the supersession statement is added, made nullable,
or given a second meaning to accommodate it.

### Both endpoints pin a version, not a document

This is the load-bearing choice, and it follows from ADR-0036 §6: a
document version *is* the pair. An edge between two `documents.id` values
alone would say "this row supersedes that row" while the bytes under
either could differ from the bytes the engineer looked at, and ADR-0036
§18 keeps that possibility live on purpose - out-of-band modification is
*"detectable rather than silently absorbed"*, not prevented.

Pinning both halves means the statement says what the engineer actually
saw: **these exact bytes, filed as this document, re-issue those exact
bytes, filed as that one.** Staleness is then computable in the same way
ADR-0036 §27 made it computable for an assertion - compare the pinned
checksum against the document's recorded one - and a statement whose
endpoint no longer matches reports a distinct state rather than silently
retargeting.

The pin is **resolved server-side and never accepted in a request body**.
AF-PROV-002 names `content_checksum` among the governed provenance fields
a persisting route may not accept
(`tests/architecture/test_architecture_freeze_af01.py:331-339`), and
ADR-0035 §9 already required this of an assertion's pin. A request names
two documents; the server resolves each one's recorded identity from its
row.

### No free-text field

No `note`, `label`, `description`, `reason` or `comment`. ADR-0035 §6
gives the reason and it applies unchanged: `human_review` confined prose
to a comment *"that engineers and auditors read and that no machine
consumer does"*, and a free-text field on a statement about documents is
where `"B supersedes A for the cable schedule only"` gets typed - a
scoped, conditional, engineering-semantic claim in a text box.

### No engineering semantics

The statement says one thing about two files. It does not say that the
equipment in them is the same equipment, that a designation in B
continues one in A, or that anything in A remains true. §4 marks the
first of those out of scope; §15 and §16 are the other two.

### It is a root, not a derivation

ADR-0035 §3's argument transfers exactly. A supersession statement must
not enter the `ArtifactIdentity` chain: that primitive exists to answer
*"does an artifact with this identity exist for this document?"*
(ADR-0032), one of whose outcomes is `RECOMPUTE`, and **nothing can
recompute what a person said.** Entering the chain would also mean
nominating some upstream artefact as the statement's derivation source,
which would assert that the declaration is a function of bytes. It is
not. A supersession statement is a root, like the source.

---

## 8. Identity of a statement

**Decision: a supersession statement is identified by a key derived from
the whole of what was declared - both endpoints, the author, and the
instant - and never from the endpoints alone.**

This is ADR-0035 §3 applied to a two-endpoint statement, and the reasons
carry over one for one.

- **Two engineers declaring the same thing are two declarations.** A key
  over the endpoints alone would collapse them into one record, and §12
  requires them to remain two - because a key that hides a second author
  also hides the case where the second author later disagrees.
- **A lawful declare / withdraw / re-declare sequence must stay
  distinct.** If the first and third records shared a key, a withdrawal
  naming its target by key could not say which one it retracts. A
  withdrawal does name its target by key, and carries a key of its own,
  derived the same way over its target, its author and its instant (§13).
- **The instant must therefore be distinguishing, not decorative.** The
  implementing milestone states its granularity, and adds a tie-breaking
  element if that granularity admits two records from one author about
  one pair within a single tick.

**The tie-breaker is an open design question, inherited rather than
solved.** ADR-0035 §3 examined the two obvious candidates and rejected
both: a database-assigned sequence is stable only inside the database
that issued it, and a random nonce, while recomputable from the record,
*"is not part of what the engineer declared, so it would make the
identity of a declaration depend on a value nobody stated."* That
position is adopted unchanged. This ADR does not name a tie-breaker
either, and the implementing milestone inherits a real design question
rather than a clerical one.

**A database surrogate is not the identity.** A record still carries a
surrogate primary key; that is storage. The identity must be recomputable
*on any machine, in any process, forever* - the property
`app/domain/artifact_identity/artifact_identity_builder.py:4-7` states the
whole chain depends on - because a key nobody can recompute is a key
nobody can compare.

**A supersession statement is addressable and recomputable, and
deliberately not deduplicable.**

---

## 9. Naming, and the words that are unavailable

This section is load-bearing. The repository has refused a name on this
exact ground before: ADR-0035 rejected `DocumentAnnotation` because
*"annotation already means corpus ground truth in the evidence-evaluation
context, and a second meaning would make the word ambiguous
permanently."* The same discipline applies here, and more words are taken
than one would expect.

### `lineage` is unavailable

`DocumentLineage` is a live enum meaning **source family**
(`app/services/document_pipeline_service.py:124-134`), with members
`CANONICAL_PDF` and `CANONICAL_SPREADSHEET`. Measured on the convention
§4 states - case-insensitive substring occurrences over tracked `*.py`
files: 15 occurrences of the identifier across 4 files; 68 occurrences
of the substring across 13 modules under `app/`, and 77 under `tests/`,
every one of them in the source-family sense; and a fitness function
pinning the enum's coverage
(`tests/architecture/test_document_pipeline_boundaries.py:504`).

A `DocumentLineage` that sometimes meant "PDF or spreadsheet" and
sometimes meant "which document supersedes which" would be ambiguous in
the one place ambiguity is most expensive: a failure message an engineer
reads while something is broken.

§4 records the resulting documentation disagreement in ADR-0036 §4 and
resolves it by not adopting the word.

### Three Italian words are unavailable

The frontend is Italian, and three candidate words already carry
engineering-review meaning there:

- **`revisione`** renders *engineering review*:
  `apps/frontend/components/workspace/ReviewPanel.tsx:77` and `:83` label
  the review panel *"Revisione ingegneristica"*, and
  `apps/frontend/lib/contracts/identity.ts:100` renders the audit action
  `engineering_review_recorded` as *"Revisione registrata"*. It also
  separately labels the `revision` column
  (`apps/frontend/lib/contracts/document.ts:130`), which is the `"00"`
  field of §6 - so the word is doubly spoken for, once for a review and
  once for a column that means nothing.
- **`corrente`** is worse than ambiguous, it is ambiguous *across
  domains*. It means the current judgement in
  `apps/frontend/components/workspace/ReviewDialog.tsx:177` and
  `apps/frontend/components/workspace/ReviewTimeline.tsx:39`, and it
  means **rated current**, the electrical quantity, in
  `apps/frontend/lib/workspace/presentation.ts:130`. A supersession UI
  using it for "the current document" would put a third meaning on a word
  that already carries an engineering one.
- **`Revisione superata`** is already rendered, for
  `engineering_review_superseded`
  (`apps/frontend/lib/contracts/identity.ts:101`). The phrase an Italian
  UI would most naturally reach for to say "this document is superseded"
  is the phrase it already uses to say "this judgement was superseded".

**One correction to the received account.** *`supersessione`* is not
taken: a repository-wide search finds zero occurrences. It is simply not
a word this codebase uses, and adopting it would introduce an Italian
coinage for a concept whose English identifier CLAUDE.md §8 requires
anyway. It is not adopted, but the reason is style, not collision.

### `superseded` is half-taken, and the taken half is the dangerous one

`AuditAction.ENGINEERING_REVIEW_SUPERSEDED`
(`app/domain/audit/audit_models.py:59`) is a member of a closed audit
vocabulary. `ReviewSuperseded` is a domain event
(`app/domain/human_review/review_events.py:62-75`). And the review
projection derives the flag from position:

> ``superseded`` is derived from position, not stored: every review
> except the newest has been superseded by definition.
>
> - `app/domain/human_review/review_projection.py:115-116`

ADR-0035 §10 flagged this precisely:

> **A warning about the word `superseded`.** In `human_review` it is
> *derived from position*: the newest review supersedes the rest, by
> definition. §5 forbids exactly that rule here. An implementer who
> reuses the review projection's idiom because the word matches would
> reintroduce the tiebreak this decision exists to prevent.

That warning is inherited in full and is the reason §12 exists as its own
section. **In this context, supersession is an authored act, never a
consequence of arrival order.** An implementer who copies
`review_projection.py` because the word matched would ship
newest-wins with a different table name.

### The chosen words

**The concept is `supersession`.** The context is
`document_supersession`; the record is a **supersession statement**; the
endpoints are **predecessor** and **successor**. The word is kept despite
the review collision because no alternative survives §4's table - the
concept genuinely is supersession, and renaming it to avoid a homonym
would produce the `DocumentAnnotation` failure in reverse.

**The real-world event is a `re-issue`.** The repository's own phrase:
`app/domain/document_identity/content_identity.py:17` writes *"a
legitimate re-issue under a new revision"*, and ADR-0035 §9 and
ADR-0036 §14 both use it. Verified: it appears as an identifier
**nowhere** - the only occurrences in `app/` are that one docstring line.
The word is available and already means the right thing to a reader of
this repository.

### Three naming rules the implementing milestone must follow

1. **No name may be shared with `human_review`'s supersession
   vocabulary.** The audit action is not
   `DOCUMENT_REVIEW_SUPERSEDED`, the event is not `Superseded`, and no
   type is named `SupersededRecord`. §19 names the audit action.
2. **`lineage` appears nowhere in the context**, in any casing, in any
   identifier, and the fitness function of §27 asserts it.
3. **No Italian identifier**, per CLAUDE.md §8. Italian belongs in
   docstrings, in comments, in `aliases` and in rendered UI strings -
   and the rendered strings must not reuse *Revisione superata*.

---

## 10. Cycles

**Decision: a cycle is represented, never rejected at write time. Every
read is total and terminating over a cyclic graph and reports a cycle as
a named outcome. Self-supersession is the one exception and it raises.**

### Why write-time rejection is forbidden

Suppose A supersedes B is recorded, and later B supersedes A arrives.
Rejecting the second declaration decides the disagreement **by arrival
order** - which is ADR-0035 §5's forbidden tiebreak in validation
clothing:

> Newest-wins is correct for `human_review`, because a judgement is
> subjective and the latest one is the operative one. A statement about
> where a header is, is not subjective - exactly one of the two engineers
> is mistaken, and collapsing that into a clock comparison would hide an
> engineering disagreement behind a timestamp.

The same holds here, and more sharply: two engineers who disagree about
which of two drawings is the re-issue have a real disagreement, and the
one who submitted second is not thereby wrong. Refusing their statement
does not resolve the disagreement; it deletes half of it.

There is a second, independent reason. **Write-time cycle detection is
not deliverable under concurrency.** Detecting a cycle means traversing
the existing statements and then writing; two transactions that traverse
before either writes both see an acyclic graph and both commit. Making it
correct means serialising every write against a full traversal, which is
a lock over a relation the platform expects to be small and read often.
A control that is correct only when nobody else is writing is not a
control - the same reasoning `app/services/storage.py:190-193` applies to
a delete whose *"only safety is that its single caller happens to be
careful"*.

### Self-supersession raises

A statement whose predecessor and successor are the same document version
is not contested; it is **incoherent**. There is no engineer who could be
right about it, no second opinion it could be half of, and no reader who
could report it as an outcome.

The repository already draws this line, in the Document Identity
context's own exceptions module: a failure reason *"describes something
true about a document"* and travels as a value; an exception *"describes
a caller that asked for something incoherent"* and is raised, because
returning it as a failure reason *"would invite the caller to persist it
as though a document were at fault"*
(`app/domain/document_identity/document_identity_exceptions.py:4-18`).

Self-supersession is the second kind. It raises a typed error from the
context's own base error, at construction, in the domain - not a
validation message, and never a stored record.

Note what this does *not* cover: A supersedes B while B supersedes A is a
two-record cycle, and both records are coherent statements by different
people about different pairs. Only the degenerate single-record case
raises.

### Every read must terminate

Because cycles are representable, **every traversal in this context is
written against a cyclic graph**, not against a tree that is assumed
acyclic. Concretely:

- No recursive descent without a visited set.
- No read whose termination depends on the data being acyclic.
- A cycle is reported as a **named outcome** on the result, in the idiom
  AF-AMB-001 established for `MULTIPLE_MATCHES`: a first-class member of
  a closed vocabulary, computed before any limit is applied so it cannot
  be truncated away.

### No single-answer accessor

**No accessor shaped `current_version_of(document)` may exist.**
ADR-0036 §13 forbids it by name, and ADR-0035 §5 gives the reason this
ADR adopts as its own:

> A method whose signature returns one answer has already decided there
> is one.

A read returns the statements, the outcome, and - where a chain is
well-formed - the set of versions with no recorded successor. A set, with
its outcome. Never one document.

---

## 11. Forks

**Decision: a supersession statement is a record in its own right. No
column on `documents` can express one, and a fork is why.**

### A fork kills any column design

The obvious design is a `superseded_by` column on `documents`. It is
single-valued, and it physically cannot hold two successors.

Forks are frequent and correct. One drawing is re-issued as two sheets. A
combined cable schedule is split by voltage level. A general arrangement
is reissued as a plan and a section. In each case the honest statement is
that A is superseded by B **and** by C, and an engineer looking for the
current material needs both.

With a column, the second declaration overwrites the first. **The model
then picks a winner through the shape of its storage rather than through
any stated policy** - which is the same failure §10 refuses at write time
and §12 refuses on read, arriving through a third door. Nobody decided
that C wins; a column had one slot.

The inverse case is equally real: two superseded predecessors converging
on one successor, when two drawings are merged into one. A column on the
successor fails identically.

### Therefore

- Statements live in their own table, many per endpoint in **both**
  directions.
- No uniqueness constraint on `(predecessor)`, on `(successor)`, or on
  the pair. Two engineers declaring the same pair produce two records
  (§8), and one predecessor with three successors is three records.
- Reads return sets. A fork is a **normal outcome**, not a diagnostic
  and not a warning.
- `tests/architecture/test_document_version_identity_architecture.py:308`
  (`test_the_document_row_carries_no_lineage_or_ordering_column`) and its
  refused-names list at `:321-327` remain in force **unchanged**. This
  ADR does not authorise adding `supersedes`, `superseded_by`,
  `previous_document_id` or `document_version_id` to `documents`; it
  confirms that they must never be added, and §11 is now the recorded
  reason rather than "lineage is undecided".

---

## 12. Conflict

**Decision: conflict is computed on read, never stored, and never
resolved. This ADR invents no resolving authority.**

ADR-0035 §10 stated the position and explicitly declined to invent one:

> **Resolving a conflict is a separate governed act, and it is not
> decided here.** Naming it is deliberate: this ADR would otherwise have
> to invent an authority - a lead engineer, a project owner - that the
> platform's role model does not currently have.

That is still true. `Capability` has six members
(`app/domain/identity/identity_roles.py:50-74`) and none of them is
"decide between two engineers". Inventing one inside a supersession
milestone would be an authorization model designed as a side effect of a
document feature.

So:

- **Two contradicting statements both remain readable**, and the pair
  reports a conflict as a named outcome.
- **Nothing is silently chosen.** Not the newest, not the highest-ranked
  author, not the one from the same project.
- **No stored flag.** No `is_current`, no `resolved_at`, no
  `winning_statement_id`. Currentness is a projection over an append-only
  history, computed on every read - the shape `human_review` already
  uses, *"chosen there precisely so there is no column that can drift
  from the truth"* (ADR-0035 §10).
- **The shape to follow is the three-valued match outcome**, a closed
  vocabulary with ambiguity as a first-class result, computed before any
  limit is applied (AF-AMB-001, AF-AMB-002).

### The accepted cost, stated plainly

A wrong statement by an engineer who has left the organisation **stands
forever**. Withdrawal is author-restricted (§13), there is no edit and no
delete, and no authority exists to overrule it. A second engineer can
contradict it visibly. Nobody can remove it.

ADR-0035 accepted this cost for an assertion about a header row. **It is
a larger cost here**, and the difference is worth naming rather than
inheriting quietly: an assertion about a header row is a statement about
how to read one region of one workbook, and a wrong one degrades one
parse. A supersession statement is a statement about **which document an
engineer should be reading**, and a wrong one that cannot be removed
points a reader at the wrong drawing, permanently and with a name
attached to it.

It is accepted anyway, for the reason ADR-0035 gave: the alternative is a
silent tiebreak, and in this domain *"a wrong answer is worse than a
visible error"* (CLAUDE.md §16). A contradicted statement is a visible
error. A quietly overruled one is a wrong answer.

**It is recorded as debt.** Conflict resolution as a governed act, with
an authority the role model actually has, is a milestone this ADR names
and does not design.

---

## 13. Withdrawal and correction

**Decision: the lifecycle is append-only. A withdrawal is a new record. A
correction is a withdrawal plus a new statement. Both act only on the
author's own statement.**

This is ADR-0035 §10 applied unchanged.

- **Immutable once recorded.** No edit, no delete, no `UPDATE` against a
  recorded statement.
- **No `status` column, no `is_current`, no `superseded_at`.** Currentness
  is derived on read.
- **Three outcomes stay distinguishable**: *never declared*, *declared and
  withdrawn with nothing in its place*, and *declared and replaced by a
  later statement from the same author*. The middle one is not the
  absence of a record.
- **Author-restricted.** An engineer may retract or revise what they
  declared. They may not retract or revise what somebody else declared -
  because that reintroduces the tiebreak §12 forbids, *"merely moving it
  from a clock comparison to a second human record while producing the
  identical effect: one engineer's statement quietly stops being
  current"* (ADR-0035 §10).
- A second engineer who disagrees records their own statement. The pair
  is a conflict, and §12 requires it to be surfaced as one.

### A withdrawal is a second record type, not a supersession statement

**Decision: a withdrawal is its own type, in its own table, in the same
bounded context. It carries the key of the statement it retracts, its own
author, its own instant, and its own key.**

This has to be decided rather than left to the implementer, because §7
gives the supersession statement two mandatory endpoints and no other
field, and a withdrawal has neither endpoint and one target.

The alternative - one table with a kind discriminator - was considered
and is refused. It requires the predecessor and successor columns to
become nullable and a target-key column to be nullable too, so that every
row carries half its columns as `NULL` depending on a flag. That is the
invented-values failure ADR-0035 refused when it declined to store an
assertion in a review's nine mandatory pipeline-shaped columns, and it
would directly contradict §27 row 3, which requires both endpoints to be
mandatory on both sides. ADR-0029 settled the general form, in the words
ADR-0035 §1 quotes: a genuinely new kind of statement gets *"a separate
type, in a separate bounded context, in a separate field, at every layer
it appears"*, and a flag on an existing type was rejected because *"a flag
is a convention, and conventions erode."*

It is a separate **type and table**, not a separate context: a withdrawal
is about a supersession statement, which this context owns, and a context
whose only content was retractions of another context's records would
have no aggregate of its own.

Consequences, stated so they are not rediscovered:

- The context holds **two** tables, not one: statements, and
  withdrawals. §21 states it as a requirement.
- The author restriction is enforced by comparing the withdrawal's
  server-resolved author against the **recorded author of the target
  statement**. It is not enforced by a foreign key, because §7 copies the
  author rather than referencing it.
- A correction is a withdrawal plus a new statement - two records in two
  tables, both appended, neither an edit.
- The projection reads both tables. *Declared and withdrawn with nothing
  in its place* is a statement with a withdrawal and no later statement
  from that author; *never declared* is the absence of both.
- A withdrawal of a withdrawal is not introduced. Re-declaring is what an
  engineer does instead, and it produces a new statement with a new key
  (§8).

**Project lifecycle does not govern statement lifecycle.** ADR-0035 §10
decided this for assertions - *"A judgement about a document's structure
is not a change to the project's contents, and an archived project's
documents remain readable"* - and the same holds here, with an additional
reason specific to supersession: a supersession statement's two endpoints
may be filed against **different** projects, or one may be in the
Canonical Library and the other project-scoped (ADR-0005). A rule gating
the statement on "the project" would have to pick one of two, and neither
choice is defensible.

There is also now a stronger structural reason than ADR-0035 had. §24
records that `Project.documents` carried `cascade="all, delete-orphan"`
until this milestone: a document's existence was coupled to its filing.
It no longer is, and a statement about two documents must not reintroduce
the coupling from the other side.

---

## 14. Supersession is not replacement

**Decision: a supersession statement changes nothing. Replacement, as
ADR-0036 §14 defines it, remains built nowhere.**

The two are easy to conflate and the conflation is the expensive one.

| | Supersession (this ADR) | Replacement (ADR-0036 §14) |
|---|---|---|
| What it is | a statement **about** two document versions | an operation **on** documents and their artefacts |
| Who performs it | a named engineer | nothing - it is specified and unbuilt |
| Effect on stored data | one new row in the statements table - and nothing else anywhere; a withdrawal is one row in the withdrawals table (§13), and neither ever writes a second table | would touch the pipeline, the registry and every artefact table |
| Effect on artefacts | **none** (§15) | none either - ADR-0036 §14 clause 3 |
| Built here | no | no |

ADR-0036 §14 already fixed what replacement would mean, and every clause
survives this ADR unchanged: version A is immutable, version B gets its
own identity, **nothing derived from A migrates to B**, A stays
queryable, and B is re-derived from its own bytes. It also carried
ADR-0035 §9's inheritance rule forward: *"a successor never inherits a
human assertion."*

**What this ADR adds is the missing converse, and §15 is it.** ADR-0036
§14 clause 3 forbids migration *during a replacement operation*. It says
nothing about what a mere *statement* may do, because no such statement
existed to legislate about.

**What is still not decided**, and is named so it is not assumed: whether
a replacement mechanism is ever built, and what it would do beyond what
ADR-0036 §14 specifies. A supersession statement is not a replacement
flow, does not trigger one, and does not make one easier.

---

## 15. Inertness with respect to derived knowledge

**Decision: a supersession statement is inert with respect to every
derived artefact. Nothing is retired, re-pointed, re-attributed,
invalidated or hidden. This is a rule, and it requires a fitness
function.**

### The rule

Recording that B supersedes A changes **nothing** about:

- A's canonical representation, in either source family;
- A's canonical text;
- A's evidence sets, in either source family;
- A's entity sets, fact sets and semantic sets;
- any human review of any of A's artefacts;
- any governed node or edge promoted from A;
- any retrieval result, context package or response that cites A.

### Why it cannot be otherwise

**Every derived artefact is content-addressed to the bytes it came
from.** `source_identity`'s preimage is `document_id`,
`content_checksum`, `checksum_algorithm`
(`app/domain/artifact_identity/artifact_identity_builder.py:156-164`),
and every downstream identity composes from it. There is no key, no
column and no field anywhere in that chain that can express a claim
contingent on a **relation between two documents** - and that is not an
oversight, it is what makes the chain reproducible. An artefact whose
validity depended on a statement somebody might make tomorrow would not
be a function of its inputs.

ADR-0036 §14 clause 3 states the same refusal for replacement, citing
AF-TRUTH-003's *"promotion modifies no artefact"* (AF-01 §20). A
statement is weaker than a replacement operation, so it can do no more.

### `GraphRetirementReason` must not gain a sixth member

`GraphRetirementReason` is a closed five-member enum
(`app/domain/governed_knowledge_graph/graph_lifecycle.py:95-123`):
`REVIEW_REVERSED`, `REQUIRES_REVALIDATION`, `ORPHANED`,
`REBUILD_RECONCILIATION`, `NO_REMAINING_RELATIONSHIPS`. Read what each
one means and the pattern is exact: **every member names either a human
judgement changing, or the deterministic material changing.** Not one
names a relation between documents, because none can.

A sixth member - `SOURCE_DOCUMENT_SUPERSEDED` - would encode a machine
concluding that a human's approved statement no longer holds, because of
a relation between two documents that the machine did not establish and
cannot check. It would retire reviewed knowledge on the strength of one
person's unreviewed declaration. **It is forbidden**, and §27 requires a
test that the enum stays at five.

Note the asymmetry that makes this sharp: the statement that would cause
the retirement is *unreviewed*, and the knowledge it would retire is
*reviewed and approved*. AF-01 §9 freezes the direction -
*"truth must not depend on judgement"* - and this would be worse than
that: truth depending on an unreviewed assertion.

### The converse ADR-0035 left undecided, decided here

ADR-0035 §9 decided one half:

> **An assertion never propagates to a successor version by itself.**
> Invalidation and inheritance are different questions: invalidation asks
> whether an existing assertion still stands, and inheritance asks
> whether a new version acquires one.

It decided **inheritance** - a successor does not acquire a predecessor's
assertion - and left invalidation unanswered in the supersession
direction, because supersession did not exist. Nothing else in the
repository decides it either: ADR-0036 §14 governs a replacement
operation, not a statement.

**This ADR decides it: supersession does not invalidate a predecessor's
derived knowledge, and must be structurally incapable of doing so.**

The reason is the one CLAUDE.md §16 states for the whole platform.
Knowledge derived from revision A was derived from revision A's bytes by
versioned rules and approved by a named reviewer. It remains exactly as
true as it was. *"A conclusion drawn from last year's revision must
remain explainable"* (ADR-0036 §14 clause 4). The engineer who needs to
know that a newer revision exists is served by being **told**, not by
having the older answer removed - and §16 is about how much of that
telling the platform can honestly do today.

### The required fitness function

Prose is not enough here, because the pressure will be constant and each
request will look reasonable. §27 rows 10 and 11 require:

- **No derived artefact of any kind changes when a supersession statement
  is recorded**, asserted end to end over the eight persisted artifact
  kinds plus the governed graph.
- **No supersession value reaches any identity preimage**, asserted
  structurally: no module under any **other** deterministic context
  imports the supersession context - the context is itself a member of
  that tuple (§20), so the scan must exclude its own directory or it
  forbids the context from importing itself - and no identity builder
  takes a supersession argument.
- **`GraphRetirementReason` has exactly five members**, pinned by explicit
  list.

---

## 16. What supersession would do to retrieval

This section raises the stakes and is the reason the decision needed an
ADR rather than a design note.

### What retrieval does today

`TR1` in document A and `TR1` in document B are two nodes **by
construction**. AF-01 §13: *"Identity is never derived from a label.
`TR1` in two documents is two `entity_key`s, therefore two `node_id`s,
therefore two answers."* Both are `ACTIVE`. Retrieval answers
`MULTIPLE_MATCHES`, and says why in its own contract:

> **No merging across documents.** Two governed assets that share a label
> are two answers, and the outcome says ``MULTIPLE_MATCHES``. Deciding
> they are the same transformer is cross-document entity resolution,
> which no governed rule performs.
>
> - `app/services/governed_retrieval_service.py:36-39`

> **Every** resolved asset is traversed, not just the first: two
> documents may each designate a ``TR1``, and answering with one of them
> would be the silent cross-document merge the identity model exists to
> refuse. The outcome reports the ambiguity instead.
>
> - `app/services/governed_retrieval_service.py:210-214`

That refusal is fenced: AF-AMB-001 closes the outcome vocabulary and
AF-AMB-002 computes the outcome before any limit, *"so ambiguity cannot
be truncated away"*. AF-01 §21 records that the absence of cross-document
resolution is what AF-AMB-001 *depends on*.

### What a supersession edge would be

**A supersession edge is exactly what would let the system answer with
one and suppress the other.** Given "B supersedes A", a filter that
excluded superseded documents' nodes would turn `MULTIPLE_MATCHES` into
`SINGLE_MATCH` and hand back B's `TR1` as the answer.

That is not an improvement to retrieval. It is **the platform deciding an
engineering question it currently, deliberately, declines to decide** -
and deciding it on the strength of one person's unreviewed declaration
about two files. Supersession converts a refusal-to-guess into a guess.

This ADR therefore states the rule and its fitness function:

**No retrieval, context assembly or reasoning path consumes a
supersession statement. Nothing filters, ranks, orders, excludes or
prefers by it.** The supersession context is not importable from
`governed_retrieval`, `context_builder`, `engineering_reasoning` or
`engineering_response`, and §27 asserts it.

### Two facts that constrain any future consumer

Even a milestone that decided to surface supersession honestly - not
filtering, only telling - would find the surface missing. Two
measurements, both verified, both recorded here so a future design starts
from them:

**Neither warning vocabulary has a slot for a stale source.**

- `ContextWarningCategory` is closed at six members - `BUDGET_EXCEEDED`,
  `ITEM_DISCARDED`, `AMBIGUOUS_RETRIEVAL`, `MISSING_QUANTITIES`,
  `MISSING_RELATIONSHIPS`, `PARTIAL_COVERAGE`
  (`app/domain/context_builder/context_builder_models.py:92-111`).
- `EngineeringWarningCategory` is closed at eight -
  `INSUFFICIENT_EVIDENCE`, `PARTIAL_CONTEXT`, `AMBIGUOUS_KNOWLEDGE`,
  `CONFLICTING_KNOWLEDGE`, `PROVIDER_WARNING`, `UNKNOWN_CONTENT`,
  `LIMITED_RESPONSE`, `UNSUPPORTED_RESPONSE`
  (`app/domain/engineering_response/engineering_response_models.py:136-160`).

**There is today no way to tell an engineer that a citation came from a
superseded document.** Not a filtered way, not a soft way, not a footnote
- no way at all. A milestone that wanted to say it would have to open a
closed vocabulary, which is a visible edit with its own review, and this
ADR does not authorise one. It records the gap so the edit is not made
casually.

**The quantity traversal takes no document filter.**
`GovernedKnowledgeReader.edges_from_subjects`
(`app/domain/governed_retrieval/governed_knowledge_reader.py:132-149`)
accepts `subject_node_ids`, `states` and an optional `kind`, and **no
project or document filter of any kind**. Any exclusion applied to nodes
and edges alone would therefore **leak through the traversal**: a
suppressed subject's relationships would still be reachable from another
subject's edges. A future consumer that filtered at the node level and
believed it had excluded a document would be wrong, silently, and only on
the paths that traverse.

Recorded as a constraint, not as a request to add the filter. Adding one
is a retrieval change with its own contract implications, and §26 lists
it as a non-goal.

---

## 17. Legacy documents

**Decision: a document whose content identity is `NULL` can never be an
endpoint of a supersession statement. There is no workaround, and none is
proposed.**

§7 requires both endpoints to pin `(document_id, content_checksum)`.
ADR-0036 §19 makes a legacy row's identity permanently `NULL`:

> **A legacy row's content identity stays `NULL` for the life of that
> row.** It is never established later, by any route. There is no repair
> path, no admin action, no reconciliation script, and no conditional
> "write it only if it is `NULL`".

and ADR-0036 §27 states the consequence for exactly this kind of
statement: **"A `NULL` identity is not a match."** ADR-0036 §19 states
the matching rule generally: *"Two `NULL`s are never the same unknown.
Any comparison, lookup or reuse check must require a real digest on both
sides."*

### The consequence, stated without softening

**The documents most likely to have revision history are structurally
excluded from supersession, permanently.**

Every document already in a deployment when ADR-0036's migration ran
carries a `NULL` identity for the life of its row. Those are, by
definition, the older documents - the ones that have been re-issued, the
ones an engineer would most want to place in a revision sequence. None of
them can be a predecessor. None can be a successor.

Only a fresh upload creates a pinnable document. And a fresh upload of a
legacy file is a **new document with a new id and its own history**
(ADR-0036 §19), not a repair of the old one - so "upload it again" does
not recover the old row's history; it starts a new one beside it.

### No workaround

Every available shortcut is already refused:

- **Backfill by migration** - refused by
  `test_no_migration_fabricates_an_identity`
  (`tests/architecture/test_artifact_identity_architecture.py:570-594`).
- **Backfill by script** - refused by ADR-0036 §25, because *"it routes
  around a fitness function rather than satisfying it"*, and because it
  would hash
  whatever is at each path *today* and record it as the document's
  original identity.
- **Pin only the `document_id` for legacy rows** - refused by §7. A
  statement that pinned one endpoint and not the other would be two
  different kinds of statement in one table, with a `NULL` column meaning
  "this half is unpinned", and ADR-0035 already named that failure: it is
  writing invented values into columns that exist to be trustworthy.
- **A sentinel checksum** - refused by ADR-0036 §19: it *"would put a
  fabricated digest in a column whose whole purpose is to be
  trustworthy."*

This is a real and permanent loss, and it is accepted on the same terms
ADR-0036 accepted the underlying one: the alternative is a record making
a claim about bytes nobody observed.

### One further ambiguity, inherited

ADR-0036 §19 records that a zero-byte upload also records no identity, so
it is indistinguishable at the column level from a legacy row - and that
for a canonical-library upload no ingestion job exists to distinguish
them either. A supersession implementation inherits that ambiguity
directly: it cannot tell *"this document predates the identity
milestone"* from *"this document is empty"*, and both are equally
ineligible. The refusal is correct in both cases; only the message an
engineer sees would differ, and there is no honest basis for differing.

---

## 18. Authorization

**Decision: declaring supersession requires its own capability, declared
per route, granted to the engineer role. It is not a new role and it is
not `USE_ENGINEERING_PLATFORM`.**

The precedent is direct and is stated in the capability enum itself:
`RECORD_ENGINEERING_REVIEW` was split from `USE_ENGINEERING_PLATFORM`
because the latter *"covers reading reviews: an auditor role that may
read every judgement without passing one is a role this separation
already admits, without any route changing"*
(`app/domain/identity/identity_roles.py:62-67`). The same argument holds
here: reading which documents an engineer declared superseded, and
declaring one, are different acts, and an installation may well want the
second to be narrower.

Rules:

- The capability is a new member of the closed `Capability` enum, and
  adding it is a visible edit.
- **Every** authoring route declares it via `require_capability`. This
  is not automatic: §24 and the Debt Register record that four project
  lifecycle routes and the whole `review_workflow` router declare none
  today, so "following the surrounding code" would produce an unguarded
  route.
- Reading requires `USE_ENGINEERING_PLATFORM`, like the rest of the
  platform.
- **No caller-supplied author**, per §5. A request schema that declared
  one would be refused by test, not merely ignored - and ADR-0035 §14 row
  5 records that this does not come free, since *"no schema in this
  repository currently sets `extra="forbid"`"*.

---

## 19. Audit

**Decision: declaring, withdrawing and correcting a supersession
statement each produce an audit event, under new members of the closed
audit vocabulary, named so they cannot be confused with human review's.**

The two-record pattern is `human_review`'s and ADR-0035 §12 adopted it:
the domain record is the system of record, and the audit event is a
parallel trail of the *action*. **Audit is never the system of record for
a domain fact**: its port is append-only by contract and commits
independently of the transaction that produced the action.

**The naming constraint is concrete.** `AuditAction` already contains
`ENGINEERING_REVIEW_SUPERSEDED` (`app/domain/audit/audit_models.py:59`),
which the frontend renders as *"Revisione superata"*
(`apps/frontend/lib/contracts/identity.ts:101`). A new member must not be
mistakable for it in the enum, in the rendered Italian, or in an audit
export read by somebody who knows neither context. The implementing
milestone chooses the exact spelling; the constraint is that an auditor
reading a filtered trail must be able to tell "an engineer's judgement
was superseded by a newer judgement" from "an engineer declared that one
drawing re-issues another", without opening the code.

`AuditAction` is closed at fifteen members today and its docstring states
that it *"grows when a milestone adds an action worth recording, and each
addition is a deliberate decision rather than a free-text string somebody
typed at a call site"* (`app/domain/audit/audit_models.py:31-39`). These
are such additions.

---

## 20. Determinism and registration

### The context is registered in `DETERMINISTIC_CONTEXTS`

**Decision: `document_supersession` is added to `DETERMINISTIC_CONTEXTS`
when it is built.**

**Not because it derives anything.** It derives nothing: its content is a
person's declaration, reproducible from no input the platform holds.
ADR-0035 §8 already stated the reason the membership is still right, and
it is adopted here verbatim in substance:

> The new context is added to `DETERMINISTIC_CONTEXTS` - not because its
> content is derived, but because that list means *"reaches no LLM"*, and
> `human_review` is in it for the same reason.

`human_review` is the eleventh-listed precedent
(`tests/architecture/test_architecture_freeze_af01.py:545`): an
append-only record of human judgement, in a list whose enforcement
(AF-DET-002) is a ban on importing an LLM runtime.

**This is not optional bookkeeping. A domain directory absent from that
tuple is silently unconstrained** - no test turns red. The list's own
comments record the precedent twice: `canonical_spreadsheet` was named
*"because the local test's forbidden set was narrower than AF-DET-002's,
so a spreadsheet module importing the provider-neutral LLM runtime would
have passed every test in the repository"*
(`tests/architecture/test_architecture_freeze_af01.py:533-538`), and
`document_identity` was added by ADR-0036 for the same structural reason
(`:516-529`).

**A supersession context outside that tuple could import an LLM runtime
with no test failing.** The tuple has fifteen members today
(`:510-555`); this would make sixteen, and any test pinning its length is
updated in the same change.

Two further consequences, both from ADR-0035 §8:

- A supersession statement must be **structurally incapable of becoming a
  context item** for a prompt. Context items require graph provenance - a
  statement key, a review id - and a supersession statement has neither.
  Forcing one would mean fabricating provenance.
- **No supersession prose reaches a model**, which is trivially satisfied
  because §7 gives the record no prose at all.

### AF-TRUTH-002's scan set is still too narrow

**Verified, and it is a live gap this ADR records rather than closes.**

`test_af_truth_002_the_deterministic_pipeline_cannot_read_a_review`
scans exactly **six** contexts
(`tests/architecture/test_architecture_freeze_af01.py:639-646`):
`canonical_pdf`, `canonical_text`, `engineering_evidence`,
`engineering_entities`, `engineering_facts`, `engineering_semantics`.

It **omits `canonical_spreadsheet` and `spreadsheet_evidence`**.

ADR-0035 §8 required that widening - *"that invariant's own scan set must
be extended at the same time, or the addition buys nothing here"* - and
its §14 row 17 made it a required test. **ADR-0036 did not do it**, which
is correct: ADR-0036 was not the milestone ADR-0035 gated that on, and it
said so.

The consequence for this ADR is direct: **a supersession context imported
by either spreadsheet context would fail no test today.** Adding
`document_supersession` to AF-TRUTH-002's forbidden set while the scan
still misses both spreadsheet contexts would leave the guarantee stated
and undelivered for the source family ADR-0035 is about. The implementing
milestone widens the scan and adds the name **in the same change**, or it
delivers neither.

### The statement is reproducible, and the platform is not

The statement is not deterministic in the pipeline's sense and is not
claimed to be. What it must be is **reproducible from its own record**:
the same stored fields yield the same key in another process, forever
(§8, and ADR-0035 §14 row 4c). The instant is injected, never read from
the ambient clock, so the same inputs and the same clock produce the same
record and tests are not time-dependent.

---

## 21. Backend and API implications

Nothing here is authorised to be built. This is what a future milestone
must and must not do.

### What must exist

- A bounded context `app/domain/document_supersession/` following the
  ontology reference pattern (CLAUDE.md §4.3): models, factory, a
  repository **port** as an `abc.ABC`, a projection computing currentness
  and conflict on read, and typed exceptions from a context base error.
- **Two tables**, per §13: supersession statements, with the shape §11
  requires - many rows per endpoint in both directions, no uniqueness
  constraint - and withdrawals, each naming a statement by key. Neither
  table carries a nullable column that exists only to let it hold the
  other's rows.
- An adapter under `app/infrastructure/document_supersession/`.
- One Alembic revision, under ADR-0008's governance, additive, with **no**
  `INSERT`, `UPDATE ... SET`, `DELETE` or `server_default` - the shape
  `test_no_migration_fabricates_an_identity`
  (`tests/architecture/test_artifact_identity_architecture.py:570-594`)
  requires of every migration.
- Routes that declare §18's capability and write §19's audit events.
- Any vocabulary a client must transcribe reaches the OpenAPI document as
  a **named component schema**, per ADR-0035 §13. A `Literal` alias
  becomes an inline anonymous enum with no name and is invisible to the
  contract test; a plain `str` with the vocabulary in a field description
  reaches the document not at all.

### What must not

- **No column on `documents`.** §11, and the refused-names list at
  `tests/architecture/test_document_version_identity_architecture.py:321-327`
  stays as it is.
- **No change to `documents.revision`.** §26.
- **No request body accepts a checksum**, an author, or a statement key.
  AF-PROV-002 names `content_checksum` among governed provenance fields
  (`tests/architecture/test_architecture_freeze_af01.py:331-339`).
- **No storage locator anywhere near the public schema.** AF-SEC-002
  fails any public schema field whose name contains `path`, `directory`,
  `storage` or `file_location`
  (`tests/architecture/test_public_api_boundaries.py:174-200`).
- **No import from the supersession context into any pipeline,
  retrieval, context, reasoning or response context.** §15, §16, §20.
- **No accessor returning one answer.** §10.

### An available action is never derived from a state value

ADR-0035 §11 legislated this against a live defect, and a supersession
resource is exposed the same way: append-only makes "may I change this
record" always *no*, so a mutability set would gate nothing or gate
everything. Either the resource **publishes the moves legal for that
record**, server-computed, and the client renders what it is told; or the
client's re-implementation is pinned by a contract test against the
backend's.

---

## 22. Frontend implications

Nothing is authorised to be built, and three constraints apply to
whatever eventually is.

- **No Italian string reuses `Revisione superata`**, and no control is
  labelled with `revisione` or `corrente` in the supersession sense (§9).
  *Corrente* in particular already carries an electrical meaning in the
  workspace vocabulary
  (`apps/frontend/lib/workspace/presentation.ts:130`).
- **No "current version" control.** Not a switcher, not a badge, not a
  banner. §10 forbids the single-answer accessor that would feed one, and
  a UI that shows one answer has made the decision the backend refused -
  the client being the last place a silent tiebreak can hide.
  A fork, a cycle and a conflict must each be *renderable*.
- **No exclusion in any existing view.** A superseded document does not
  disappear from a document list, a workspace, a pipeline page or a
  citation. §15 and §16.

One existing inaccuracy is worth naming because a supersession UI would
sit next to it: the pipeline page renders `"Non ancora calcolato"` -
*not yet calculated* - for a null checksum
(`apps/frontend/app/documents/[documentId]/pipeline/page.tsx:171-175`),
and ADR-0036 §23 records that the words are false in all three cases
where the fallback still fires. Two of those three are the legacy rows
§17 excludes from supersession; the third is a zero-byte upload, which
§17 records as ineligible for the same reason and indistinguishable from
a legacy row at the column level. So an engineer would see "not yet
calculated" beside a refusal to accept the document as an endpoint, with
nothing connecting the two.

---

## 23. Security

### What a supersession statement is, in security terms

An **attributed assertion by an authenticated user about two rows they
did not create**. It carries no bytes, no path, no secret and no
credential, and it grants no access: a statement about A and B confers
nothing on its author with respect to A or B.

### The realistic abuse, and what bounds it

The abuse is **misdirection**: declaring that a wrong or outdated drawing
supersedes the correct one, so that an engineer reading the platform is
pointed at the wrong document. Four things bound it, and one does not.

- **It is attributed.** The author is server-resolved from the
  authenticated identity (§5) and cannot be forged in a request body.
- **It is capability-gated** (§18).
- **It is audited** (§19).
- **It is inert** (§15). It retires nothing, hides nothing and changes no
  artefact, so the predecessor's knowledge remains readable and citable.
  A misdirection is a misleading statement, not a deletion.
- **It cannot be removed** (§12). This is the bound that fails: a
  malicious or mistaken statement from a departed author stands forever.
  §12 records it as the accepted cost and names conflict resolution as
  the milestone that would close it.

### Untrusted input

The statement carries no content from any document. It names two rows and
records who said so. **No new parsing of untrusted content is introduced
anywhere**, and none may be: a supersession implementation that opened
either file to check anything would have become the machine
establishment §6 refuses.

### Project boundaries

Two endpoints may be filed against different projects, or one may be in
the Canonical Library (ADR-0005). The platform's project-level
authorization is *"filtering, not enforcement"* (AF-01 §21) - any
authenticated engineer may read any project - so a cross-project
statement crosses no boundary the platform currently enforces. It is
recorded as a property of the design rather than presented as safe: when
project-level enforcement arrives, a statement whose endpoints sit in two
projects is a case that authorization model must answer, and this ADR
does not pre-empt it.

---

## 24. What this milestone repaired

This ADR builds no supersession. It did repair two defects found while
establishing whether a document is durable enough to be an endpoint, and
the answer was that it was not. **Four further defects were found in the
tests written to pin that repair** - two in the first attempt and two in
the second - and all four are recorded below, because the shape of them
generalises well past this milestone. Every one was found by a reviewer
rather than by the author.

### `Project.documents` cascaded deletes

`Project.documents` carried `cascade="all, delete-orphan"`. Two
consequences, neither written down anywhere:

- Deleting a project deleted **every document filed against it** - in a
  system where a project is only ever *soft* deleted, precisely so the
  record and everything referencing it survive for audit and restore.
- Merely **detaching** a document from the collection deleted its row.
  Re-filing a document into another project is the most natural way
  somebody would write that, and it would have destroyed the document.

**Removed.** The relationship now takes SQLAlchemy's default
`save-update, merge`: a way to read a project's documents, not a way to
destroy them (`app/models/project.py:149-169`).

### `documents.id` was reusable

`documents.id` had no `AUTOINCREMENT`, so SQLite assigns `max(id) + 1`.
Removing the highest-numbered document hands its id to the next upload,
and **that upload silently inherits the removed document's ingestion jobs
and every derived artefact keyed to the old id** - a different file
acquiring another document's provenance, with nothing anywhere reporting
it.

**Fixed** by `__table_args__ = {"sqlite_autoincrement": True}`
(`app/models/document.py:53-89`) and migration
`8f21c04ab7de_documents_never_reuse_an_id.py`. SQLite cannot alter a
primary key, so the migration rebuilds the table via
`op.batch_alter_table(..., recreate="always")`: Alembic creates the new
shape, copies the rows, drops the old table and renames. No engineering
row is altered in transit and no identity is computed.

**The rebuild is gated on the dialect**, and runs on SQLite only
(`migrations/versions/8f21c04ab7de_documents_never_reuse_an_id.py`,
`upgrade` and `downgrade`). A backend with a real sequence does not reuse
an id, so there is nothing to fix there - and dropping and recreating a
table that twelve others reference, to change nothing, would be the most
destructive no-op in the repository. The first version of this migration
was not gated.

**Two further defects were found in the migration, both by running it.
One is mitigated. The other is reproduced, recorded, and deliberately
left unfixed** - and the reason it is unfixed is the substantive part.

- **A downgrade and a re-upgrade reset the high-water mark. NOT FIXED.**
  `downgrade` rebuilds the table without `AUTOINCREMENT`, which drops the
  `sqlite_sequence` row; `upgrade` then reseeds from the highest
  *surviving* id. A reviewer deleted an id at the head of the table - the
  protection held, and the next id was 4 - then round-tripped the
  migration and watched the next insert receive the deleted id back **and
  reach the victim's ingestion job**. Reproduced, not theorised.
- **Any future migration that rebuilds `documents` silently removes the
  guard. Mitigated, not eliminated.** Alembic batch mode reflects a table
  in order to recreate it, reflection does not carry
  `sqlite_autoincrement`, and `--autogenerate` never emits it. Measured:
  `alter_column`, `drop_column`, and `add_column` under
  `recreate="always"` each drop `AUTOINCREMENT` and ids are reused again,
  while `recreate="auto"` with `add_column` or `create_index` keeps it.
  These are ordinary operations that need never mention ids. The rule is
  now stated at `app/models/document.py:70-79`, and
  `tests/infrastructure/test_the_migration_chain_protects_document_ids.py`
  runs the Alembic chain and fails if the guard is gone.

**And the remedy for that second defect preserves the keyword, not the
guarantee.** Passing `table_kwargs={"sqlite_autoincrement": True}` to a
future `batch_alter_table("documents", ...)` restores the DDL keyword -
and the rebuild still reseeds SQLite's counter from the highest
**surviving** row, so every id spent on a since-removed document is
handed out again. Measured directly: a table at mark 3 with id 3 deleted
keeps the mark through the delete, and a rebuild *that repeats the
keyword* drops it to 2, leaves `AUTOINCREMENT` present in the DDL, and
issues **3** to the next insert. The migration-chain test stays green
throughout, because it asserts only that `AUTOINCREMENT` is in the DDL.

So a future rebuild has the **same effect as the downgrade and
re-upgrade** below, and carrying the mark across one runs into the same
wall: writing it needs a data statement, which
`test_no_migration_fabricates_an_identity` forbids. This is recorded at
`app/models/document.py:81-89` so the next author to rebuild the table
finds it at the keyword rather than here.

### Why the first defect is not fixed: one integrity rule blocked another

**The fix was written, it worked, and it was reverted.** `downgrade`
preserved the mark it found and `upgrade` restored it; the round trip
then held. It was reverted because restoring the mark requires an
`UPDATE` or an `INSERT` against `sqlite_sequence`, and
`test_no_migration_fabricates_an_identity`
(`tests/architecture/test_artifact_identity_architecture.py:570-591`)
fails any migration containing a string constant matching `insert into`,
`update ... set` or `delete from`. With the fix in place the suite read
**1 failed, 492 passed** across `tests/architecture/` - that one failure
and nothing else.

The argument for keeping the fix is available and is refused here.
`sqlite_sequence` holds no identity, no engineering row and nothing this
platform derives; it is bookkeeping SQLite owns, and the test's stated
purpose is that *"an identity computed by a migration would be a claim
about a derivation the migration never saw."* On its purpose, the fix is
innocent.

It is refused anyway, for two reasons.

**The rule is textual precisely so that it cannot be argued with.** Every
exception to it is reasonable in the moment, and the exceptions are what
the rule exists to refuse. Weakening a frozen fitness function - even for
a counter that is not an identity, in a table the platform does not own -
is an AF-01 §22 decision requiring its own ADR. It is not a thing a
migration that needed to go green gets to settle.

**And the available shortcut was worse than the defect.** The same
statement written through SQLAlchemy's query builder rather than as a
string constant would have passed the scan untouched, because the scan
reads string constants. That satisfies the letter while defeating the
purpose, and it is the exact failure ADR-0036 §25 names in refusing a
backfill script: *"it routes around a fitness function rather than
satisfying it."* A repository that evades its own guard once has a guard
that means whatever the next author needs it to mean.

So the guarantee is narrower than it first reads, and the migration now
says so: **an id is not reused while the schema stays at or above this
revision, and while the table is not rebuilt.** Two exceptions, not one.
The first is a downgrade followed by a re-upgrade, which takes two manual
operations in sequence - removing a row by hand, then round-tripping the
migration - and no code path performs either. The second is any future
migration that rebuilds `documents`, which needs no manual step at all
and restores the keyword without restoring the mark, as above.

**The defect is pinned executably rather than only described.**
`test_the_high_water_mark_survives_a_downgrade_and_re_upgrade`
(`tests/infrastructure/test_the_migration_chain_protects_document_ids.py:125-161`,
marked at `:109-124`) is written as the assertion that *should* hold and
marked `@pytest.mark.xfail(strict=True, raises=AssertionError)`. Both
arguments earn their place. **Strict** means that if anybody ever fixes
the migration, the suite reports that this test now passes unexpectedly
rather than staying quietly green. **`raises`** means a failure in the
fixture is an error rather than the expected failure: without it, pytest
reports XFAIL when setup breaks, so the marker would go on recording a
known defect while actually recording nothing at all - a demonstrated
behaviour, not a precaution. It is deliberately **not** written to
assert the broken behaviour - a test that asserted the reuse would go
green on a defect and quietly become its specification, which is how a
defect becomes a feature nobody remembers choosing. Suite state:
**3851 passed, 1 xfailed.**

**The open decision this leaves**, named so a future milestone finds it
rather than rediscovering it: either narrow
`test_no_migration_fabricates_an_identity` to the governed tables it is
actually about - which needs its own ADR under AF-01 §22, and would let
this defect be fixed - or accept the narrowed guarantee permanently.
**This ADR chooses neither.**

**The migration states two honest limits.** An id deleted *before* the
migration ever ran cannot be recovered - nothing can reconstruct a
high-water mark that was never recorded. And the mark binds only while
the schema sits at or above this revision, which is the defect above.

**Why both defects reached a reviewer rather than a test.** Until this
milestone, **no test in the repository executed the Alembic chain**:
`tests/conftest.py:66` builds every test database with
`Base.metadata.create_all`, straight from the models. So the suite tested
a schema no deployment has, and the deployments ran a schema no test had.
Both defects lived entirely in that gap - one in `downgrade`, which
`create_all` has no analogue for, and one in how a *future* migration
interacts with this one. `test_the_migration_chain_protects_document_ids.py`
is now the one place the chain is executed.

**What "verified" means for the rebuild, stated exactly.** Row
preservation was checked by hand, twice, and independently during review
by diffing the resulting schema: rows, `NULL`s, the project foreign key
and all three indexes are preserved, and no other table's foreign key
clause is rewritten. The new migration-chain test now exercises the
chain and the guard, but **not** that diff. A reader should treat the
preservation claim as a reviewed manual result, not as a tested one.

**New tests**, in two modules.

`apps/backend/tests/infrastructure/test_a_document_outlives_its_filing.py`
holds five: four behavioural, pinning the two repairs, and one pinning
the invariant beneath them. Neither repaired behaviour is reachable
through the application today - no route deletes a project row, and
nothing traverses the collection - which is why the tests exist: an
invariant nothing currently exercises is one a future change breaks
without noticing.

`apps/backend/tests/infrastructure/test_the_migration_chain_protects_document_ids.py`
holds three, and is the **only** module in the repository that runs the
Alembic chain. It asserts that the migrated schema declares
`AUTOINCREMENT`, that a migrated database does not reuse a document id,
and that the high-water mark survives a downgrade and a re-upgrade.

### Four defects in the tests, and what each one teaches

Two in the first attempt at that module and two in the second. All four
are recorded because the shape of each generalises, and because a section
whose only job is recording what was built should record how badly it
went before it went right.

**`test_clearing_a_documents_project_leaves_it` was vacuous.** It passed
with the cascade restored. A many-to-one does not load its old value
before it is replaced, so clearing `document.project` on an unloaded
collection fires no removal event and orphans nothing. It is fixed by
loading the collection first - which is also what real code does, since
anything re-filing a document has read the project's documents to find
it - and was then verified to fail with the cascade restored.

**A source scan could not see most of the ways to spell what it looked
for.** The first version of the invariant test parsed `app/models/**`
with `ast` and looked for a `relationship()` whose first positional
argument named `Document`.

That catches the one spelling in the tree today:
`Project.documents` is written
`relationship("Document", back_populates="project")`
(`app/models/project.py:166-169`), positional string and all. It catches
nothing else. SQLAlchemy accepts at least five further spellings of the
same target - the `argument=` keyword, a bare class object, a target left
to be inferred from the `Mapped[list["Document"]]` annotation, a
`backref()` declared from the `Document` side, and `orm.relationship`
instead of a bare name - and each configures a real delete cascade while
returning *no offenders*. A scan that passes because the code is
currently written one way is reporting coverage it does not have, and the
next hand that adds a relationship is under no obligation to pick the
spelling the scan can see.

It is replaced by `test_no_mapped_relationship_can_delete_a_document`,
which asks `Base.registry.mappers` for the **resolved** target and the
**resolved** cascade rather than reading source.

**An earlier draft of this section then claimed that "every spelling of a
relationship is therefore covered." That was false, and it was false
twice over.** The replacement failed three separate times, each found by
a reviewer rather than by its author, and the progression is the honest
content of this subsection:

- **It keyed on class identity.** `relation.mapper.class_ is not
  DocumentRecord` waves through a **second mapper over the same table** -
  a single-table subclass is a different class whose
  `cascade="all, delete-orphan"` deletes the same `documents` rows. A
  reviewer built one and deleted real rows while the scan reported `[]`.
  Fixed by matching on the table:
  `DocumentRecord.__table__ not in relation.mapper.tables`.
- **Its coverage depended on import order.** It inspected whichever
  mappers some earlier import had registered. Bare `import app.models`
  registers **two** - the package re-exports only `Project` and
  `Document` - against **50** once every model module is imported; under
  `conftest` it happened to see 48, and `app/models/spreadsheet_evidence.py`
  was not among them. Fixed by calling `_import_every_model_module()`,
  which walks the package with `pkgutil` first.
- **It missed `secondary=` entirely, and this one needed no cascade at
  all.** A relationship whose **association table is `documents`**
  destroys a `documents` row on ordinary collection removal - that is
  simply what SQLAlchemy does with an association table - so plain
  `save-update, merge` suffices and there is no cascade keyword anywhere
  for a cascade-based check to notice. The guard missed it because
  `relation.mapper.tables` names the **target's** tables and never the
  secondary, so the table check from the first fix could not see it
  however carefully it was applied. Reproduced: a relationship carrying
  cascade `['merge', 'save-update']` deleted a real row while the guard
  returned `[]`. Fixed by checking
  `relation.secondary is DocumentRecord.__table__` **first and
  unconditionally**, before the table check.

Three evasions, of three different kinds, of a test whose entire job is
one keyword argument. The scan it replaced was retired for reporting
coverage it did not have; its replacement did the same thing three times
before it stopped. That is the reason this section refuses to state a
completeness claim at all, and states a blind-spot list instead.

**What it still does not cover**, recorded here because the retired
scan's blind spots are documented above at length and it would be dishonest
to give its replacement none:

- **A database-level `ondelete="CASCADE"`** deletes rows with no ORM
  cascade for this test to find - but only on one of the two directions,
  and the section above gets that direction wrong often enough to be
  worth stating precisely.

  **Twelve foreign keys point *into* `documents`**
  (`child.document_id -> documents.id`). A cascade on any of those
  deletes the **child artefact rows** when a document goes. It can never
  delete a `documents` row, so it is not the invariant this test
  protects - it is the twelve-tables-of-orphans problem, from the other
  end.

  **One foreign key points *out*: `documents.project_id -> projects.id`**
  (`app/models/document.py:97-101`). **This thirteenth key is the only
  database-level rule that could destroy a document** - one keyword on
  one line, and a project delete takes its documents with it, which is
  precisely the cascade this milestone removed from the ORM. Verified
  from the live metadata: all thirteen carry `ondelete = None`, and there
  is no `ondelete` string anywhere in `app/models/` or in any migration.
- **A mapped class outside `app/models/`.** The guard sweeps that package
  with `pkgutil`. Today exactly one declarative base exists and every
  mapped class lives under it, so the sweep is complete - but its
  completeness rests on a placement convention, not on anything the test
  checks.
- **A cascade assigned at runtime**, after mapper configuration.
- **Direct deletion**: `session.delete(document)`,
  `query(Document).delete()`, or raw SQL. This test forbids a
  *relationship* that can delete a document. It does not forbid deleting
  one.

**On PostgreSQL, and the direction of the risk.** It would be easy to
read the above as "inert on SQLite, dangerous on PostgreSQL". That
inverts it. PostgreSQL always enforces foreign keys, and `NO ACTION` -
what all thirteen keys declare today - makes a parent delete **refused**,
not propagated. A Postgres deployment would therefore be *stricter and
safer* than today's SQLite, where enforcement is off and a hand-deleted
document silently orphans twelve tables with no complaint from anywhere.
The prospective risk runs the other way: a future `ondelete="CASCADE"` on
the thirteenth key would be **inert on the only backend anyone tests**,
and live on the first one that enforces. *Limitation: no PostgreSQL
deployment exists in this repository, so this is referential-action
semantics applied to verified DDL, not measured behaviour.*

This is the same lesson ADR-0036 §28 recorded about its own row 9 scan -
*"a scan aimed at the wrong directories is worse than none, because it
reports coverage it does not have"* - arriving three more times in one
milestone, through three different doors. Debt Register item (k) is a
fifth instance, still open.

### Still not repaired, and recorded here

**Foreign keys are not enforced.** SQLite disables foreign key
constraints by default and enables them per connection with
`PRAGMA foreign_keys = ON`. A repository-wide search finds **no such
pragma anywhere**: `app/database/database.py:1-23` creates the engine
with `connect_args={"check_same_thread": False}` and nothing else, and no
event listener sets it.

**Twelve tables reference `documents.id`** -
`app/models/canonicalization.py:160`, `app/models/canonical_pdf.py:65`,
`app/models/canonical_spreadsheet.py:75`,
`app/models/canonical_text.py:58`, `app/models/document_ingestion.py:67`,
`app/models/engineering_entities.py:64`,
`app/models/engineering_evidence.py:59`,
`app/models/engineering_facts.py:69`,
`app/models/engineering_index.py:63`,
`app/models/engineering_semantics.py:64`,
`app/models/proposed_claims.py:126`,
`app/models/spreadsheet_evidence.py:65` - and **not one declares
`ondelete`**; a search for the keyword across `app/models/` returns
nothing.

So a document row removed by hand leaves twelve tables of derived
artefacts pointing at a row that is not there, and the database will not
object. The two repairs above close the paths application code could
take. They do not make the database enforce anything, and the ADR says so
rather than implying an atomicity it has not delivered.

---

## 25. Alternatives considered and rejected

### A `superseded_by` column on `documents`

Rejected, and it is the design that will be proposed first.

It is single-valued and **cannot hold a fork** (§11), which is frequent
and correct - one drawing re-issued as two sheets. The second declaration
overwrites the first, so the model picks a winner through its storage
shape rather than through any stated policy. It also has no author, no
instant and no version pin, so it could not be §5's declaration at all:
it would be an unattributed fact of unknown provenance in a table whose
other columns are either bytes-derived or registry metadata.

`tests/architecture/test_document_version_identity_architecture.py:308`
already forbids it. This ADR supplies the reason that test was waiting
for.

### Machine establishment from bytes, filenames, chronology or `revision`

Rejected; §6 gives the argument in full, with each signal's existing
refusal cited. In short: byte equality is refused three times and points
the wrong way anyway, chronology is *"routinely false in practice"*
(ADR-0036 §13), filename is refused where the checksum rule is declared,
and `revision` is a constant `"00"` with no write path.

### A suggestion an engineer confirms

Rejected as machine establishment with a human's name attached. The
statement's whole value is that a person examined two documents and
concluded; a pre-filled pair converts that into a person clicking
"confirm" on a rule's guess, and the record would say a human decided it.
This is the *"rule first, declaration as the recorded override"* sequence
ADR-0035 endorsed, run backwards: there, the rule abstains and the human
states; here, the rule would state and the human would acquiesce.

### Rejecting a cycle at write time

Rejected; §10. It makes arrival order the adjudicator, which is
ADR-0035 §5's forbidden tiebreak in validation clothing, and it is not
deliverable under concurrency: two transactions that traverse before
either writes both see an acyclic graph.

### Newest-wins, following `human_review`'s projection

Rejected, and it is the one this ADR most expects to be attempted,
because the word matches and the code is already written
(`app/domain/human_review/review_projection.py:115-146`). ADR-0035 §10
warned about exactly this reuse. Newest-wins is correct for a review
because a judgement is subjective and the latest is operative. Which
drawing re-issues which is not subjective: one of the two engineers is
mistaken, and a clock comparison hides that.

### Storing a conflict flag, or a resolution

Rejected. A stored flag can drift from the truth, which is why
`human_review` derives its own on read. And a stored *resolution* would
require an authority to resolve it - §12 records that the role model has
none, and inventing one inside a document milestone is an authorization
model designed as a side effect.

### Letting supersession filter retrieval

Rejected, and §16 is the argument. It converts a deliberate
`MULTIPLE_MATCHES` into a guess, on the strength of an unreviewed
declaration, in the one place the platform's identity model exists to
refuse guessing. AF-01 §21 records that AF-AMB-001 *depends on*
cross-document resolution being absent.

### Retiring a predecessor's governed knowledge

Rejected; §15. It would require a sixth `GraphRetirementReason`, which
would encode a machine concluding that a human's *approved* statement no
longer holds because of a relation between two documents that no rule
established. The direction AF-01 §9 freezes - truth must not depend on
judgement - would be inverted, and inverted onto an *unreviewed*
judgement.

### A generic `related_document` relation, of which supersession is one kind

Rejected. §4 gives the argument: strip away re-issue, filing and equal
bytes, and the only honest remaining reason two documents are related is
that they describe the same equipment - cross-document engineering
identity, refused in four places. A generic relation would be where that
refusal is reintroduced one plausible kind at a time, and it is exactly
the speculative generality CLAUDE.md §12 forbids: it would be designed
against one relation that has a use case and an open set that does not.

### Allowing a legacy document as an endpoint by pinning only its id

Rejected; §17. It makes one table hold two kinds of statement,
distinguished by a `NULL`, and ADR-0035 already named that failure as
writing invented values into columns that exist to be trustworthy.

### Deferring again

Rejected, and it deserves a reason rather than an omission. ADR-0035 §9
deferred to a prerequisite; ADR-0036 §5 deferred this specific question
and recorded it as *"unresolved rather than settled by default"*. A third
deferral would mean the next milestone that needs supersession invents it
under delivery pressure - and §11 and §25 show that the convenient
invention is the one that cannot represent the common case. Deciding
without building is what ADR-0036 §14 did for replacement, and for the
same reason.

---

## 26. Non-goals

None of the following is introduced, designed, prepared for, or made
easier by this ADR. Each is listed because it is a plausible misreading
of what a "document supersession" decision might include.

- **Any implementation of supersession.** This ADR builds none: no
  context, no table, no port, no adapter, no migration, no route, no
  schema, no capability, no audit action, no vocabulary, no UI. It
  decides what one must be.
- **`HumanAssertion` implementation.** ADR-0035 remains deferred. This
  ADR discharges its §9 prerequisite and authorises nothing else.
- **A supersession API or UI.** No route, no schema, no control.
- **Automatic supersession.** No rule, policy, heuristic, suggestion,
  import or backfill establishes a statement. §6.
- **`related document`.** §4 and §25.
- **Duplicate detection.** Equal checksums conclude nothing, and no
  upload-time lookup is introduced. ADR-0036 §16.
- **Cross-document engineering identity.** Two documents naming the same
  designation remain two independent sets of observations. AF-01 §21,
  ADR-0034 §10.
- **`Cable`, `CableRun`, `Circuit`, `Terminal` or conductor.** No such
  concept, type, column or vocabulary member.
- **Electrical connectivity.** Nothing here expresses that two things are
  connected.
- **Header detection.** Refused by ADR-0034 §6, ADR-0035 §4 and
  ADR-0036 §26, and refused again here.
- **Any change to `documents.revision`.** It stays a `String(50)`
  defaulting to `"00"` that nothing writes. Making it meaningful is a
  registry milestone with its own migration and its own API behaviour
  change; borrowing it for ordering is refused in §6.
- **A replacement mechanism.** ADR-0036 §14 specifies the semantics and
  builds none; §14 here adds the missing converse and builds none either.
- **A document filter on `edges_from_subjects`.** §16 records the gap as
  a constraint on a future consumer, not as work to do.
- **A new warning category.** Neither closed warning vocabulary is
  opened. §16.
- **Conflict resolution as a governed act.** §12 names it and declines to
  design it.
- **P2 expansion.** No reasoning, retrieval or graph capability.
- **Semantic inference.** Nothing concludes meaning from anything.

---

## 27. Testing contract

The following tests are **required**, not suggested, of whatever
milestone implements supersession. Each names what it proves, the layer
it belongs to, the invariant, and what breaks without it - because a test
whose failure nobody can interpret is a test nobody will fix correctly.

Fixtures are synthetic throughout: two documents with a few bytes of
known content is sufficient for every row below. **No real project
document is ever committed**, and the repository is public.

| # | What is proven | Layer | Invariant | What breaks without it |
|---|---|---|---|---|
| 1 | No rule, policy, service or scheduled path produces a supersession statement - the only writer is an authored act | architecture | §5, §6: establishment is human-only | the platform concludes lineage from bytes, filenames or chronology, each already refused where it is computed, and a guess acquires a person's authority |
| 2 | The author is server-resolved from the authenticated identity, and **no request schema declares an author field** | service + architecture | §5; ADR-0023's *"a field in which a caller could claim to be somebody else"* | a caller attributes a statement to somebody else; note that `extra="forbid"` is set on no schema in this repository, so refusal does not come free |
| 3 | Both endpoints pin a version: `document_id` **and** `content_checksum`, both mandatory on both sides | domain | §7 | a statement retargets silently when bytes change, and says something the engineer never looked at |
| 4 | A document whose recorded identity is `NULL` is refused as either endpoint | domain + service | §17; ADR-0036 §27 *"A NULL identity is not a match"* | a legacy row is pinned to an unknown, two unknowns pair, and the statement means nothing |
| 5 | Self-supersession **raises** a typed error and is never stored | domain | §10; the failure-reason / exception line at `document_identity_exceptions.py:4-18` | an incoherent record is persisted as though a document were at fault, and every read must then handle a self-loop |
| 6 | A cycle between two or more statements is **representable**, and every read over it terminates and reports the cycle as a named outcome | domain | §10: arrival order is never the adjudicator, and no read assumes acyclicity | either the second declaration is refused - the forbidden tiebreak in validation clothing - or a read recurses forever on real data |
| 7 | A fork is representable: one predecessor with two successors produces two records, and both are returned | domain + persistence | §11: no uniqueness constraint in either direction | the second declaration overwrites the first, and storage shape picks a winner no policy chose |
| 8 | Two contradicting statements both remain readable, and the pair reports a conflict computed on read | domain | §12: conflict is an outcome, never stored and never resolved | an engineering disagreement is hidden behind a timestamp, the `human_review` idiom reintroduced under a new table name |
| 9 | Withdrawal and correction act only on the author's own statement; another author's attempt is refused | service | §13 | the tiebreak §12 forbids returns through a side door, as a second human record with identical effect |
| 9b | A withdrawal is a record of its own type in its own table, and **neither table carries a nullable column that exists only to hold the other's rows** - both endpoints stay mandatory on a statement, and a withdrawal's target key stays mandatory on a withdrawal | domain + persistence | §13's two-type decision; §21's two-table requirement | the one-table-with-a-discriminator shape §13 refuses arrives anyway, every row carries half its columns as `NULL` behind a flag, and §27 row 3's mandatory endpoints quietly become optional |
| 10 | **No derived artefact changes when a statement is recorded** - byte-identical canonical representations, evidence, entities, facts, semantics, reviews and governed graph, before and after | integration | §15: inertness | supersession retires, re-points or invalidates knowledge derived from bytes nobody re-read, on the strength of an unreviewed declaration |
| 11 | **No supersession value reaches any identity preimage**, and `GraphRetirementReason` has exactly five members | architecture | §15; `graph_lifecycle.py:95-123` | a derived identity becomes a function of a relation between documents, or a machine retires a human's approved statement |
| 12 | No retrieval, context assembly, reasoning or response module imports the supersession context | architecture | §16 | `MULTIPLE_MATCHES` becomes a guess, and the platform decides the engineering question AF-AMB-001 depends on it refusing |
| 13 | **No engineering semantics**: no `cable`, `circuit`, `terminal`, `conductor`, `connects` or equipment vocabulary, and no interpretation name, anywhere in the context | architecture | §7, §26; the existing scans at `test_canonical_spreadsheet_boundaries.py:82-91` and `:96-112`, widened to this directory | a milestone about two rows acquires a vocabulary about substations, one plausible name at a time - and the existing scan stops at four spreadsheet packages, so it would not reach here |
| 14 | The word `lineage` appears in no identifier in the context, in any casing | architecture | §9: `DocumentLineage` means source family in 4 files and 15 sites | the one enum an engineer reads while a pipeline is broken acquires a second meaning |
| 15 | No name in the context collides with `human_review`'s supersession vocabulary, and the new audit actions are distinguishable from `ENGINEERING_REVIEW_SUPERSEDED` | architecture + contract | §9, §19 | an auditor cannot tell "a judgement was superseded" from "a drawing was declared re-issued" |
| 16 | Two engineers declaring the same pair produce two records with different keys | domain | §8: author and instant are in the preimage | two independent declarations collapse into one, and a disagreement that was never resolved reads as agreement |
| 17 | The same record yields the same key when recomputed in another process | domain | §8: nothing ambient in the preimage - no surrogate, no clock read at hash time | the key is stable only inside one database, so nothing downstream can compare it |
| 18 | The instant is injected, never read from the ambient clock | service | §20 | the record is not reproducible and tests become time-dependent |
| 19 | No route accepts a checksum, and no route accepts a statement key | architecture + API | AF-PROV-002 (`test_architecture_freeze_af01.py:331-339`); §7 | a caller asserts which version was pinned, and the record believes it |
| 20 | Declaring requires its own capability, and **every** authoring route declares it | security | §18 | authoring is available to any authenticated user - the state four project routes and the whole `review_workflow` router are in today |
| 21 | Every authoring act produces an audit event | integration | §19 | the action is invisible in the trail even though the record is visible |
| 22 | `document_supersession` is named in `DETERMINISTIC_CONTEXTS` and in AF-TRUTH-002's forbidden set, **and AF-TRUTH-002's scan set is widened to `canonical_spreadsheet` and `spreadsheet_evidence` in the same change** | architecture | §20; the tuple at `test_architecture_freeze_af01.py:510-555`; the six-context scan at `:639-646` | the context could import an LLM runtime with no test failing, and the truth boundary stays stated and undelivered for the one source family ADR-0035 is about |
| 23 | `documents` gains no supersession column, and the refused-names list still fails on one | architecture | §11; `test_document_version_identity_architecture.py:308, 321-327` | the column design §11 refutes arrives anyway, and a fork silently picks a winner |
| 24 | A supersession statement cannot be constructed as, or converted into, a context item for a prompt | architecture | §20; ADR-0035 §8 | provenance is fabricated to satisfy a context item's required fields |
| 25 | Project lifecycle does not gate authorship or readability | service | §13 | record administration silently governs an engineering statement whose two endpoints may sit in two projects |
| 26 | Whatever lifecycle or outcome vocabulary a client must transcribe reaches the public schema as a **named** enum | contract | ADR-0035 §13 | the frontend transcription becomes uncheckable, joining the eight vocabularies already in that position |

Rows 1, 10, 11, 12 and 13 are the ones that keep this decision honest
over time. The rest can be re-derived from the model; those five are the
only defence against the boundary eroding quietly.

---

## 28. Relationship to ADR-0035 and ADR-0036

### What this ADR discharges

**ADR-0035 §9's prerequisite, in the part that was still open.**
ADR-0035 named two things: a stable single-valued version handle, and the
ability for *"a document to say which document it supersedes"*.
ADR-0036 §27 reported that it had delivered the first and not the second:

> ADR-0035 §9's stronger sentence is **not** satisfied: *"Assertions are
> not implemented until a document can say which document it
> supersedes."* A document still cannot say that.

This ADR decides **what saying it is**: a human-declared, append-only,
version-pinned, attributed statement, conflicting rather than resolving,
inert with respect to everything derived. A document still cannot say it,
because nothing is built. What is no longer missing is the design.

**ADR-0036 §5's deferred question.** *"Whether document lineage is
machine-established or human-declared"* - recorded there as unresolved.
Answered in §5 and §6: human-declared. §4 also resolves the term
collision ADR-0036 §4 introduced.

**ADR-0035 §9's undecided converse.** That ADR decided inheritance - a
successor does not acquire a predecessor's assertion. §15 decides
invalidation in the supersession direction, which nothing in the
repository had decided: supersession does not invalidate a predecessor's
derived knowledge, and must be structurally incapable of doing so.

### What it inherits unchanged

From **ADR-0035**: the declared-statement shape (§1), the copied
server-resolved author (§2), identity including author and instant and
never an `ArtifactIdentity` (§3), conflict as an outcome and never a
tiebreak (§5), the closed-vocabulary discipline (§6), never an input to
deterministic extraction (§7), `DETERMINISTIC_CONTEXTS` membership and
the AF-TRUTH-002 widening (§8), non-propagation to a successor (§9),
append-only with author-restricted withdrawal and the warning about the
word `superseded` (§10), actions never derived from state values (§11),
own capability and own audit action (§12), named enums in the public
schema (§13).

From **ADR-0036**: the document version as the pair (§6), the content
checksum as the thing to pin (§7, §27), no ordering over versions (§13),
replacement semantics (§14), no deduplication (§16), server-side
provenance and no storage locator (§17), write-once immutability (§18),
`NULL` permanence with no backfill (§19).

### What it does not touch

ADR-0035's assertion context, locator, type vocabulary and consuming
stage - all still deferred. ADR-0036's columns, migration, upload path,
registry adapter and `source_identity` preimage - all unchanged, and
§21a's portability defect is neither fixed nor worsened here.

---

## 29. Consequences

### Good

- **The question two ADRs deferred in writing now has an answer.**
  ADR-0036 §5 recorded it as *"unresolved rather than settled by
  default"*; it is settled, and the argument is built from the
  repository's own refusals rather than from preference.
- **The convenient wrong design is refuted before anybody writes it.**
  §11 shows a `superseded_by` column cannot hold a fork, and that a fork
  is frequent and correct. That is the design a delivery-pressured
  milestone would have shipped.
- **Forks, cycles and conflicts are designed for rather than discovered.**
  Each is a representable outcome with a named result, not an error
  condition found in production.
- **Inertness is decided, and decided in the direction that preserves
  explainability.** A conclusion drawn from last year's revision stays
  explainable, and no machine retires a human's approved statement
  because of a relation between two files.
- **The cost to retrieval is stated before anything is built.** §16 names
  the exact mechanism by which supersession would convert a deliberate
  refusal into a guess, so a future consumer has to argue against a
  written position rather than discover an unstated one.
- **Three naming collisions are recorded with their evidence** - `lineage`
  in 4 files, `superseded` in the audit vocabulary and the review
  projection, and three Italian words in the UI - so the implementing
  milestone does not rediscover them at review time.
- **Two live defects were repaired**, and a document is now genuinely
  durable enough to be an endpoint (§24).

### Costs and risks

- **Legacy documents are permanently excluded**, and they are the ones
  most likely to have revision history (§17). This is the largest cost in
  the ADR and it has no mitigation.
- **A wrong statement from a departed author stands forever** (§12), and
  unlike an assertion about a header row it is a statement about which
  document an engineer should be reading.
- **The tie-breaker is still an open design question** (§8), inherited
  from ADR-0035 §3 and not closed here. The implementing milestone
  inherits real design work.
- **The value is partly deferred.** A statement that changes nothing
  (§15) and is read by nothing (§16) is, on the day it ships, a record
  nobody sees. Its value arrives when something honestly surfaces it -
  and §16 measures that both warning vocabularies are closed with no slot
  for it, so that milestone starts with a visible edit to a closed enum.
- **The word `supersession` will mean two things in this repository**
  once the context is built, in two contexts, with opposite rules about
  how it is established. It does not yet: `supersession` appears in code
  exactly once, at
  `tests/architecture/test_architecture_freeze_af01.py:715`, about
  AF-01's own change and supersession policy, and `human_review` uses
  `superseded` rather than the noun. §9 and §12 are the only things that
  will keep the two apart, and §9's naming rules are prose until §27 rows
  14 and 15 are executable.
- **Nothing is built**, so nothing is proven. Every claim above is a
  constraint on a future milestone, and a constraint with no test is a
  preference.

### Debt recorded, not paid

- **Conflict resolution as a governed act does not exist**, and cannot
  until the role model has an authority to perform it (§12).
- **AF-TRUTH-002 still scans six contexts** and omits both spreadsheet
  contexts (§20). ADR-0035 §8 required the widening; ADR-0036 did not do
  it; this ADR does not do it either, because widening a fitness function
  in a milestone that adds no context would be the refactoring-mixed-with-
  behaviour CLAUDE.md §10 forbids. It is required of the implementing
  milestone by §27 row 22.
- **Foreign keys are unenforced**, and all thirteen that touch
  `documents` declare `ondelete = None` (§24). The repairs close the
  application paths, not the database.
- **A document id can still be reused, by one route, and it is not
  fixed.** A hand-deletion followed by a downgrade and a re-upgrade
  reissues a spent id. Fixing it needs an `UPDATE` against
  `sqlite_sequence`, which `test_no_migration_fabricates_an_identity`
  forbids textually - so a repair for one integrity rule was blocked by
  another, and the frozen rule won. The guarantee is therefore narrowed
  to *while the schema stays at or above this revision*, the defect is
  pinned by an `xfail(strict=True)`, and §24 leaves the choice between
  narrowing that fitness function under AF-01 §22 and accepting the
  narrower guarantee to a future milestone. **The suite is green:
  3851 passed, 1 xfailed.**
- **Every test but one still runs against a `create_all` schema**, not a
  migrated one. That divergence hid two migration defects until a
  reviewer ran them (§24), and it is closed for document ids only.
  Debt Register item (l).
- **The repair left an incoherent state reachable in principle**: both a
  detach and a project delete leave a document with a null `project_id`
  while `scope` still reads `PROJECT`. No route reaches it, and it is
  strictly better than the irrecoverable deletion it replaced. Debt
  Register item (m).
- Everything in the Debt Register below.

---

## Debt Register

Known, verified, and deliberately untouched. Each is recorded so a future
engineer finds it here rather than rediscovering it. None is caused by
this change. ADR-0036's own register is not restated; these are
additional.

| # | Statement | Where |
|---|---|---|
| a | Foreign keys are not enforced: no `PRAGMA foreign_keys = ON` exists anywhere, and twelve tables reference `documents.id` with no `ondelete` on any of them | `app/database/database.py:1-23` (engine created with `check_same_thread` only); the twelve are `canonicalization.py:160`, `canonical_pdf.py:65`, `canonical_spreadsheet.py:75`, `canonical_text.py:58`, `document_ingestion.py:67`, `engineering_entities.py:64`, `engineering_evidence.py:59`, `engineering_facts.py:69`, `engineering_index.py:63`, `engineering_semantics.py:64`, `proposed_claims.py:126`, `spreadsheet_evidence.py:65`, all under `app/models/`; a search for `ondelete` across `app/models/` returns nothing |
| b | `PATCH /projects/{id}`, `activate`, `archive` and `restore` declare no capability and never consult `may_administer_project`, whose own docstring says *"'Administer' means archive, restore or delete"* | `app/routers/projects.py:270-282` (PATCH), `:351-365` (activate), `:367-381` (archive), `:383-397` (restore) - none takes a `require_capability` dependency, unlike `create_project` at `:199-204` and `delete_project` at `:405-410`; the docstring is `app/domain/identity/project_access.py:44-52` |
| c | No project lifecycle transition is audited. `AuditAction` carries `PROJECT_CREATED` and nothing for activate, archive, restore or metadata update, and the router writes an audit event only on create and on a denied delete | `app/domain/audit/audit_models.py:50`; `app/routers/projects.py:245-251` (create) and `:429-435` (`ACCESS_DENIED` on delete) |
| d | `review_workflow` accepts `reviewed_by` from the request body with no capability gate on any route, and that value becomes a stored fact's chain of custody | `app/schemas/review_workflow.py:27` (`reviewed_by: str = Field(min_length=1, ...)`); consumed at `app/routers/review_workflow.py:197`, `:240`, `:283` and `:326`; the router declares no `require_capability` on any of its nine routes; the value reaches `app/domain/canonicalization/canonicalization_models.py:78` as provenance |
| e | `scripts/create_administrator.py` contradicts its own docstring - *"Refuses to run when any user already exists"* and *"A script that could mint an administrator into a running installation would be a privilege-escalation tool sitting in the repository"* - via `--allow-additional`, which does exactly that; and it records no audit event | `scripts/create_administrator.py:17-20` (the docstring), `:44-52` (the flag), `:81` (the guard it bypasses); a search for `audit` in the file returns nothing |
| f | `find_latest_for_document` resolves an artefact by highest row id across **eight** adapters (the brief that prompted this ADR said nine; it is eight, with eight matching ports) | `app/infrastructure/canonical_pdf/sqlalchemy_canonical_representation_repository.py:120`, `canonical_spreadsheet/...:115`, `canonical_text/...:77`, `engineering_entities/...:84`, `engineering_evidence/...:92`, `engineering_facts/...:92`, `engineering_semantics/...:98`, `spreadsheet_evidence/...:95`, each `.order_by(<Record>.id.desc())` |
| g | The document row's recorded identity and its artefacts' recorded identity can diverge, and nothing compares them. `documents.content_checksum` is read by exactly one consumer - the registry detail view | `app/infrastructure/document_registry/sqlalchemy_document_registry.py:210-212` is the only read; the four pipeline comparisons at `engineering_evidence/evidence_validation.py:60`, `engineering_entities/entity_validation.py:45`, `engineering_facts/fact_validation.py:41` and `engineering_semantics/semantic_validation.py:39` compare an artefact against its **upstream artefact**, never against the document row |
| h | **Fixed in this milestone, recorded because it was found here.** `app/models/document.py` justified the identity columns with *"every downstream stage refuses to build when its checksum and its upstream's disagree"* - true of the artefact chain, and false as an account of the **document row**, whose recorded identity participates in no refusal anywhere. The comment now says what actually happens and names ADR-0036 §18's *detectable, not detected* | the corrected comment at `app/models/document.py:149-165`; see (g) for what compares what |
| i | `document_models.py` still documents `content_checksum` as *"read from the document's own ingestion record"*, which ADR-0036 §22 changed: it is read from the document row | `app/domain/document_registry/document_models.py:120-128`, against `app/infrastructure/document_registry/sqlalchemy_document_registry.py:210-212` |
| j | ADR-0036 §10 calls `revision`, `category`, `scope` and `project_name` *"mutable registry metadata, changeable after upload without touching a byte"* when no route can change them; and `docs/architecture/document_management.md:29` calls `revision` *"The document's own revision, as supplied"* when nothing supplies it and every row reads `"00"` | ADR-0036 §10's exclusion table; `app/models/document.py:125-129` (default `"00"`); `docs/architecture/document_management.md:29`; `app/routers/projects.py` and `app/routers/documents.py` expose no route writing any of the four |
| k | ADR-0036 §28 row 9's identity scan misses two real cases. It records an `ImportFrom` node's `module` and compares it to `"app.models.document"`, so **every import through the package** resolves to `app.models` and takes the module through the scan untouched - both `from app.models import Document`, which `app/models/__init__.py:14` re-exports, and `from app.models import document`, which two modules already use. And its raw-SQL half walks `ast.Constant` only, so an f-string `UPDATE` is an `ast.JoinedStr` and evades it entirely | `tests/architecture/test_document_version_identity_architecture.py:109-118` (`_imported_module_names` records `node.module`), `:121-137` (`_sees_a_document_row`), `:200-208` (`_sql_updates`); `app/models/__init__.py:14`; the package-import style in use at `app/main.py:14` and `apps/backend/scripts/benchmarks/graph_performance_benchmark.py:58` |
| l | **Raised and largely paid inside this milestone.** It was: the migration was exercised by no test, because `tests/conftest.py:66` builds every test database with `Base.metadata.create_all` and nothing ran the Alembic chain. `tests/infrastructure/test_the_migration_chain_protects_document_ids.py` now runs it and is the only module that does. **What remains**: every *other* test in the repository still runs against a `create_all` schema rather than a migrated one, so the divergence that hid two migration defects is closed for document ids and open everywhere else - and the rebuild's row-and-index preservation is still a reviewed manual result rather than a tested one (§24) | `apps/backend/tests/conftest.py:61-66`; `apps/backend/tests/infrastructure/test_the_migration_chain_protects_document_ids.py`; `apps/backend/migrations/versions/8f21c04ab7de_documents_never_reuse_an_id.py` |
| m | **Made reachable by this milestone's repair.** Removing the cascade turned a destructive operation into an incoherent one. Both `project.documents.remove(document)` **and `session.delete(project)`** now leave `project_id` null while `scope` stays `PROJECT` and `project_name` keeps the dead project's name - the ORM nulls the child key before deleting the parent, so the very operation `test_deleting_a_project_leaves_its_documents` performs leaves that residue, and the test asserts only the row count. Demonstrated. The row reaches the public list API claiming project scope with no project, a pair `POST /documents/upload` refuses with 422. It is precisely the state `DocumentScope`'s docstring says must never arise: *"This scope must never be inferred from a nullable project reference being empty."* Still unreachable by any route, and still strictly better than the irrecoverable deletion it replaced | `app/domain/project/project_document_scope.py:16-19` (the docstring); the only enforcement at `app/routers/documents.py:409-423`; `app/models/document.py:137-141` (`scope` defaults to `PROJECT`) |
| n | **Not previously recorded anywhere, and reachable through public HTTP routes - unlike the document defect this milestone fixed.** `proposed_claims` and `engineering_index_entries` carry no `sqlite_autoincrement` - `app/models/document.py` is the only model that does - and their repositories delete rows in bulk, so SQLite reissues the ids. Reproduced: a reused claim id inherited rows in `canonical_facts` and `review_candidates`, and a re-indexed entry inherited citations in `canonical_fact_evidence` and `proposed_claim_evidence` - so an approved canonical fact's citation of *where in the document it was found* silently re-points to another entry. Out of scope for this milestone | `app/infrastructure/proposed_claims/sqlalchemy_proposed_claim_repository.py:174-182` (`delete`); `app/infrastructure/engineering_index/sqlalchemy_engineering_index_repository.py:108-135` (`replace_for_document`) and `:137-142` (`delete_by_document`); reachable via `DELETE /proposed-claims/{id}` (`app/routers/proposed_claims.py:202`) and `PUT`/`DELETE /documents/{id}/engineering-index` (`app/routers/engineering_index.py:217`, `:273`), and neither router declares `require_capability` on any route |
| o | `ix_projects_owner_user_id` exists in a `create_all` schema and therefore in every test database, and in no Alembic-migrated one. The model declares `index=True`; the migration that adds the column never creates the index. Every test runs against an index no deployment has, and by construction no test can notice - the same test-versus-deployment divergence as (l), in a second place | `app/models/project.py:111-115` (`index=True`); `migrations/versions/a4c81f2b90de_add_identity_sessions_and_audit.py:151` adds the column and `:165` drops it, with no `create_index` for it anywhere |
| p | A storage-suffix collision silently overwrites another document's bytes. The suffix is `secrets.token_hex(4)` - 32 bits - and the write opens `"wb"`, which truncates, while `safe_storage_name`'s docstring claims *"a random suffix so no upload overwrites another"*, which is absolute and not delivered. Forced in review: document A's row keeps its own checksum while its storage reference resolves to document B's bytes - so §7's version pin would name bytes the platform no longer holds. A one-character fix exists (`"xb"`, which refuses rather than truncates). Out of scope | `app/services/storage.py:80` (the docstring claim), `:84` (`secrets.token_hex(4)`), `:147` (`open("wb")`) |

---

## References

- [ADR-0002](0002-engineering-index-vs-project-knowledge-graph.md) - an
  uninterpreted locator carries no trust; why a lead is not knowledge.
- [ADR-0005](0005-project-vs-canonical-library-document-scope.md) - a
  document belongs to exactly one project or to the Canonical Library,
  which is why §13 refuses to let project lifecycle gate a statement
  whose endpoints may sit in two.
- [ADR-0008](0008-database-migration-governance.md) - Alembic governs
  every schema change; §21 and §24 follow it.
- [ADR-0023](0023-human-review-append-only-judgement.md) - append-only
  judgement; the caller-supplied reviewer field rejected as *"a field in
  which a caller could claim to be somebody else"*; *"nothing about human
  judgement may become an input to"* the deterministic pipeline.
- [ADR-0029](0029-deterministic-engineering-reasoning-foundation.md) - a
  new kind of statement gets a separate type in a separate context, never
  a flag.
- [ADR-0032](0032-upstream-identity-in-derived-set-reuse.md) - the
  composed identity contract, and the reuse question `RECOMPUTE` answers
  - the one §7 shows has no meaning for a declaration.
- [ADR-0034](0034-spreadsheet-canonical-representation.md) - the source
  family fork, which is what `DocumentLineage` actually names; *"a wrong
  answer is worse than a visible error in this domain."*
- [ADR-0035](0035-human-authored-document-assertions.md) - the fifth kind
  of statement, whose §9 prerequisite this ADR discharges; §3, §5, §9,
  §10 and §12 are inherited here almost entire.
- [ADR-0036](0036-document-version-identity.md) - the document version as
  `(document_id, content_checksum)`; §5's deferred question, which §5 and
  §6 here answer; §13's refusal of ordering; §14's replacement semantics;
  §19's permanent `NULL`, which §17 here inherits as a hard exclusion.
- [Architecture Freeze AF-01](../architecture_freeze_af01.md) - §7 data
  ownership, §8 write authority, §9 frozen dependency directions, §11
  provenance, §13 the identity model and *"identity is never derived from
  a label"*, §20 the fitness functions, §21 the stated absence of
  cross-document entity resolution, §22 the change policy.
