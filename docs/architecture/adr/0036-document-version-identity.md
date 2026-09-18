# ADR-0036: Document Version Identity

## Status

Accepted. Introduced by the *Document Version Identity* milestone, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted. One fitness function is **strengthened**
(§21); none is loosened and none is deleted.

AF-01 §22 sorts a change into one of two categories: ordinary evolution,
or a change requiring an ADR that names the invariant it alters. This
change alters no AF-01 invariant, so §22 does not compel an ADR. It is
recorded as one because CLAUDE.md §11 requires an ADR for a persistence
choice, and because this milestone settles what a *version* of a
document is - a question four domain modules already ask in their own
failure messages (§6) without anything in the system being able to
answer it.

This ADR is the prerequisite
[ADR-0035](0035-human-authored-document-assertions.md) §9 named and
deferred to: *"a durable document version handle is a prerequisite
milestone"*, and *"there is no stable single-valued source to resolve it
from today, and that is part of the same prerequisite."* It discharges
that prerequisite in the narrow, materialising form §5 and §6 below
describe, and **does not** discharge ADR-0035 itself: no assertion
context, table, route or vocabulary is authorised here, and none is
created.

Adds no governed vocabulary, no graph capability, and no engineering
semantics.

**On evidence.** Every claim below about the repository as it stands is
cited to `path:line` and was read before it was written. Where this ADR
reasons past what the code states - about what a future implementation
must do, or about what a defect would cost to fix - it says so in the
prose. The two are deliberately not blended.

**On line numbers.** Every citation is to the code **as it stands after
this milestone**, with exactly two exceptions, both describing the
upload path as it was and both saying so in their own text: §3's *"What
upload did before this milestone"* subsection, and the two references to
the bare `db.commit()` at `documents.py:467` (§3's closing subsection
and §20's *"What was wrong"*). Everything else in §3, including the
domain module and the storage service, is cited post-milestone like the
rest of the document. Where a present-tense claim and a "before"
description quote the same file, they cite different lines on purpose.

---

## 1. Context

### What forced the decision

The platform binds its entire deterministic chain to a value called
`content_checksum`. Four separate domain modules refuse to build an
artifact when two stages disagree about it, and each says so in the same
words:

- `app/domain/engineering_evidence/evidence_validation.py:60-65` - the
  evidence set and its canonical text *"disagree about which document
  version was observed"*.
- `app/domain/engineering_entities/entity_validation.py:45-50` - the
  same, for an entity set and its evidence.
- `app/domain/engineering_facts/fact_validation.py:41-46` - the same,
  for a fact set and its entities.
- `app/domain/engineering_semantics/semantic_validation.py:39-44` - the
  same, for a semantic set and its facts.

All four **return** a typed `INCONSISTENT_SOURCE_IDENTITY` failure -
none raises; the failure is a frozen value a caller reports, not an
exception. All four are talking
about a **document version**. The concept is therefore not new, not
speculative, and not introduced here: it is already load-bearing in the
pipeline's own refusals.

What the system could not do was *state* one. **Before this milestone**
no table held a document's content identity: the `documents` row carried
`filename`, `file_path`, `file_format`, `category`, `revision`,
`project_name`, `scope`, `uploaded_at` and a project foreign key - and
no checksum, no size, no algorithm. §6 adds the three columns that close
that, and `app/models/document.py:123-137` is where they now live.
There is no `supersedes`, no `superseded_by` and no
`previous_document_id`. A search across backend and frontend for those
three names returns **eleven hits in seven files**, and **not one of
them is a lineage mechanism**: no column, no field and no relation
anywhere says that one document supersedes another. They break down as:

- **Seven in human review's own supersession vocabulary**: the domain
  event field (`app/domain/human_review/review_events.py:72`), the
  service that populates it
  (`app/services/human_review_service.py:160`), and three frontend
  modules that render it
  (`apps/frontend/components/workspace/ReviewDialog.tsx:28, 54, 176`,
  `apps/frontend/components/workspace/ReviewPanel.tsx:210`,
  `apps/frontend/hooks/useStatementReview.ts:137`).
- **One in a human review architecture test**, pinning that field's name
  (`tests/architecture/test_human_review_boundaries.py:357`).
- **Three added by this milestone itself**, in the list of column names
  §13 refuses - they appear there precisely so that adding one becomes
  an edit to that list
  (`tests/architecture/test_document_version_identity_architecture.py:321-323`).

**In production code the count is seven** - two in the backend and five
in the frontend, all of them human review's. The remaining four are in
tests, three of which name `documents` columns precisely in order to
forbid them. The same holds for `document_version`: zero occurrences in production
code, and one in this milestone's refused-names list
(`tests/architecture/test_document_version_identity_architecture.py:327`,
`document_version_id`). No document lineage vocabulary exists anywhere
in the system, and the only places these words appear at all are a
different context's supersession model and the tests that forbid them
here.

So the phrase *"which document version was observed"* is, today, a
sentence the code writes about a thing the code cannot name.

### What answers "the checksum of document 17" today

One thing did, and it was the wrong thing. The registry adapter read the
document's most recent ingestion job by row id and copied that job's
checksum onto the detail view:

- `_latest_job` orders by `DocumentIngestionJob.id.desc()` and takes the
  first. There is **no filter on outcome**: a failed attempt is as
  eligible as a successful one. That query is unchanged and still serves
  the ingestion *state*
  (`app/infrastructure/document_registry/sqlalchemy_document_registry.py:101-118`).
- That job's `content_checksum`, `content_checksum_algorithm` and
  `content_size_bytes` became the document's. **That mapping is what
  this milestone replaced**; `_to_detail` now reads the three columns
  off the document row
  (`app/infrastructure/document_registry/sqlalchemy_document_registry.py:203-212`),
  and the adapter's own docstring records why (same file, `:106-110`).

A document legitimately accumulates jobs. `DocumentIngestionJob`
declines a uniqueness constraint on `document_id` and says why:
*"a document is legitimately ingested more than once over its life, and
the accumulated jobs are its audit trail"*
(`app/models/document_ingestion.py:28-34`). "The most recent attempt" is
an operational fact about a queue. It is not a version handle, and
ADR-0035 §9 already said so.

### The shape the answer has to take

The pipeline binds to a checksum, so the answer has to be a checksum.
The registry cannot resolve one, so the answer has to live somewhere a
registry read can reach single-valuedly. And ADR-0035 forbids the one
shortcut that would otherwise be available: lineage may never be
inferred from equal bytes, because *"the system declines to conclude
that equal bytes mean the same document"* (ADR-0035 §9).

---

## 2. Problem

Stated exactly:

> A document has an identity (`documents.id`). Its bytes have an
> identity (a SHA-256 digest, computed in at least three places). The
> pair of the two is what every deterministic artifact in the system is
> keyed to, and **nothing records it**.

Four consequences follow, and each is independently a defect.

1. **`content_checksum` on the public document resource is derived from
   an arbitrary row.** It is whichever ingestion attempt has the highest
   id, succeeded or not. Two reads of one unchanged document can return
   different values if a second attempt ran between them.
2. **A document that has never been ingested has no checksum at all**,
   even though its bytes were hashed during upload and the value was
   discarded (§3).
3. **A durable human record cannot be built on it.** This is ADR-0035's
   blocking reason, restated: *"A durable human record cannot be built
   on an identity that is not durable."*
4. **Nothing can detect that the bytes under a document changed**,
   because there is no recorded prior value to compare against.

There is also a *non*-problem this milestone must resist solving.
Lineage - which document supersedes which - is a separate question, and
§5 refuses it deliberately rather than by omission.

---

## 3. Existing Architecture

What already exists, and is reused unchanged.

### Content identity is already a domain service

`app/domain/document_identity/content_identity.py` owns the rule:

- `CHECKSUM_ALGORITHM = "sha256"` (line 37) and
  `CHECKSUM_CHUNK_SIZE = 1024 * 1024` (line 42).
- `ContentIdentity` (lines 81-90) is a frozen value object of
  `storage_reference`, `checksum_algorithm`, `checksum` and
  `size_bytes`, whose docstring already states that the storage
  reference *"is recorded so a reader can see which stored object was
  hashed, without it being part of what the checksum covers"*.
- `resolve_content_identity` (lines 141-227) streams the bytes through
  `DocumentContentPort`, refuses an empty file rather than recording
  SHA-256's empty digest (lines 152-156, 186-191), and refuses when the
  streamed length disagrees with the reported size (lines 208-217).

The domain reaches bytes only through the port, and fitness functions
hold it there - at two different scopes, which is worth stating
precisely. In
`tests/architecture/test_document_identity_boundaries.py`, the parser
and AI bans scan the whole identity *surface* - the domain package, the
infrastructure adapter, the identity service and the format backfill
service (`_identity_surface`, lines 62-67). The filesystem ban and the
"never opens a file" assertion scan the **domain package only** (lines
199 and 220). So the domain cannot import `pathlib` or call `open`,
while the adapter that streams the bytes is deliberately free to.

### The pipeline's identity primitive

`app/domain/artifact_identity/` composes every deterministic identity as
`H(contract, kind, upstream, local)`
(`artifact_identity_models.py:14-15`). An `ArtifactIdentity` value is
validated to be exactly 64 lowercase hex characters
(`artifact_identity_models.py:92-99`). The contract version is
`"1.0"` and raising it *"re-identifies every artifact in the repository,
so it is a migration event and not a routine edit"*
(`artifact_identity_policy.py:17-18`).

### Storage writes bytes and changes nothing

`save_file` (`app/services/storage.py:107-174`) sanitises the storage
name, checks the resolved path is inside the storage root, and writes
the stream chunk by chunk with no transformation of any kind
(`app/services/storage.py:147-156`). No normalisation, no re-encoding.
**What is stored is byte-for-byte what was uploaded**, and §9 rests on
that. Before this milestone the same guarantee came from a
`shutil.copyfileobj` call; §8 says why the loop replaced it.

### What upload did before this milestone

**The line numbers in this subsection are the pre-milestone ones**; the
Status section names the only other place that is true.
`app/routers/documents.py`, in order, as it stood at commit `2ab449a`:

| Line | Step |
|---|---|
| 445 | `save_file(...)` - the stream is read once and written |
| 450-455 | `resolve_document_identity(...)` - the stored file is **re-opened and fully re-hashed** |
| 466-467 | `db.add(document)` then a bare `db.commit()` |
| 470 | `_run_document_pipeline(...)` |
| 472-477 | the detail read that produces the response |
| 481-489 | the audit event naming the actor |

The digest computed at line 450 is used to classify the format and to
build warnings. **It is never stored.** Downstream, the bytes are read
in full again by ingestion
(`app/services/document_ingestion_service.py:221-227`) and again by
canonicalization (`app/services/canonical_pdf_service.py:174-177`),
which then reads them a further time into memory to parse
(`app/services/canonical_pdf_service.py:219`, `_read_all` at 377-395).
The spreadsheet lineage does the same at
`app/services/canonical_spreadsheet_service.py:188` and `:429`.

### The commit at line 467

`app/routers/documents.py:467` was the **only** raw `commit()` in
`app/routers/` and `app/services/`; a search across both returned
exactly that one line. The scope is the claim: the one other raw commit
outside `app/infrastructure/` is the `session.commit()` inside
`commit_or_restore` itself (`app/database/session_commit.py:51`), which
is the rule rather than an exception to it.

**That is the whole of the claim, and it is narrower than it sounds.**
`commit_or_restore` (`app/database/session_commit.py:40-54`) exists, but
most adapters do not use it. Measured across `app/infrastructure/`:
**28 raw `.commit()` calls in 17 modules**, against **5 adapter modules**
that route through `commit_or_restore` - audit, canonical PDF, canonical
spreadsheet, canonical text and document ingestion. Examples of the
majority that do not:
`app/infrastructure/document_identity/sqlalchemy_document_format_registry.py:53`,
`app/infrastructure/project/sqlalchemy_project_repository.py:83`,
`app/infrastructure/identity/sqlalchemy_user_repository.py:73, 96`, and
`app/infrastructure/governed_knowledge_graph/`
`sqlalchemy_governed_graph_repository.py:74, 90, 110, 125`.

So the upload route was not an exception to a rule the adapters keep; it
was the one instance of a widespread pattern that happened to sit
outside `app/infrastructure/`. The wider exposure is recorded in the
Debt Register and is **not** closed by this milestone.

What `session_commit.py`'s own docstring describes is nonetheless
exactly the failure the upload path had: a failed commit leaves the
session requiring an explicit rollback, *"until that happens every later
statement raises PendingRollbackError"*
(`app/database/session_commit.py:11-14`).

The upload had a second exposure the adapters do not: the file at line
445 was already on disk when line 467 ran. A failed commit left **an
orphaned file and an unusable session**.

---

## 4. Terminology

Four terms, kept apart on purpose. Conflating any two of them is the
failure mode this ADR exists to prevent.

| Term | Means | Identified by |
|---|---|---|
| **Logical document** | the record an engineer uploaded, named, filed under a project and refers to | `documents.id` |
| **Content identity** | the identity of one exact sequence of stored bytes | SHA-256 over the authoritative source bytes |
| **Document version** | one logical document *as it stood for one exact content identity* | the pair `(document_id, content_checksum)` |
| **Upload event** | one act of putting a file into the platform | a `documents` row, audited separately |

Two further terms are used below and are **not** introduced by this
milestone:

- **Representation identity** - what a versioned reader produced from
  those bytes (`canonical_pdf`, `canonical_spreadsheet`). It changes
  when the reader changes, while the content identity does not. ADR-0035
  §9 names this distinction as one the implementing milestone must
  preserve; §13 and §14 preserve it.
- **Lineage** - the relation "this document supersedes that one". It
  does not exist in the repository and is **not** created here (§5).

---

## 5. Logical Document Identity

**Decision: this milestone introduces no second identity. The
`documents` row remains the logical document handle it already is.**

There is a tempting design in which `documents` becomes a shell and a
new `document_versions` table holds the bytes-level facts. It is
rejected here, and the reason is not aesthetic.

**A two-entity model has to answer a question nothing in this repository
answers.** If versions are children of a logical document, something has
to decide which uploads are versions of the *same* document. There are
only two possible answers, and the repository states neither:

- *Machine-established* - the system concludes lineage from the bytes,
  the filename, or some similarity. ADR-0035 §9 forbids the only
  mechanical form of this that would be available: *"never inferred from
  two documents sharing bytes."* And the content identity context says
  the same about itself - whether a repeated upload is a duplicate, a
  re-issue or the same drawing filed twice *"is a question about the
  documents, not their bytes - and answering it here would be inventing
  a policy nobody has stated"*
  (`app/domain/document_identity/content_identity.py:15-20`).
- *Human-declared* - an engineer states that this upload supersedes that
  one. The platform has no such control, no such route, no such
  capability and no such audit action. Introducing one is a governed act
  with review obligations, and it is a different milestone.

**The repository does not state which.** That is the finding, and it is
recorded as unresolved rather than settled by default. Building a parent
entity now would mean shipping a table whose rows can only ever be
one-to-one with `documents`, plus a foreign key nothing populates,
plus the standing invitation to populate it by inference.

Two further reasons, both concrete:

- **`document_id` is already everywhere.** It is the first **local**
  component of the deterministic **root**
  (`app/domain/artifact_identity/artifact_identity_builder.py:160`) and
  therefore reaches every derived identity transitively, through the
  upstream digest rather than as a component of its own - the precise
  form §21a depends on. It is also a column on every deterministic
  artifact table, and the argument to every `find_latest_for_document`.
  A new logical identity would have to be threaded through all of it or
  shadow it. §21a records what that
  coupling already costs; adding a second identity on top of it
  compounds the problem rather than relieving it.
- **YAGNI, explicitly.** CLAUDE.md §12 forbids speculative generality,
  and the milestone's own framing was: *do not introduce two identities
  merely because it sounds correct.*

**Recorded as deferred, not answered:** whether document lineage is
machine-established or human-declared. Until it is answered, two
uploads of the same drawing are two documents (§12), and nothing
concludes otherwise.

---

## 6. Document Version Identity

**Decision: a document version is the pair
`(document_id, content_checksum)`. This milestone materialises it by
recording the content identity on the `documents` row, making it
single-valued and immutable. No new table.**

The pair is not invented here. It is what the four failure messages in
§1 already mean, and it is what `source_identity` already hashes
(`app/domain/artifact_identity/artifact_identity_builder.py:138-164`,
whose preimage is exactly `document_id`, `content_checksum`,
`checksum_algorithm`). Every canonical representation, evidence set,
entity set, fact set and semantic set in the system already carries both
halves as columns and refuses to be built when they disagree with its
upstream's.

What changes is that the pair becomes **stateable**. Today the
`document_id` half is on the `documents` row and the `content_checksum`
half is not, so the pair can be recognised at every downstream stage and
resolved at none.

Three columns are added to `documents`, following the shape and the
naming the ingestion job table already established
(`migrations/versions/d5b93e17ca40_add_document_content_identity.py`):

| Column | Type | Null | Meaning |
|---|---|---|---|
| `content_checksum` | `String(128)` | yes | the digest of the authoritative source bytes |
| `content_checksum_algorithm` | `String(20)` | yes | which algorithm produced it |
| `content_size_bytes` | `Integer` | yes | an observation about those bytes (§10) |

Nullable for the reason §19 gives, not as a convenience. Indexed
non-uniquely, for the same reason and in the same words the existing
migration used: *"deliberately not unique: identical checksums are
recorded and nothing is concluded from them"*
(`migrations/versions/d5b93e17ca40_add_document_content_identity.py:77-85`).

**What a document version is not.** It is not a row, not a sequence
number, not an ordinal, and not a thing that can be listed in order. §13
is about that.

---

## 7. Content Identity

**Decision: content identity is the SHA-256 digest of the authoritative
source bytes.**

*Authoritative source bytes* means, exactly: **the bytes as written to
storage.** Not the bytes as uploaded - because an upload can be
interrupted, and a digest over what the client sent would describe
something that is not what the platform holds. Not the bytes as later
read back - because a digest recomputed at read time answers "what is
there now", which is a different and also useful question (§18), but not
an identity.

This is already the domain's own definition. `ContentIdentity` records
the digest *of the stored object*, alongside a storage reference that is
*"not part of what the checksum covers"*
(`app/domain/document_identity/content_identity.py:83-85`), and
`resolve_content_identity` refuses to return an identity when the bytes
it streamed and the size the store reported disagree
(`app/domain/document_identity/content_identity.py:208-217`).

The domain value object is reused unchanged. No new checksum type, no
second definition of the algorithm, no re-declaration of the chunk size.
There is one content identity rule in this system and it stays in one
module.

---

## 8. Hash and Checksum Policy

**Algorithm.** SHA-256, reusing `CHECKSUM_ALGORITHM`
(`app/domain/document_identity/content_identity.py:37`). Not chosen
here - inherited, and inherited deliberately, because the pipeline's
entire identity chain already hashes this value under this name.

**Representation.** 64 lowercase hexadecimal characters. Uppercase hex,
base64 and a `sha256:` prefix all name the same bytes and none of them
compares equal to this spelling, so a digest that could arrive in more
than one form is not an identity - it is a value that sometimes matches
itself.

The convention is `ArtifactIdentity`'s, which validates exactly that
shape for its own digests
(`app/domain/artifact_identity/artifact_identity_models.py:92-99`). **But
that validator did not, and does not, constrain a content checksum**: it
checks the *derived output* of `derive_identity`, never the input
content checksum fed into the preimage. Asserting that "the existing
chain would refuse a badly spelled content checksum at construction"
would have been false.

**The enforcement therefore had to be built, and it now lives in the
Document Identity context**, where the value is made:

- `app/domain/document_identity/document_identity_exceptions.py`
  declares `DocumentIdentityError`, the context's base error, and states
  the distinction this rule turns on: a failure reason *"describes
  something true about a document"*, while an exception *"describes a
  caller that asked for something incoherent"* (lines 4-17).
- `app/domain/document_identity/content_identity.py:66` declares
  `CHECKSUM_PATTERN` as `\A[0-9a-f]{64}\Z`, and lines 69-78 declare
  `MalformedChecksumError(DocumentIdentityError)`.
- `ContentIdentity.__post_init__`
  (`app/domain/document_identity/content_identity.py:92-119`) rejects a
  checksum algorithm other than `sha256`, a checksum that is not the
  canonical spelling, and a non-positive size. Its own docstring is
  clear that this rejects nothing that exists today, and says why it
  exists anyway: the guarantee *"should not be 'the only caller happens
  to be correct', which is a property of the call site rather than of
  the identity"* (lines 96-100).

**The two kinds of bad news do not collapse into one, and that is
deliberate.** `identity_of_written_bytes`
(`app/domain/document_identity/content_identity.py:230-266`) checks
`size_bytes <= 0` **first** and returns a typed `EMPTY_CONTENT`
*failure* (lines 251-256), so an empty file never reaches the
constructor's non-positive-size raise. An empty document is a fact about
a document and travels as a value a caller reports; a malformed digest
is a caller error and is raised. Returning the second as a failure
reason would invite a caller to persist it as though a document were at
fault.

**The algorithm travels with the value.** `content_checksum_algorithm`
is stored beside the digest and is never assumed. The reason is already
written twice in the repository: *"a future change of algorithm makes
old identities recognisably old instead of silently incomparable"*
(`app/domain/document_identity/content_identity.py:11-13`, and again at
`app/domain/document_ingestion/ingestion_models.py:103-105`). A stored
digest whose algorithm is implicit becomes unreadable the day the
algorithm changes, and the failure is silent.

**Comparison rule.** Two content identities are equal when **both** the
algorithm and the digest are equal. A digest compared across algorithms
is not a comparison.

**The digest is computed once, during the write.**

This is the substantive change. Before this milestone the file was
written and closed, then re-opened and fully re-hashed, with at least
two more full reads following downstream (§3, whose pre-milestone line
numbers cover both). The rule now is that the write itself hashes the
stream as it writes it and returns the identity along with the path:
`save_file` updates one digest from the same chunks it sends to disk
(`app/services/storage.py:144-156`) and returns a `StoredFile` carrying
both (`app/services/storage.py:93-104, 174`).

Three reasons, in order of weight:

1. **It is strictly stronger.** A digest taken over a separate,
   later read describes the bytes that were there *at read time*. A
   digest accumulated over the bytes being written describes, provably,
   the bytes that were persisted. The existing size cross-check
   (`content_identity.py:208-217`) narrows that window - it catches a
   file that changed length - but a same-length substitution between
   close and re-open passes it. Hashing during the write closes the
   window rather than narrowing it.
2. **It is strictly cheaper.** One pass over the bytes instead of two,
   on the one code path where an arbitrarily large engineering drawing
   is guaranteed to be moving through memory.
3. **It removes a second definition of the truth.** Two hashes of one
   file can disagree. One cannot.

**Constraints the write-side hash inherits and must not lose:**

- **The empty-file refusal.** A zero-byte upload must not be recorded
  with SHA-256's empty digest. That digest is real and well-defined,
  which is exactly the problem: *"recorded as an identity it would make
  every empty document in the system look like the same document"*
  (`app/domain/document_identity/content_identity.py:152-156`). A
  zero-byte upload records no content identity. §19 records the cost of
  that.
- **The domain does not open files.** The streaming hash is an
  infrastructure concern and belongs on the write side of storage. The
  domain keeps owning the algorithm, the chunk size and the value
  object; a fitness function already asserts the domain opens nothing
  (`tests/architecture/test_document_identity_boundaries.py:212`).
- **The downstream re-hashes stay.** Ingestion and canonicalization
  continue to resolve content identity for themselves. That is not
  redundancy to be cleaned up: those reads answer *"what are the bytes
  now"*, and §18's detectability depends on them continuing to ask.

---

## 9. Source Bytes and Normalization Policy

**Decision: none. The source bytes are authoritative and are never
normalized.**

No PDF is re-serialised, linearised or re-saved before hashing. No
workbook is re-zipped, re-ordered or stripped of metadata. No
line-ending conversion, no encoding conversion, no whitespace handling.
The digest covers the file exactly as the engineer's tooling produced
it.

**This is not an aspiration; it is what the code does.** Storage reads a
chunk, writes that chunk and hashes that chunk, and does nothing else to
it (`app/services/storage.py:147-156`). There is no transformation step
between the upload stream and the stored object to disable.

The argument for normalising is real and is refused. Two PDFs that
render identically can differ in producer metadata, object ordering or
an incremental-update trailer, and a normalising digest would call them
the same document version. The refusals:

- **"Renders the same" is a semantic judgement**, and it is one no
  normaliser in a substation context should be trusted to make. ADR-0034
  set the standard the whole chain follows: *"a guess that cannot be
  checked will be wrong silently, on one sheet in fifty"*, and *"a wrong
  answer is worse than a visible error in this domain."*
- **It would make the digest depend on a library version.** A PDF
  normaliser is a parser. Its output changes when it is upgraded, so
  every content identity in the system would change with it - which is
  exactly the property the architecture keeps in the *representation*
  identity, where `parser_name` and `parser_version` are hashed on
  purpose (`app/domain/canonical_pdf/canonical_pdf_identity.py:56-60`),
  and keeps *out of* the root.
- **It would break the one thing this value is for.** ADR-0035 §9
  requires an assertion to pin the content checksum rather than a
  representation identity, precisely so that *"a reader-library
  upgrade"* does not falsely invalidate it at scale. A normalised
  digest is a representation identity wearing the content identity's
  name.

Consequence, stated plainly: **two byte-different files that look
identical to an engineer are two document versions.** That is correct
under this model, it will occasionally surprise someone, and the
alternative is worse.

---

## 10. Metadata Boundary

**Decision: no document metadata is part of the content identity
preimage.**

The preimage is the bytes. Nothing else. Specifically, **none** of the
following affects the digest:

| Excluded | Why it would be wrong |
|---|---|
| `filename` | the checksum's own docstring: *"a checksum that depended on the filename would answer a question nobody asked"* (`content_identity.py:6-8`) |
| the original uploaded filename | the same file re-uploaded under a corrected name would become a different version |
| declared MIME type | client-supplied, and the classifier already treats it as evidence rather than fact |
| `file_path` / storage reference | §11; also already excluded by name in `ContentIdentity`'s own docstring (`content_identity.py:83-85`) |
| `uploaded_at` | a wall-clock reading is not a property of the bytes |
| the uploader | it would make an artifact's identity a function of a person - ADR-0035 §"Attach the assertion to existing provenance" refuses exactly this: *"running the pipeline twice under two logins would produce two different artefacts"* |
| `project_id` | the same drawing filed against two projects is the same bytes; ADR-0005's scope rule is about filing, not content |
| `project_name`, `category`, `revision`, `scope` | mutable registry metadata, changeable after upload without touching a byte |

**`size_bytes` is the one adjacent value, and it is an observation, not
an ingredient.** It is recorded beside the digest, exactly as
`ContentIdentity` records it (`content_identity.py:81-90`), and it is
**not** part of any digest preimage. It earns its place for one reason:
it makes the "did this change" comparison in §18 cheap in the common
case and makes a truncated read visible without a full re-hash. It
proves nothing on its own - two different files of the same length are
routine.

---

## 11. Storage Boundary

**Decision: the storage reference is recorded, is never part of the
identity, and never reaches a public schema.**

`ContentIdentity` already carries `storage_reference` alongside the
digest and already states the rule
(`app/domain/document_identity/content_identity.py:83-85`). What matters
here is that it stops at the API boundary.

**AF-SEC-002** enforces this structurally.
`tests/architecture/test_public_api_boundaries.py:174-200` walks every
public schema's annotated assignments and fails on any field name
containing `path`, `directory`, `storage` or `file_location`. A
companion test applies a **narrower** rule - two fragments, `path` and
`storage` - to one file, the document registry's `document_models.py`
(`tests/architecture/test_public_api_boundaries.py:203-221`), so the
schema cannot leak what its source object does not have.

`DocumentDetailRead` observes this today: it publishes
`content_checksum` and `content_available`, and its docstring states the
distinction - the checksum *"identifies the bytes, never where they
are"*; `content_available` *"answers 'can I download this?' honestly"*
(`app/schemas/document.py:78-86`). This milestone changes neither.

The consequence for §17 is not cosmetic: a storage locator is
**forbidden** in any provenance reference, not merely unnecessary.

---

## 12. Upload Event Boundary

**Decision: an upload event and a document version are different things,
and an upload never merges with an existing document.**

Two uploads of byte-identical files produce **two** `documents` rows,
each recording the **same** content identity. They are not merged,
nothing is concluded from the match, and no comparison is performed.

This reaffirms policy that is already written and already shipped. The
frontend contract states it as an API property: *"There is no `reused`
field: upload does not deduplicate... reporting `reused: false` on every
response would imply a comparison that never happens"*
(`apps/frontend/lib/contracts/document.ts:188-194`).

**Who uploaded** is recorded on the *action*, never on the document.
`app/routers/documents.py:525-533` writes an audit event with the
actor's identity and `AuditAction.DOCUMENT_UPLOADED`
(`app/domain/audit/audit_models.py:51`); a repository-wide search for
`uploaded_by` or `uploader` finds no such column anywhere. That
separation is kept: §10 excludes the uploader from the identity, and
this section excludes them from the document row.

---

## 13. Version Ordering

**Decision: this milestone establishes no ordering over versions. None.**

A digest is an identity. It is not a timestamp, not a sequence, and not
comparable in any way except equality. Nothing here answers "which
version came first", "which is current", or "what did this supersede".

Specifically **not** introduced: `version_number`, `is_current`,
`supersedes`, `superseded_by`, `previous_content_checksum`, or any
accessor shaped like `current_version_of(document)`. ADR-0035 §5 records
why a signature matters more than an implementation here: *"A method
whose signature returns one answer has already decided there is one."*

`uploaded_at` remains what it is: **upload chronology**. It says when a
row was created. It does not say that the file uploaded later is the
later revision of the same drawing - which is routinely false in
practice, because documents arrive out of order.

The pressure this section resists is obvious and will arrive as a
feature request. It is refused here for the same reason §5 refuses two
identities: ordering versions of a document requires lineage, and
lineage is undecided.

---

## 14. Replacement

**Decision: replacement semantics are defined here and implemented
nowhere. No replacement mechanism is built by this milestone.**

Defining without building is deliberate. The next milestone that wants
"replace this document with a new revision" will otherwise invent the
semantics under delivery pressure, and the most convenient invention -
move the evidence across - is the one that destroys the property this
whole chain exists to have.

**What replacement would mean under this model**, if and when it is
built:

1. **Version A is immutable.** Its recorded content identity does not
   change, is not cleared, and is not re-pointed. Every artifact keyed
   to `(document_id, checksum_A)` remains exactly as valid as it was.
2. **Version B gets its own content identity**, computed from its own
   bytes by the same rule. B is never assigned A's identity, and A's is
   never recomputed.
3. **Nothing derived from A migrates to B.** No evidence, no entity, no
   fact, no semantic statement, and no review moves. Each was produced
   by a versioned rule reading *specific bytes*; attaching it to
   different bytes would make its provenance a lie. This is the same
   refusal AF-TRUTH-003 already makes for promotion - *"promotion
   modifies no artefact"* (AF-01 §20) - applied to replacement.
4. **A stays queryable.** Its artifacts, its identity and its audit
   trail remain readable. A conclusion drawn from last year's revision
   must remain explainable, which is the property the canonical tables'
   own docstrings state they exist to preserve
   (`app/models/canonical_pdf.py:32`).
5. **B must be re-derived from its own bytes**, through the ordinary
   pipeline. Nothing is inherited.

**And a successor never inherits a human assertion.** ADR-0035 §9 states
this and this ADR adopts it unchanged: *"Carrying an assertion onto a
re-issued document is a fresh authored act by a named engineer who has
looked at the new revision - never an automatic consequence of lineage,
and never inferred from two documents sharing bytes."* Whatever
replacement mechanism is eventually built inherits that rule before it
inherits anything else.

**What is not decided here**, and is named so it is not assumed: whether
replacement is expressed as a new `documents` row, as a lineage edge
between two rows, or as something else entirely. That is §5's deferred
question and it is still deferred.

---

## 15. Re-ingestion

**Decision: ingestion jobs continue to accumulate, one per attempt, and
each keeps its own checksum. The document's recorded identity does not
move.**

Nothing about `document_ingestion_jobs` changes. Its columns stay, its
non-unique index on `content_checksum` stays, and its deliberate absence
of a uniqueness constraint on `document_id` stays, for the reason it
already gives: the accumulated jobs *"are its audit trail"*
(`app/models/document_ingestion.py:28-34`).

The two values answer different questions, and both are worth keeping:

| Value | Question it answers |
|---|---|
| `documents.content_checksum` | what this document **is** |
| `document_ingestion_jobs.content_checksum` | what one ingestion attempt **saw** |

A re-ingestion that computes the same digest confirms the document. A
re-ingestion that computes a **different** digest is the signal in §18:
the bytes under the document changed. In neither case does the
document's own recorded identity move - §18 is explicit that it is never
silently re-identified.

**And re-ingesting a legacy document does not give it one.** A `NULL`
identity is not filled in by a later attempt any more than a recorded
one is overwritten by it; both are the same forbidden `UPDATE` (§18,
§19). The attempt records what it saw on its own job, which is what that
table is for.

---

## 16. Deduplication

**Decision: none. Equal checksums conclude nothing.**

This is not a new decision and is recorded here only because a column
holding a checksum on the `documents` table is precisely where somebody
will add a unique constraint.

The policy is already written, twice, in the repository:

> **Identity is not deduplication.** Two documents with identical bytes
> get identical checksums, and this milestone draws no conclusion from
> that. Whether a repeated upload is a duplicate, a legitimate re-issue
> under a new revision, or the same drawing filed against two projects
> is a question about the *documents*, not their bytes - and answering
> it here would be inventing a policy nobody has stated.
>
> - `app/domain/document_identity/content_identity.py:15-20`

> Identity is **not** deduplication: identical checksums are recorded
> and nothing is concluded from them.
>
> - `app/domain/document_ingestion/ingestion_models.py:107-108`

Concretely, therefore:

- **No unique constraint** on `documents.content_checksum`. The index is
  non-unique, following the ingestion table's precedent and its stated
  reason.
- **No upload-time lookup** by checksum. The upload path performs no
  "have I seen these bytes" query.
- **No `reused` field** on the upload response
  (`apps/frontend/lib/contracts/document.ts:188-194`).
- **The checksum is not a natural key.** It selects a set of documents,
  not a document.

---

## 17. Provenance

**Decision: the minimum reference a future statement needs about a
source is `document_version_id` + `content_checksum` + a
family-specific in-document locator. A storage locator is forbidden.**

Read the first element carefully. `document_version_id` is the pair
`(document_id, content_checksum)` of §6 - it is a *composite*, not a new
surrogate column, and under §5 it does not become one. Written out, a
provenance reference carries:

1. **which document** - `document_id`;
2. **which version of it** - `content_checksum` (with its algorithm, per
   §8);
3. **where in it** - a locator belonging to one source family.

The third element is deliberately *not* generalised. ADR-0034 forked the
two source families at the root and forbade the spreadsheet family from
borrowing `page`, `block`, `span` or `line`; ADR-0035 §4 refuses a
cross-format locator for the same reason and adds that *"the only
vocabulary general enough to span them is a semantic one."* This ADR
introduces no locator of any kind and does not widen either family's.

**A storage locator is forbidden, not merely unnecessary.** AF-SEC-002
scans every public schema's field names for `path`, `directory`,
`storage` and `file_location` and fails on any match
(`tests/architecture/test_public_api_boundaries.py:174-200`). A
provenance reference that named a stored object would either violate
that invariant directly or smuggle the same value under a different
name. The stored path is private backend state - `save_file`'s own
docstring says the storage reference *"is private backend state and
never leaves the backend"*
(`app/services/storage.py:116-118`) - and it is also **not stable**: the
storage name carries a random suffix
(`app/services/storage.py:77-90`), so it identifies a placement, not
content.

**And provenance is never caller-asserted.** AF-PROV-002 names
`content_checksum` explicitly in its set of governed provenance fields
(`tests/architecture/test_architecture_freeze_af01.py:331-339`) and
fails any route that can persist and accepts one in a body. The content
identity recorded by this milestone is computed server-side during the
write (§8) and is never read from a request. §28 requires a test for
that.

---

## 18. Immutability

**Decision: a document's recorded content identity is written once, at
creation, and no code path ever updates it.**

Concretely:

- It is set in the same unit of work that creates the `documents` row.
- **No service, adapter, route or migration issues an `UPDATE` against
  those three columns**, ever. Not to correct them, not to backfill
  them, not to "repair" them.
- There is no endpoint, no admin action and no script that re-identifies
  a document.

**If the bytes under a document change out of band, that becomes
detectable rather than silently absorbed.** The ordinary downstream
reads already recompute content identity for themselves - ingestion at
`app/services/document_ingestion_service.py:221-227`, canonicalization
at `app/services/canonical_pdf_service.py:174-177` and
`app/services/canonical_spreadsheet_service.py:188` - so a recomputed
digest that differs from the recorded one is a comparison the system can
make.

**It is not repaired.** A discrepancy is a visible, reportable fact
about the document, not a trigger to overwrite the record. Silently
re-identifying the document would destroy the only evidence that
anything happened, and would retroactively re-attribute every artifact
keyed to the old identity. CLAUDE.md §16 states the principle this follows:
*"a wrong answer is worse than a visible error in this domain."*

This milestone does **not** build the reporting surface for such a
discrepancy. It makes it detectable and leaves the reporting to whatever
milestone needs it. That is recorded as debt in §30 rather than implied
as delivered.

---

## 19. Legacy Records

**Decision: existing `documents` rows get a `NULL` content identity, and
keep it permanently. There is no backfill, no backfill script, and no
later route by which a legacy row acquires one.**

This is not a preference. It is what the repository's own fitness
function requires.

`tests/architecture/test_artifact_identity_architecture.py:570-594`
parses every migration and fails if any string constant matches
`insert into`, `update ... set` or `delete from`, or if any call passes
a `server_default` keyword. Its docstring states the reason: *"An
identity computed by a migration would be a claim about a derivation the
migration never saw."* A migration that hashed files and wrote the
results would violate it directly; one that used `server_default` to
manufacture a value would violate it twice over.

The precedent is exact and one revision old. `artifact_identity` is
nullable on every deterministic artifact table, and a companion test
pins that nullability in place:
`test_unknown_legacy_identity_is_never_current_compatible`
(`tests/architecture/test_artifact_identity_architecture.py:557-567`)
asserts `nullable is True` for every stage, because *"`column == None`
renders as `IS NULL` and would pair arbitrary legacy rows."* Legacy rows
were never backfilled and are never treated as matching each other.

The additive, fully-nullable, no-rewrite migration shape is likewise
already established:
`migrations/versions/d5b93e17ca40_add_document_content_identity.py:6-10`
- *"Every column added here is optional... a historical job simply
carries no content identity, which is the truth about it. No existing
row is rewritten and no existing column is altered."*

Therefore:

- **`NULL` means "honestly unknown", never "empty" and never "zero".**
- **Two `NULL`s are never the same unknown.** Any comparison, lookup or
  reuse check must require a real digest on both sides. A `NULL`
  matches nothing, including another `NULL`.
- **A legacy row's content identity stays `NULL` for the life of that
  row.** It is never established later, by any route. There is no repair
  path, no admin action, no reconciliation script, and no conditional
  "write it only if it is `NULL`". Each of those is the `UPDATE` §18
  forbids without exception, and a `NULL` -> value write is precisely
  the case that would otherwise slip through as harmless.
- **The way a legacy document's bytes come to have a recorded identity
  is by being uploaded**, which creates a **new** `documents` row that
  records its identity at creation (§18). That is not a backfill and not
  a repair - it is a new document, with its own id and its own history.
  The system draws no conclusion from the fact that its bytes may equal
  an older row's: §12 keeps the two rows separate and §16 refuses to
  compare them.

This is the `artifact_identity` precedent applied exactly rather than
merely cited. A new identity appears in that chain by deriving into a
**new row**, never by rewriting an old one, and legacy rows were left
unidentified rather than repaired.

**What this costs, stated without softening.** Every document already in
a deployment when this migration runs keeps a `NULL` content identity
for its whole life. It never becomes identified. Any future feature that
requires a recorded identity simply does not apply to it: an assertion
cannot pin it (§27), and a change to its bytes cannot be detected (§18).
The only way such a file participates at all is if somebody uploads it
again, and what they get is a different document. That is a real and
permanent loss, and it is accepted, because the alternative is a
migration or a script writing an identity for bytes it is guessing
about - the exact claim `test_no_migration_fabricates_an_identity`
exists to prevent.

**One honest cost, and it is worse than the column alone suggests.** A
zero-byte upload also records no content identity (§8), so it is
indistinguishable at the column level from a legacy row.

For a **project-scoped** upload there is a signal elsewhere: the upload
runs the pipeline, an ingestion job is written, and that job records the
`EMPTY_CONTENT` failure reason
(`app/domain/document_identity/content_identity.py:55-58`), which a
legacy row's jobs do not carry.

**For a canonical-library upload that signal does not exist.** A
document with no project skips the pipeline entirely -
`_run_document_pipeline` returns `skipped` before choosing a lineage
when `project is None` (`app/routers/documents.py:660-666`) - so **no
ingestion job is created at all**. A zero-byte canonical-library upload
then carries a `NULL` identity and no ingestion job, which is exactly
the pair a legacy row presents - so nothing in the identity columns or
the job table distinguishes them. Other columns may still differ:
`file_format` is classified from the bytes, and zero bytes classify as
unclassified where a legacy PDF does not. That is a coincidence of
classification, not a lineage signal, and it says nothing for a legacy
row that was itself unclassified.

No mitigation is proposed here. The honest statement is that the
distinction holds for one scope and not the other, and that anything
built on "a `NULL` with no job means a legacy document" would be wrong
for canonical-library uploads.

What is still refused is the shortcut: a sentinel value would be worse
than the ambiguity, because it would put a fabricated digest in a column
whose whole purpose is to be trustworthy.

---

## 20. Failure Atomicity

**Decision: the upload's commit is routed through `commit_or_restore`,
and any failure between the write and the commit deletes the stored file
before re-raising. The write-then-commit order is correct and is kept.**

### What was wrong

`app/routers/documents.py:467` was a bare `db.commit()`, and a search
across `app/routers/` and `app/services/` confirmed it was the **only**
raw commit in either tree (§3 notes the one further instance, inside
`commit_or_restore` itself). It was *not* an exception
to a rule the adapters keep: §3 measures 28 raw commits in 17
infrastructure modules against 5 that route through `commit_or_restore`.
The upload was simply the one instance outside `app/infrastructure/`,
and the only one where a file was already on disk.

Two things went wrong when that commit failed:

1. **The session becomes unusable.** SQLAlchemy rolls back internally
   and then requires an explicit `rollback()`; *"until that happens
   every later statement raises `PendingRollbackError`"*
   (`app/database/session_commit.py:11-14`). The upload handler makes
   several further queries after line 467 - the pipeline run at line
   470, the detail read at 472, the audit write at 481 - and each would
   raise.
2. **The file is orphaned.** `save_file` ran at line 445. The bytes are
   on disk under a name nothing now references, and `storage/` is
   excluded from version control (`.gitignore:48`), so nothing will ever
   reconcile it.

### The fix

- **The commit routes through `commit_or_restore`**
  (`app/routers/documents.py:503`). That repairs the session and
  re-raises unchanged, which is the contract it declares: *"the
  component that issued the commit is the component that repairs the
  session, and it repairs it without deciding what the failure means"*
  (`app/database/session_commit.py:29-32`).
- **The compensating block covers the whole window, not just the
  commit.** Everything from immediately after `save_file`
  (`app/routers/documents.py:452`) through the commit runs inside one
  `try` whose handler discards the file and re-raises
  (`app/routers/documents.py:461-510`, with `discard_file` at 509). The
  reason is that a failed commit is not the only way out of that window:
  format classification and row construction can both raise, and a file
  orphaned by either is orphaned just as thoroughly. Narrowing the block
  to the commit alone would have fixed one exit and left two open.
- **`save_file` compensates its own write.** There is one window the
  router's block cannot reach: `identity_of_written_bytes` is called
  with the bytes already on disk, and `ContentIdentity.__post_init__`
  (§8) can raise there. If it did, the caller would never receive the
  path and so could never discard it. `save_file` therefore discards the
  file and re-raises (`app/services/storage.py:158-172`). Unreachable
  while the only digest reaching it is `hexdigest()`, and present for
  the same reason `UnsafeStoragePathError` is: a control that exists
  only because the current caller is careful is not a control.
- **`discard_file` re-checks containment itself.** It resolves the path
  and refuses one outside the storage root with
  `UnsafeStoragePathError`, rather than trusting that its only caller
  passed a path `save_file` already validated
  (`app/services/storage.py:196-210`). Its docstring gives the reason
  this is not redundant: *"a delete whose only safety is that its single
  caller happens to be careful is one caller away from deleting
  something else"* (`app/services/storage.py:190-193`).
- **A failed unlink is logged, not swallowed and not raised**
  (`app/services/storage.py:212-225`). Raising would replace the failure
  the caller is about to report with a filesystem error from the
  cleanup, hiding why the upload failed; silence would leave an orphan
  nothing knows about.

### Why the order is not reversed

Writing the file before committing the row is the correct order and is
kept. The alternative - commit the row, then write the file - fails
worse: a crash between the two leaves a committed `documents` row
pointing at a path with nothing at it. That row is visible in the
registry, appears in listings, and reports `content_available: false`
forever, with no signal distinguishing it from a document whose bytes
went missing later.

An orphaned file is invisible waste. An orphaned row is a lie in the
registry. **The fix is the compensation, not a reorder.**

### What this does not claim

Compensation is best-effort, and this ADR says so rather than implying
atomicity it cannot deliver. If the process dies between the failed
commit and the delete, the file is still orphaned. Closing that case
needs a storage reconciliation pass, which is operational work this
milestone does not do and does not pretend to.

**And there is a case where the compensation is actively wrong.** A
commit can be *in doubt*: the COMMIT is sent, the database applies it,
and the connection drops before the acknowledgement arrives. The driver
raises, the compensating handler runs, and the file is deleted for a row
that **did** land - producing exactly the "orphaned row is a lie in the
registry" state this section argues against, by the mechanism chosen to
prevent the opposite one.

This is not reachable on SQLite, which is what this deployment runs
(`app/database/database.py:5`), because there is no connection to drop
between the process and its own file. It is realistic on PostgreSQL, and
the platform is explicitly built to be portable off SQLite
(`migrations/versions/d5b93e17ca40_add_document_content_identity.py:12-18`
records the same portability concern about enum DDL). So this is a
latent defect of the compensation, named now rather than discovered
during a database migration. Resolving it needs something the
compensation cannot supply on its own - a reconciliation pass, or an
in-doubt check before discarding - and neither is built here.

---

## 21. Determinism

### The content identity is deterministic, and already is

`resolve_content_identity` reads no clock, holds no state and consults
nothing ambient; it is a function of the bytes it streams
(`app/domain/document_identity/content_identity.py:141-227`). Computing
the same digest during the write instead of after it does not change
that. The same file produces the same identity on any machine, in any
process, forever - the property
`app/domain/artifact_identity/artifact_identity_builder.py:4-7` states
the whole chain depends on.

### `document_identity` was absent from `DETERMINISTIC_CONTEXTS`

**Verified before the change.** `DETERMINISTIC_CONTEXTS` declared
exactly fourteen members - `artifact_identity`, `canonical_pdf`,
`canonical_text`, `canonical_spreadsheet`, `spreadsheet_evidence`,
`engineering_evidence`, `engineering_entities`, `engineering_facts`,
`engineering_semantics`, `human_review`, `governed_knowledge_graph`,
`governed_retrieval`, `context_builder`, `engineering_reasoning` - and
`document_identity` was not among them, although it computes the value
that is the **first local component of the deterministic root**
(`app/domain/artifact_identity/artifact_identity_builder.py:159-163`).
The context that produces the chain's input was not named in the list
that constrains the chain.

### Decision: add it. This is a strengthening.

**`document_identity` is added to `DETERMINISTIC_CONTEXTS`, and the
tuple now has fifteen members**
(`tests/architecture/test_architecture_freeze_af01.py:510-549`, the new
entry and its rationale at `:516-524`).

The precedent is written into the list itself. `canonical_spreadsheet`
was added *"because this list is what makes 'a new deterministic
context' a visible edit to the freeze - and because the local test's
forbidden set was narrower than AF-DET-002's, so a spreadsheet module
importing the provider-neutral LLM runtime would have passed every test
in the repository"*
(`tests/architecture/test_architecture_freeze_af01.py:527-532`).

**No equivalent gap existed here, and this ADR does not claim one.** The
`canonical_spreadsheet` precedent is about why the list exists, not
evidence that `document_identity` was unprotected. It was not:

- `test_document_identity_cannot_reach_a_model`
  (`tests/architecture/test_document_identity_boundaries.py:127-137`)
  bans `_AI_MODULES` (lines 89-107) across the whole identity surface;
- and `test_the_identity_domain_holds_no_infrastructure_dependency`
  (same file, `:171-205`) forbids the bare prefix `"app.application"`
  (line 195), which - because the check is a prefix match
  (`_violates`, lines 55-59) - already caught
  `app.application.ports.llm_provider_port`, the one entry in
  AF-DET-002's tuple
  (`tests/architecture/test_architecture_freeze_af01.py:565-572`) that
  `_AI_MODULES` does not name.

Both tests scan `IDENTITY_DOMAIN_ROOT`, which resolves to
`app/domain/document_identity` - **the identical directory** AF-DET-002
walks as `DOMAIN_ROOT / context`
(`tests/architecture/test_architecture_freeze_af01.py:576-577`). Over
that scope the membership adds **no new enforcement whatever**, and on
today's scan root the local test is the stricter of the two: it also
bans `sqlalchemy`, `fastapi`, `pydantic`, `httpx`, the filesystem
modules and five further `app.*` packages.

**What the membership is actually worth**, stated without inflation:

- **It makes the context's deterministic status a visible edit to the
  freeze.** That is the tuple's own stated reason for existing, and it
  is the whole of the first clause quoted above. A reader asking "which
  contexts are deterministic?" now gets the right answer from the
  canonical registry rather than by knowing which local test to open.
- **It is defence in depth.** Two independent tests now assert the same
  rule over the same directory, so deleting or weakening the local
  boundary test no longer silently removes LLM protection from the
  chain's root input. That is a real property, and it is the only
  enforcement property this change adds.

**What adding it costs**, stated honestly:

- AF-DET-002 scans `DOMAIN_ROOT / context` only, so it reaches
  `app/domain/document_identity/**` and **not** the adapter or the
  services, which only the local test covers. The local test remains
  necessary and is not replaced.
- The tuple is fifteen members rather than fourteen, and any test that
  pins its length must be updated in the same change.
- Membership is a visible edit to the freeze document's own scan set,
  which is the point of the list and is the cost worth paying.

**No existing fitness function is weakened, and none is deleted.** The
local `document_identity` boundary tests stay exactly as written.

### What this does not make deterministic

The **upload** is not deterministic and is not claimed to be. It reads
the clock for `uploaded_at` (`app/models/document.py:105-109`) and calls
`secrets.token_hex` for the storage name
(`app/services/storage.py:84`). Neither reaches the digest (§10, §11),
which is precisely why they are allowed to remain. This is the same
distinction AF-01 §12 draws between engineering output and operational
metadata.

---

## 21a. Deferred Defect: the deterministic root is not portable

This section records a defect found while establishing the above. It is
**not fixed by this milestone**, and it is written down here so it is
not rediscovered later at higher cost.

### The defect

`source_identity` folds the database surrogate `document_id` into its
preimage:

```
app/domain/artifact_identity/artifact_identity_builder.py:156-164

    return derive_identity(
        ArtifactKind.SOURCE,
        upstream=None,
        local=(
            ("document_id", str(document_id)),
            ("content_checksum", content_checksum),
            ("checksum_algorithm", checksum_algorithm),
        ),
    )
```

Two consequences follow, and both are real:

1. **Identical bytes uploaded twice produce two different roots**, and
   therefore two entirely parallel artifact chains. Nothing is shared
   between them even though the input to every stage is identical. This
   is consistent with §12 and §16 - the system concludes nothing from
   equal bytes - but it means the root is not a function of the bytes.
2. **The root is not portable.** Restoring a dump into a fresh database
   whose sequence issues different ids would change **every artifact
   identity in the system**. Not one stage: every stage, because the
   root is the upstream of the first derivation and invalidation
   propagates by construction
   (`app/domain/artifact_identity/artifact_identity_models.py:19-23`).

### The documentation contradiction

Two module docstrings state the opposite of what the code does:

- `app/domain/canonical_pdf/canonical_pdf_identity.py:4-5` - *"Its
  upstream is the immutable source content, which is not derived by this
  platform: the chain hangs on the bytes themselves."*
- `app/domain/canonical_spreadsheet/canonical_spreadsheet_identity.py:4-6`
  - *"this lineage, like the PDF one, hangs on the bytes themselves."*

The chain does not hang on the bytes themselves. It hangs on the bytes
**and a row id**. `source_identity`'s own docstring is closer but still
reads past it: *"Composed from what the platform observed about the
bytes and nothing else"*
(`app/domain/artifact_identity/artifact_identity_builder.py:144-145`) -
a row id is not an observation about bytes.

Under CLAUDE.md §11, code and documentation disagreeing is a bug to be
fixed in the same change. **It is not fixed here**, because the honest
fix is the code and the code cannot be changed cheaply. See below.

### What fixing it would cost

Removing `document_id` from the preimage changes how an identity is
composed. That is exactly the change
`ARTIFACT_IDENTITY_CONTRACT_VERSION` exists to version, and its own
policy module states the consequence:

> Raising it re-identifies every artifact in the repository, so it is a
> **migration event and not a routine edit**.
>
> - `app/domain/artifact_identity/artifact_identity_policy.py:17-18`

So the fix is: raise the contract version, re-identify every stored
artifact of all eight persisted kinds, and accept that every stored
identity from before the change is unexplainable under the new contract
unless the old one is kept readable. ADR-0032 governs that contract;
this is squarely its territory, not this milestone's.

### Decision

**Not fixed in this milestone. Recorded, with its cost, so the next
milestone that touches ADR-0032's contract can decide it deliberately.**

### The consequence of deferring, stated plainly

**The two identities this system holds disagree about portability.**

- The content identity recorded by this milestone is **portable**. It is
  a function of bytes and an algorithm name. Restore the database
  anywhere and it still means the same thing.
- The artifact chain rooted at `source_identity` is **not portable**. It
  is a function of bytes, an algorithm name, and a surrogate that
  belongs to one database.

Until the defect is addressed, "this system's identities are stable on
any machine, in any process, forever" is true of the new column and
false of the chain, and any document that states it without qualifying
it is overclaiming.

---

## 22. Backend and API Implications

### No API contract change

**The `documents` response schema gains no field.** `content_checksum`,
`checksum_algorithm` and `size_bytes` are **already public** on
`DocumentDetailRead` (`app/schemas/document.py:88-90`), already nullable,
and already documented there as intentional
(`app/schemas/document.py:78-82`).

### What changes is the field's source, and therefore its meaning

| | Before | After |
|---|---|---|
| Source | the checksum of the most recent ingestion job by row id, no filter on outcome (the pre-milestone `_to_detail`; see §1) | the document's own recorded content identity |
| Single-valued | no - it moves when a new job is recorded | yes - written once, never updated (§18) |
| Present before ingestion | no | **yes**, for any newly uploaded document whose bytes could be identified - a zero-byte upload records none (§8) |
| Present for a legacy row | only if that row has a job | no - `NULL` (§19) |

This **is** a behaviour change to an existing field, and it is recorded
as one rather than described as a bug fix. Two properties change for the
better: the value becomes single-valued, and it becomes correct - it can
no longer be the digest a *failed* attempt computed.

One property changes in a way a client can observe: a document uploaded
and never ingested now reports a checksum where it previously reported
`null` - unless its bytes could not be identified, a zero-byte upload
being the reachable case (§8), where `null` is still the answer. Any
consumer treating `content_checksum != null` as "this document has been
ingested" was already reading the wrong signal -
`ingestion_state` and `ingestion_outcome` are the fields for that
(`app/schemas/document.py:92-93`) - but the misreading becomes visible
now, so it is named.

### OpenAPI is unchanged - and here is how that was verified

The claim is that the generated document does not change. Verification,
step by step:

1. The declaration is `content_checksum: str | None` at
   `app/schemas/document.py:88`. This milestone does not edit that line,
   its type, or its position.
2. The source value object's declaration is `content_checksum: str |
   None` at `app/domain/document_registry/document_models.py:143`. This
   milestone does not edit it either. What changes is inside
   `SqlAlchemyDocumentRegistryRepository` - `_to_detail` now reads the
   three columns off the document row
   (`app/infrastructure/document_registry/sqlalchemy_document_registry.py:203-212`)
   and `_latest_job`'s docstring is rewritten to say it no longer
   supplies the content identity (same file, `:101-111`). Both are
   adapter internals, not schema.
3. The committed `apps/backend/openapi.json` was read directly and shows
   `DocumentDetailRead.content_checksum` as
   `{"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Content
   Checksum"}`, with `content_checksum` present in the schema's
   `required` array. Both are functions of the Pydantic annotation
   alone, which is unchanged.

Since FastAPI derives the schema from the annotation and the annotation
does not change, the document does not change. **This was verified by
inspecting the declarations and the committed OpenAPI document, not by
regenerating and diffing it** - that distinction is stated so the
verification is not read as stronger than it was.

### The upload path

Changes, in order:

- `save_file` computes the digest as it writes and returns it alongside
  the path (§8).
- The separate re-hash is gone: `resolve_document_identity`
  (`app/routers/documents.py:466-473`) is handed the identity the write
  produced instead of computing one. The leading-signature read it also
  performs is a 32-byte prefix read, not a full pass, and is unaffected.
- The `Document` row is constructed with the three identity columns
  (`app/routers/documents.py:478-500`).
- The commit routes through `commit_or_restore`
  (`app/routers/documents.py:503`), inside the compensating block
  described in §20.

### Explicitly not changed

- No route is added, removed or renamed.
- No capability is added. Upload continues to require
  `USE_ENGINEERING_PLATFORM` (`app/routers/documents.py:404-406`).
- `document_ingestion_jobs` is untouched (§15).
- No deterministic artifact table, port, service or identity function is
  touched. `source_identity` keeps its current preimage (§21a).
- No request body accepts a checksum. AF-PROV-002 continues to hold by
  construction, since the value is never read from a request (§17).

---

## 23. Frontend Implications

**No TypeScript type changes.** `DocumentDetail` already declares
`content_checksum: string | null` and `checksum_algorithm: string |
null` (`apps/frontend/lib/contracts/document.ts:107-114`), mirroring the
backend schema, and this milestone does not change either side's
nullability.

**One rendered string becomes rarer, and wrong in every case where it
survives.** The pipeline page renders the checksum, or the literal
fallback `"Non ancora calcolato"` - *not yet calculated* - when it is
null
(`apps/frontend/app/documents/[documentId]/pipeline/page.tsx:171-175`).
After this milestone that fallback is unreachable for a newly uploaded
document **whose bytes could be identified**, and reachable in three
cases. In all three, the words are false:

- **A legacy row that was successfully ingested.** Its checksum *was*
  calculated - by the very ingestion run the same page displays - and
  under §19's no-backfill rule it is now permanently `NULL`. The page
  says "not yet calculated" about a value that was calculated and then
  became unreadable from this field.
- **A legacy row that was never ingested, or whose ingestion failed.**
  Nothing was calculated for it, so the first half is true - but
  §19 makes the identity permanently `NULL`, so "not **yet**" promises a
  computation that will never happen for that row. Only a fresh upload
  produces one, and that is a different document.
- **A zero-byte upload.** Here too nothing was calculated, and here too
  "not **yet**" implies a computation still pending: §8's empty-file
  refusal together with §18's write-once rule guarantee it never will
  be. The string promises an outcome the architecture forbids.

**No frontend production file and no TypeScript type changes**, which is
the substantive point: the declarations are unchanged, as above, and the
string is a caption whose correction is a UI decision rather than an
architectural one. It is recorded so that the inaccuracy is a known one
rather than a discovery.

One frontend **test** file does change, because it asserted the old
meaning. `apps/frontend/tests/document-detail.test.tsx` held a case
requiring a never-ingested document to report no checksum - true before
§22, false after it. It now reads *"reports the identity of a document
that was never ingested"* (line 94), and a sibling case covers the
genuine null - *"reports no checksum for a document that has no
identity"* (line 123), which is §19's legacy row. A test that pins a
behaviour this ADR deliberately changes is not evidence against the
change; leaving it green by weakening it would have been.

**No new UI is built.** No version list, no version switcher, no
"compare versions" control, no replacement flow. §13 establishes no
ordering, so there is nothing to list; §14 builds no replacement, so
there is nothing to drive.

**The frontend already states the deduplication policy correctly** in
its own contract docstring
(`apps/frontend/lib/contracts/document.ts:188-194`), and §16 changes
nothing it would have to retract.

---

## 24. Security

### The collision model, stated honestly

SHA-256 provides approximately **2^128** collision resistance (the
birthday bound) and approximately **2^256** second-preimage resistance,
against a classical adversary and on the current state of public
cryptanalysis. No practical collision attack against full SHA-256 is
known.

That is the whole claim. In particular, this ADR does **not** say the
digest "cannot collide" and does **not** say it "uniquely identifies"
anything. Both are false as stated: a 256-bit function over an unbounded
input space has collisions by counting, and the guarantee is that
finding one is computationally infeasible - not that none exists. Any
future document that upgrades this language to "unique" is overclaiming,
and this sentence exists so the upgrade is a visible edit.

### What is not claimed

A content identity is an **integrity identifier and nothing else**.
Specifically it provides:

- **No authenticity.** It does not establish that the bytes are what
  their claimed author produced.
- **No origin.** It says nothing about who uploaded the file, where it
  came from, or whether the sender was who they said they were. The
  uploader is recorded on the audit event
  (`app/routers/documents.py:525-533`) and is deliberately not part of
  the identity (§10).
- **No non-repudiation.** It is an unkeyed digest. Anyone can compute
  it, so possessing one proves nothing about who produced the bytes.
- **No protection against an actor who can write both the stored bytes
  and the recorded digest.** Someone with write access to the storage
  root *and* to the `documents` table can substitute a file and update
  its recorded identity, and the result is internally consistent.
  Detecting that requires controls this milestone does not build:
  storage integrity, database write auditing, or an external anchor.
  §18's detectability protects against out-of-band modification of the
  *bytes alone* - which is the realistic accident and the realistic
  storage-layer fault - and against nothing stronger.

### These digests must never become a MAC

If some future milestone needs an authenticated checksum, it must not
build one as `H(secret || message)`. **SHA-256 is a Merkle-Damgard
construction and is length-extension vulnerable**: an attacker who knows
`H(secret || message)` and `len(secret)` can compute
`H(secret || message || padding || suffix)` without knowing the secret.
The correct primitive is HMAC-SHA-256, or SHA-3/BLAKE2 keyed modes.

This is recorded because the raw digests introduced here are stored,
public (§11, §22) and convenient, and "just prefix a secret" is the
shortcut that will be reached for.

### Untrusted input

The bytes hashed here are untrusted by definition and are treated that
way: hashing parses nothing, decodes nothing and evaluates nothing. It
streams the file in fixed chunks
(`app/domain/document_identity/content_identity.py:42`, and the write's
own loop at `app/services/storage.py:147-156`). This milestone adds
**no** new parsing of untrusted content anywhere.

The storage-name sanitiser is unchanged in substance and continues to
hold: allow-list, random suffix, and a resolved-path containment check
before anything is written
(`app/services/storage.py:1-21, 65-90, 137-142`). Its containment check
moved when the write loop replaced the copy call, so the lines differ
from earlier revisions while the control is the same one.

**One security control is added.** `discard_file` performs its own
containment check and raises `UnsafeStoragePathError` for a path outside
the storage root (`app/services/storage.py:196-210`), rather than
relying on having been handed a path `save_file` already validated. The
milestone introduces a delete into the upload path, and a delete
defended only by its caller's care is the kind of control that stops
being a control at the next refactor - the same reasoning `save_file`
already applied to its own unreachable branch
(`app/services/storage.py:55-62`). A failed unlink is logged rather than
raised or silently swallowed (`app/services/storage.py:212-225`).

**One pre-existing exposure is not closed here**: there is no upload
size limit anywhere in the backend. It is recorded in the Debt Register.

---

## 25. Alternatives Considered and Rejected

### A separate `document_versions` table

Rejected. It is the design that "sounds correct", and §5 gives the full
argument: a parent/child model must decide which uploads are versions of
the same document, the repository states no answer, the only mechanical
answer available is forbidden by ADR-0035 §9, and the human answer is a
governed act nothing in the platform can perform. The table would be
one-to-one with `documents` for the foreseeable future, and its foreign
key would be a permanent invitation to populate it by inference.

Not rejected forever. When lineage is decided, this is the shape it will
most likely take, and §14 already specifies what it would have to mean.

### Normalize PDF or XLSX content before hashing

Rejected; §9 gives the argument in full. In short: it requires a
semantic judgement about equivalence, it makes the digest a function of
a library version, and it converts the content identity into a
representation identity - which the chain already has, separately and
correctly, with `parser_name` and `parser_version` in its preimage
(`app/domain/canonical_pdf/canonical_pdf_identity.py:56-60`).

### Keep resolving the checksum from the latest ingestion job

Rejected, and it is the status quo, so it deserves a precise refusal.
`_latest_job` takes the highest-id job with no filter on outcome
(`app/infrastructure/document_registry/sqlalchemy_document_registry.py:101-118`),
so the published identity of a document can be the digest a failed
attempt computed. It also moves: a re-ingestion changes the answer to
"what is this document" without a byte having changed. ADR-0035 §9
already rejected it in those terms - *"'most recent attempt' is not a
version handle."*

### Add the outcome filter and keep the job as the source

Rejected as a narrower version of the same thing. Filtering to succeeded
jobs makes the value better without making it a version handle: a
document with no successful ingestion would still have no identity even
though its bytes were hashed at upload, and the value would still be
derived from a queue rather than recorded about the document.

### Hash on read instead of recording a digest

Rejected. It answers "what are these bytes now", which §18 keeps and
needs, but it cannot answer "what were these bytes when the chain was
derived". Without a recorded prior value there is nothing to compare
against, so out-of-band modification is undetectable by construction. It
would also put a full file read on every registry detail request. The
adapter has always refused that - it resolves the detail view from rows
and never from storage
(`app/infrastructure/document_registry/sqlalchemy_document_registry.py:213-214`,
which says the registry *"cannot see storage and does not guess"*) - and
a document list would multiply the cost by the page size.

### Backfill legacy rows with a migration

Rejected, and not on judgement: `test_no_migration_fabricates_an_identity`
(`tests/architecture/test_artifact_identity_architecture.py:570-594`)
fails on any migration containing `insert into`, `update ... set`,
`delete from` or a `server_default`. §19 has the full argument and the
`artifact_identity` precedent.

### Backfill legacy rows with a one-off script instead

Rejected. It routes around a fitness function rather than satisfying it,
which is the behaviour CLAUDE.md §14 forbids - *"do not weaken this
manual to make a shortcut pass"* - and AF-01 §22 says the same about
architecture tests. It would also hash whatever is at each storage path
*today* and record it as the document's original identity, which is a
claim about the past that the script cannot support. There is no route:
a legacy row stays `NULL` permanently, and a fresh upload of the same
file produces a **new** document rather than repairing the old one
(§19).

### Deduplicate on equal checksums

Rejected; §16 quotes the two places the repository already states the
policy. Worth naming the concrete harm: merging two uploads would
destroy a project-scoped filing (the same drawing legitimately belongs
to two projects under ADR-0005), and would silently discard one
document's audit trail.

### Reorder the upload to commit before writing the file

Rejected; §20. It trades an invisible orphaned file for a visible
orphaned registry row, which is strictly worse in a system whose
governing principle is that a visible error beats a wrong answer.

### Fix the `source_identity` surrogate in this milestone

Rejected as scope. §21a gives the cost: a chain-wide re-identification
gated on raising `ARTIFACT_IDENTITY_CONTRACT_VERSION`, which
`app/domain/artifact_identity/artifact_identity_policy.py:17-18` calls a
migration event. Mixing it into a milestone that adds three nullable
columns would violate CLAUDE.md §10's rule against mixing refactoring
with behaviour change, and would put a chain-wide migration behind a
registry improvement.

---

## 26. Non-Goals

None of the following is introduced, designed, prepared for, or made
easier by this milestone. Each is listed because it is a plausible
misreading of what a "document version" milestone might include.

- **`HumanAssertion` implementation.** ADR-0035 remains deferred; this
  ADR discharges its §9 prerequisite and authorises nothing else.
- **An assertion API or UI.** No route, no schema, no control.
- **`Cable`, `CableRun`, `Circuit` or `Terminal`.** No such concept,
  type, column or vocabulary member.
- **Conductor.** Not modelled, not named, not prepared for.
- **An equipment entity.** No equipment concept is created.
- **An engineering hierarchy.** No containment, no parent/child over
  engineering objects.
- **`CONNECTS`, `FROM`, `TO`, `TERMINATES_AT`.** No edge kind, no
  relation, no vocabulary member.
- **Electrical connectivity.** Nothing in this milestone expresses that
  two things are connected.
- **Cross-document engineering identity.** Two documents naming the same
  designation remain two independent sets of observations, per ADR-0034
  §10 and AF-01 §21.
- **P2 expansion.** No reasoning, retrieval or graph capability.
- **Header detection.** Refused by ADR-0034 §6 and ADR-0035 §4, and
  refused again here.
- **Spreadsheet semantic vocabulary.** No word from the prohibited set
  enters anything.
- **Visual evidence.** No rendering, no image, no region.
- **OCR.** None, anywhere.
- **Semantic inference.** Nothing concludes meaning from anything.
- **Automatic engineering classification.** The format classifier
  continues to answer *what kind of file this is*; nothing answers *what
  kind of engineering document this is*.

Two further non-goals specific to this milestone:

- **Document lineage.** §5 names it as undecided and leaves it so.
- **A replacement mechanism.** §14 specifies the semantics and builds
  nothing.

---

## 27. Future Human-Authored Assertions

ADR-0035 is accepted and deferred, gated on this milestone. What it now
has, and what it still lacks.

### What this milestone gives it

ADR-0035 §9 recorded the absence this milestone had to fill - *"There is
no stable single-valued source to resolve it from today, and that is
part of the same prerequisite"* - and observed that *"'The checksum of
document 17' is therefore not yet a question with one answer."* It is
now: the document's own recorded content identity, written once and
never updated (§18), resolvable by a registry read without touching
storage.

ADR-0035 also required that the pin be *the content checksum* rather
than a representation identity, so that *"a reader-library upgrade"*
does not falsely invalidate assertions at scale. §9's refusal to
normalize is what preserves that: the content identity is a function of
bytes alone, and no parser upgrade can move it.

And ADR-0035 required that the pin be resolved server-side and never
accepted in a request body, citing the invariant that names
`content_checksum` among caller-asserted provenance fields. §17 confirms
that invariant - `tests/architecture/test_architecture_freeze_af01.py:331-339`
- and §8 keeps the value server-computed.

### What it still lacks

ADR-0035 §9's stronger sentence is **not** satisfied: *"Assertions are
not implemented until a document can say which document it supersedes."*
A document still cannot say that. §5 explains why this milestone
declines to invent it.

So the position after this milestone is precise, and it is better than
before but not complete:

- An assertion can now **pin a version durably**, and can state exactly
  which bytes of which document it was made against.
- An assertion still **dies with its document** when the file is
  re-issued as a new upload, because nothing relates the two.
- ADR-0035 §9's rule that *"an assertion never propagates to a successor
  version by itself"* is unaffected and remains correct: even when
  lineage exists, inheritance is a fresh authored act.

### What a future assertion milestone inherits from here

- Its source reference is `(document_id, content_checksum)` plus a
  family-specific in-document locator, and **never** a storage locator
  (§17).
- Its pin is resolved server-side, never accepted from a caller (§17).
- Staleness is decided by comparing its pinned checksum against the
  document's recorded one - a comparison that is now possible, and that
  distinguishes *the bytes changed* from *the reader changed* from *the
  representation contract was raised*, exactly as ADR-0035 §9 demanded.
- **A `NULL` identity is not a match.** An assertion cannot pin a
  document that has none (§19).

---

## 28. Testing Contract

The following tests are **required**, not suggested. Each names what it
proves, the layer it belongs to, the invariant, and what breaks without
it - because a test whose failure nobody can interpret is a test nobody
will fix correctly.

Fixtures are synthetic throughout: a few bytes of known content is
sufficient for every row below. **No real project document is ever
committed**, and the repository is public.

| # | What is proven | Layer | Invariant | What breaks without it |
|---|---|---|---|---|
| 1 | Identical bytes produce an identical content identity | domain | the digest is a pure function of the bytes | the same file uploaded twice is two versions, and the pipeline's four `INCONSISTENT_SOURCE_IDENTITY` checks compare noise |
| 2 | Different bytes produce a different content identity | domain | the digest distinguishes content | a changed drawing reuses the old artifacts and an engineer is answered from superseded content |
| 3 | The filename does not affect the identity | service | §10's exclusion holds for the name | renaming a document re-identifies it and orphans every artifact keyed to it |
| 4 | The storage path does not affect the identity | service | §10 and §11 hold for the reference | the random storage suffix (`storage.py:77-90`) makes every upload of one file a different version |
| 5 | The upload timestamp does not affect the identity | domain (structural) + API (behavioural) | no clock enters the preimage | the identity is not reproducible, and tests become time-dependent |
| 6 | The uploader does not affect the identity | API | no actor enters the preimage | the same bytes under two logins are two versions - the failure ADR-0035 refuses by name |
| 7 | `project_id`, scope, category and revision do not affect the identity | domain (structural) + API (behavioural) | §10's metadata boundary holds entire | editable registry metadata silently re-identifies a document |
| 8 | A document's identity columns are unchanged after any later operation, whether they hold a digest or `NULL` | persistence | §18: written once, never updated; §19: a `NULL` stays `NULL` | a document is silently re-identified and the evidence that its bytes changed is destroyed, or a legacy row is quietly identified |
| 9 | No production module, migration or operational script issues an `UPDATE` against the identity columns - including a `NULL` -> value write | architecture | §18 and §19 have no code path that could violate them, and the scan reaches where a backfill would actually be put | §18 and §19 are prose only, and the first "write it only if it is `NULL`" repair makes both false - the case most likely to be waved through as harmless |
| 10 | Re-ingestion records a new job and never writes the document's identity - it neither changes a recorded one nor fills a `NULL` one | service | §15's two-value separation; §19's permanence | "what this document is" and "what one attempt saw" collapse into one mutable value, or re-ingestion becomes the backfill §19 refuses |
| 11 | A `NULL` identity never matches, including another `NULL` | persistence | §19: two unknowns are not the same unknown | legacy rows pair with each other, the failure `test_unknown_legacy_identity_is_never_current_compatible` already names |
| 12 | No migration inserts, updates, deletes or declares a `server_default` | architecture | §19's no-backfill rule | a migration fabricates identities for derivations it never saw - already asserted at `test_artifact_identity_architecture.py:570-594`, and must be seen to still pass with the new migration present |
| 13 | The recorded digest equals a digest recomputed from the stored file | integration | §8: the digest covers the bytes actually persisted | the digest describes something other than what is on disk, and every comparison built on it is meaningless |
| 14 | A zero-byte upload records no identity, and never the empty digest | domain | §8's empty-file refusal survives the move to write-time hashing | every empty document in the system looks like the same document |
| 14b | A content identity refuses a wrong algorithm, a non-canonical digest spelling and a non-positive size at construction - and an empty file still returns a typed `EMPTY_CONTENT` failure rather than raising | domain | §8's representation rule is enforced where the value is made, and a caller error stays distinct from a fact about a document | a digest that compares unequal to itself is recorded and every comparison built on it silently misses; or the two kinds of bad news collapse, and an empty upload is reported as a caller's malformed input |
| 15 | A failed commit leaves no stored file and a usable session | API | §20's compensation and `commit_or_restore` | an orphaned file plus `PendingRollbackError` on the next statement - today's behaviour |
| 16 | A successful upload leaves exactly one file and one row | integration | the compensation does not fire on success | the happy path deletes the document it just stored |
| 17 | No caller can supply a content identity on any route | architecture + API | AF-PROV-002; §17 | a caller asserts what the bytes are, and the pipeline believes it |
| 18 | The public schema declares no storage field | architecture | AF-SEC-002 continues to hold | the stored path leaves the backend - already asserted at `test_public_api_boundaries.py:174-200` |
| 19 | The document detail's checksum comes from the document, not from any ingestion job | infrastructure + API | §22's source change is real | the field silently keeps its old, job-derived meaning while the column sits unused |
| 20 | A document uploaded and never ingested reports its checksum, and a zero-byte upload reports none | API | §22's non-null claim for new uploads, and §8's one exception to it | the milestone's headline improvement is unverified, or the exception is claimed away and an empty upload is expected to carry a digest |
| 21 | No engineering semantics are introduced | architecture | §26 | a milestone about bytes acquires a vocabulary about substations, one plausible name at a time |
| 22 | `document_identity` is named in `DETERMINISTIC_CONTEXTS` | architecture | §21: the registry of deterministic contexts is complete, and the rule has a second enforcer | the canonical registry answers "which contexts are deterministic?" wrongly for the chain's root input, and the rule over that directory rests on one test again |

Rows 8, 9, 12, 17 and 21 are the ones that keep this decision honest
over time. The rest can be re-derived from the model; those five are the
only defence against the boundary eroding quietly.

**What row 9's scan reaches, and what it deliberately does not.** A scan
aimed at the wrong directories is worse than none, because it reports
coverage it does not have. Row 9's first attempt scanned only the
repository-root `scripts/`, which holds `create_administrator.py` and
`export_openapi.py` - neither of which has ever touched `documents`.
**The repository's established home for backfilling a `documents` column
is elsewhere**: `apps/backend/scripts/maintenance/backfill_document_formats.py`
exists to do exactly that for `file_format`, and a loose tracked
`apps/backend/migrate_project_documents.py` rewrites `documents` rows in
hand-written SQL. Both were outside the scan, so the widening missed the
two places a backfill would most naturally be written. The test now
scans both script trees and the loose backend scripts
(`SCRIPT_ROOTS` and `LOOSE_BACKEND_SCRIPTS`,
`apps/backend/tests/architecture/test_document_version_identity_architecture.py:61-74`),
alongside `app/**` and the migrations, and treats a script as
unconditionally in scope rather than only when it is seen to touch a
document row.

The raw-SQL half of that check is **narrowed on purpose**, and the
narrowing is recorded here rather than left to be rediscovered. It once
flagged any string constant matching `UPDATE documents`; it now also
requires an identity column name in the same statement
(`_sql_updates`, same file, `:200-208`). The reason is concrete:
`migrate_project_documents.py` contains **four** such statements,
setting `file_format`, `category`, `revision` and `project_name`, none
of them an identity column. Scanning it with the broad check would have
failed the test for a reason the test does not hold - and a fitness
function that fails for the wrong reason gets weakened by whoever has to
make it green. **The limitation this carries is real**: a statement
assembled from several string constants, with the column name in a
different fragment from the `UPDATE`, would evade it. The check is a
backstop against a hand-written rewrite, not a proof that none can be
expressed.

---

## 29. Migration Strategy

One Alembic revision, following ADR-0008's governance and the shape
`d5b93e17ca40` already established.

**What it does:**

- `op.add_column("documents", ...)` three times:
  `content_checksum` (`String(128)`, nullable),
  `content_checksum_algorithm` (`String(20)`, nullable),
  `content_size_bytes` (`Integer`, nullable).
- One non-unique index on `documents.content_checksum`, for the read
  "which documents recorded these exact bytes?" - and non-unique for
  §16's reason, in the words the existing migration already used
  (`migrations/versions/d5b93e17ca40_add_document_content_identity.py:77-85`).

**What it must not do**, each because a fitness function or a stated
policy forbids it:

| Forbidden | Why |
|---|---|
| any `INSERT`, `UPDATE ... SET` or `DELETE` | `test_no_migration_fabricates_an_identity` (`test_artifact_identity_architecture.py:570-594`) |
| any `server_default` | the same test, same lines |
| `nullable=False` on any new column | it would require a default, which is a fabricated identity by another name (§19) |
| a unique constraint on `content_checksum` | §16 |
| altering any existing column | §19's additive-only precedent |

**Downgrade** drops the index and the three columns, in reverse order,
and is genuinely reversible because nothing else depends on them.

**Rollout.** The column is populated only by new uploads. Existing rows
stay `NULL` permanently (§19). No coordination, no downtime, no data
movement; the migration is DDL only.

**Verification after the migration**, in the order a reviewer should
check them: the full suite is green
(`python -m pytest` from `apps/backend/`); rows 12 and 22 of §28 pass
with the new migration and the new context membership present; and the
committed `apps/backend/openapi.json` is unchanged (§22).

---

## 30. Consequences

### Good

- **"Which version of this document?" becomes a question with one
  answer.** The four domain modules that already phrase their failures
  in those terms (§1) are now talking about something the system can
  state.
- **`content_checksum` on the public document resource becomes
  single-valued and correct.** It stops being whichever ingestion
  attempt happened to have the highest row id, succeeded or not.
- **The digest provably covers the bytes that were persisted.** Hashing
  during the write closes a window the current size cross-check only
  narrows (§8).
- **One fewer full read of every uploaded file**, on the one path where
  arbitrarily large engineering drawings move through the system.
- **Out-of-band modification of stored bytes becomes detectable**, for
  the first time, because there is now a recorded prior value to compare
  against (§18).
- **A failed upload commit stops corrupting the request.** The session
  stays usable and the orphaned file is cleaned up (§20).
- **ADR-0035's §9 prerequisite is discharged in the part that was
  actually blocking**: an assertion can pin a durable, stable,
  single-valued content identity.
- **The deterministic registry becomes complete, and the rule gains a
  second enforcer.** `document_identity` joins `DETERMINISTIC_CONTEXTS`,
  so the chain's root input is named where deterministic contexts are
  named, and two independent tests now cover it. This closes no gap -
  §21 records that the local boundary test already forbade everything
  AF-DET-002 does, over the same directory, and more besides.
- **No API contract changes**, so no client is forced to move.

### Costs and risks

- **An existing public field changes meaning.** §22 records it as a
  behaviour change. A consumer treating a non-null checksum as "this has
  been ingested" was already wrong, but it breaks now.
- **Legacy documents stay unidentified permanently.** There is no
  backfill, none is permitted, and no later route establishes one (§19).
  A deployment gets the benefit only for documents uploaded after this
  migration; everything already in it is excluded for good.
- **`NULL` is ambiguous at the column level.** A legacy row and a
  zero-byte upload both record nothing, and are distinguishable only by
  looking elsewhere (§19).
- **Byte-different files that look identical are two versions.** §9's
  refusal to normalize is correct and will still surprise an engineer
  who re-saved a PDF without changing anything visible.
- **The failure compensation is best-effort.** A process death between
  the failed commit and the delete still orphans a file (§20).
- **The write path now has two responsibilities.** `save_file` writes
  and hashes. That is one more thing in one function, justified by the
  guarantee it buys, and it is a place where a future change could
  quietly drop the hash. §28 row 13 exists for that.
- **§21a's defect is now visible and unfixed.** Writing it down makes
  the gap between the portable new identity and the non-portable
  existing chain a stated property of the system rather than an
  unexamined one. That is the point, and it is also a cost: the
  inconsistency is now on the record.

### Debt recorded, not paid

- **Document lineage still does not exist.** §5 names it undecided; §14
  specifies what replacement would mean and builds none. ADR-0035 is not
  unblocked in full.
- **The `source_identity` surrogate is not removed.** §21a, with its
  cost and the contract-version consequence.
- **Two module docstrings state something the code does not do.** §21a
  quotes both. Fixing the prose without fixing the code would make the
  documentation describe an aspiration; fixing the code is a migration
  event. Left as one item, not two.
- **No surface reports a checksum discrepancy.** §18 makes it
  detectable; nothing surfaces it. The milestone that needs it builds
  it.
- **The downstream full re-reads remain.** Ingestion and canonicalization
  each still hash the file independently (§3). Deliberate - §18 depends
  on them - but the cost is real on large files.

---

## Debt Register

Known, verified, and deliberately untouched by this milestone. Each is
recorded so a future engineer finds it here rather than rediscovering
it. None is caused by this change.

| # | Statement | Where |
|---|---|---|
| a | `revision` is never written by any upload path and publishes the default `"00"` into engineer-facing answers, while the architecture documentation calls it *"The document's own revision, as supplied"* | `app/models/document.py:87-91` (default `"00"`); the upload constructs `Document` without it at `app/routers/documents.py:478-500`; it reaches a composed answer at `app/domain/engineering_response/engineering_response_document_composition.py:86`; the claim is at `docs/architecture/document_management.md:29` |
| b | `BASE_STORAGE` is a relative path and `DATABASE_URL` is anchored differently, so both resolve against the process working directory and they do not agree with each other | `app/services/storage.py:42` (`Path("../../storage")`) and `app/database/database.py:5` (`"sqlite:///./substationos.db"`) |
| c | `find_latest_for_document` serves the newest row id rather than a named version, and no canonical read schema exposes `artifact_identity`, so a caller cannot say which artifact it was given | `app/infrastructure/canonical_pdf/sqlalchemy_canonical_representation_repository.py:114-124` (`order_by(...id.desc()).first()`); a search of `app/schemas/*.py` for `artifact_identity` returns nothing |
| d | No upload size limit exists anywhere in the backend - not on the route, not in middleware, not in storage | `app/routers/documents.py:400-452`; `app/services/storage.py:107-174`; a repository-wide search for `max_upload`, `max_file_size`, `size_limit` and `max_size` finds no limit |
| e | The PDF lineage reads a whole file into memory, unbounded, to parse it | `app/services/canonical_pdf_service.py:377-395` (`b"".join(content_port.iter_chunks(...))`), called at `:219` |
| f | `ArtifactKind.SOURCE` has no table, no repository and no `find_by_identity`, so a derived artifact's `upstream_identity` names a root that resolves to no row | `app/domain/artifact_identity/artifact_identity_models.py:51-53`; `CHAIN` at `tests/architecture/test_artifact_identity_architecture.py:45` enumerates eight persisted artifacts and `SOURCE` is not among them; `upstream_identity` is stored on every derived record, e.g. `app/models/canonical_pdf.py:113` |
| g | Most of the test suite writes uploaded files into the deployment storage root and never cleans up. `tests/conftest.py` isolates the database in memory but does not redirect `BASE_STORAGE`. This milestone's own modules do redirect it, so the fix pattern now exists in the repository - it is simply not applied anywhere else | `apps/backend/tests/conftest.py:48-59` (database isolation only); `app/services/storage.py:42`; of the 29 test modules exercising `POST /documents/upload`, exactly 1 monkeypatches `BASE_STORAGE` to a `tmp_path` (`tests/api/test_document_version_identity_api.py:58`), as does `tests/services/test_storage_content_identity.py:47` for `save_file` directly; the other 28 do not |
| h | The known project lifecycle frontend defect: the detail page derives an available action from a mutability predicate, so a `DRAFT` project is offered "Archivia" - a transition `VALID_TRANSITIONS` does not allow from `DRAFT` - and is offered no control for the one transition it actually needs | `apps/frontend/app/projects/[projectId]/page.tsx:123, 153-176`; `apps/frontend/lib/contracts/project.ts:50-57`; `apps/backend/app/domain/project/project_lifecycle.py:31-49` |
| i | Most adapters still commit raw, so the `PendingRollbackError` exposure `session_commit.py` describes is far wider than this milestone closes. §20 fixes the upload path only. Measured: **28 raw `.commit()` calls in 17 modules** under `app/infrastructure/`, against **5 adapter modules** that route through `commit_or_restore`. Any of the 28 that fails leaves the request's shared session unusable for every later statement, exactly as the upload's did | `app/database/session_commit.py:11-14` (the failure it describes); routed: audit, canonical PDF, canonical spreadsheet, canonical text, document ingestion; not routed, e.g. `app/infrastructure/document_identity/sqlalchemy_document_format_registry.py:53`, `app/infrastructure/project/sqlalchemy_project_repository.py:83`, `app/infrastructure/identity/sqlalchemy_user_repository.py:73, 96`, `app/infrastructure/governed_knowledge_graph/sqlalchemy_governed_graph_repository.py:74, 90, 110, 125` |

Item (h) is the live defect ADR-0035 §11 describes and legislates
against; it is restated here with its locations, not re-decided.

---

## References

- [ADR-0005](0005-project-vs-canonical-library-document-scope.md) - a
  document belongs to exactly one project or to the Canonical Library,
  which is why §16 refuses to merge two filings of one drawing.
- [ADR-0008](0008-database-migration-governance.md) - Alembic governs
  every schema change; §29 follows it.
- [ADR-0023](0023-human-review-append-only-judgement.md) - a
  caller-supplied provenance field is *"a field in which a caller could
  claim to be somebody else"*; §17.
- [ADR-0032](0032-upstream-identity-in-derived-set-reuse.md) - the
  composed identity contract, and the contract version whose raising is
  a migration event; §21a is its territory.
- [ADR-0033](0033-pseudonymous-reference-corpus-provenance.md) - a
  provenance field's name must honestly describe what it holds; §21a's
  documentation contradiction is the same failure.
- [ADR-0034](0034-spreadsheet-canonical-representation.md) - the source
  family fork; every identity composed from one `document_id` and one
  `content_checksum`; *"a wrong answer is worse than a visible error in
  this domain."*
- [ADR-0035](0035-human-authored-document-assertions.md) - the ADR this
  one is the prerequisite for; §9 is this milestone's charter and §27
  reports what it does and does not discharge.
- [Architecture Freeze AF-01](../architecture_freeze_af01.md) - §7 data
  ownership, §8 write authority, §11 provenance, §13 the identity model,
  §20 the fitness functions, §22 the change policy.
- FIPS 180-4, *Secure Hash Standard* - the SHA-256 definition §24 makes
  claims against.
- RFC 2104, *HMAC: Keyed-Hashing for Message Authentication* - the
  construction §24 requires if these digests are ever authenticated.
