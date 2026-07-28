# Document Management and Ingestion

**Status:** As-built reference. Documents themselves have existed since
the earliest milestones but carried no architecture note of their own -
this document closes that gap and describes the **Document Ingestion**
pipeline added in Milestone 25.1, the **Document Identity** context
added in Milestone 25.2, the **Canonical PDF Representation** added in
Milestone 26.1, the **Canonical Text Segmentation** added in Milestone
27.1, and the **consolidation** of every PDF consumer onto that pipeline
in Milestone 26.2. What happens to canonical text after that -
deterministic engineering observation - is
[engineering_evidence.md](engineering_evidence.md). For where documents
sit in the wider
pipeline, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md); for the
scope rule, [ADR-0005](adr/0005-project-vs-canonical-library-document-scope.md).

## The document record

A `Document` (`app/models/document.py`) is the file an engineer uploaded
and the small set of facts the system holds about it:

| Field | Meaning |
|---|---|
| `filename` | The stored name - today the only human-readable title |
| `file_path` | Where the bytes live - the *storage reference* |
| `file_format` | `pdf` / `dwg` / `dxf` / `model_3d` / `xlsx` / `docx` / `image` / `other` |
| `category` | Functional schematic, wiring, cable list, relay settings, … |
| `revision` | The document's own revision, as supplied |
| `scope` | `PROJECT` or `CANONICAL_LIBRARY` (ADR-0005) |

**Every document belongs to exactly one Project, or to the Canonical
Library - never both, never neither.** The upload endpoint enforces that
and refuses a project-scoped upload into a non-mutable project.

`other` means **unclassified** - "nobody has named this format yet" -
and never "examined and found unusable". Every document uploaded before
Milestone 25.2 carries it, because the upload endpoint set no format at
all until then. Those rows stay readable exactly as they are, and the
[backfill command](#backfilling-historical-documents) offers to name the
ones whose bytes can be classified.

## Document identity (Milestone 25.2)

Two deterministic facts about a document's bytes, established without
reading the document:

```
Upload  ->  Format classification  ->  Content identity  ->  Ingestion snapshot
               (signature > MIME        (SHA-256, size,        (recorded on the job)
                > extension)             accessibility)
```

Both come from one place - `app/services/document_identity_service.py`,
over the `app/domain/document_identity` context - so upload and ingestion
cannot disagree about what a document is.

### Format classification

Evidence is gathered from three sources and resolved in descending order
of trust:

| Rank | Evidence | Why it ranks there |
|---|---|---|
| 1 | **Content signature** (leading bytes) | The only evidence the file itself supplies, and the only one a rename cannot change |
| 2 | **Declared MIME type** | What the uploading client claimed |
| 3 | **Filename extension** | A naming convention, not a fact |

The rules live in exactly one module, `format_signatures.py`, and an
architecture test asserts nothing else declares a signature, a MIME map
or an extension map.

- **A readable signature decides, full stop.** If the bytes say PDF and
  the filename says `.dwg`, the format is PDF. The disagreement is not
  discarded - it is recorded as `disagreeing_evidence`, because a file
  whose name contradicts its contents deserves an engineer's attention
  even when the classification is certain.
- **Without a signature, two weak sources that disagree deadlock.** MIME
  and extension are both claims *about* the file rather than facts *from*
  it, so neither can arbitrate the other. The result is `CONFLICTING` and
  the caller decides - choosing one would be an arbitrary classification.
- **A signature that identifies only a container abstains.** `xlsx` and
  `docx` are both ZIP archives, so the ZIP header says "this is a ZIP",
  not "this is a spreadsheet". The classifier records that it looked and
  had no opinion, which is different from having found nothing.
- **Nothing has an opinion -> `UNKNOWN`.** Never a guess.

At most 32 leading bytes are read - the longest signature is 18. That is
never a meaningful amount of a document, and there is no parsing, OCR,
text extraction, embedding or model call anywhere in this context.

### Content identity

| Field | Meaning |
|---|---|
| `checksum` | SHA-256 of the bytes, streamed in 1 MiB chunks |
| `checksum_algorithm` | Recorded, not assumed, so a future change makes old identities recognisably old |
| `size_bytes` | As read |
| `storage_reference` | *Which* stored object was hashed - not part of what the checksum covers |

The same bytes always produce the same identity, whatever the file is
called and wherever it is stored.

An **empty file fails** rather than hashing to SHA-256's empty digest.
That digest is a real value, which is exactly the problem: recorded as an
identity it would make every empty document look like the same document.
If the bytes read disagree with the reported size the attempt fails as a
`CHECKSUM_FAILURE` rather than being recorded - a digest describing bytes
other than the ones reported would be a lie.

> **Identity is not deduplication.** Two documents with identical bytes
> get identical checksums, and this milestone concludes nothing from
> that. Whether a repeated upload is a duplicate, a re-issue under a new
> revision, or the same drawing filed against two projects is a question
> about the *documents*, and answering it here would invent a policy
> nobody has stated.

### Ports

| Port | Question it answers | Adapter |
|---|---|---|
| `DocumentContentPort` | "What is at this storage reference?" | `FilesystemDocumentContentAdapter` |
| `DocumentStorageLocationPort` | "Where are document N's bytes recorded to be?" | `SqlAlchemyDocumentStorageLocation` |
| `DocumentFormatRegistryPort` | "Which documents are unclassified?", and records one format | `SqlAlchemyDocumentFormatRegistry` |

`DocumentContentPort` is **read-only**: `describe`, `read_prefix`,
`iter_chunks`, and nothing else. Its abstract-method set is asserted by
test, so read-only is a contract rather than a convention. `describe`
returning `None` (no such content) is deliberately distinct from a
descriptor reporting `readable=False` (there, but unopenable) - two
different problems for whoever has to fix them.

Three narrow ports rather than one wide one: the first serves the byte
store, the second the document registry. Merging them would give a single
adapter both a database session and a filesystem handle, which is exactly
the breadth this milestone does not grant.

A `storage_reference` is **opaque** to the domain. Today it is a
filesystem path; under an object store it would be a key. No domain code
parses it, joins it to a root, or assumes it addresses a file.

## Ingestion (Milestone 25.1)

Ingestion is the deterministic pipeline a document passes through on its
way to being extractable. Its responsibility is **orchestration,
lifecycle and state** - not extraction.

```
Upload                 (POST /documents/upload - unchanged)
   → Register          (the document repository - unchanged)
   → Create job        request_ingestion   → UPLOADED
   → Queue             queue_ingestion     → QUEUED
   → Execute           execute_ingestion   → PROCESSING → terminal
   → Persist result    every state written as it happens
```

Each stage is a separate call on purpose. A single "ingest this" function
would collapse five distinct facts - accepted, scheduled, started,
concluded, recorded - into one, and the point of this milestone is that a
document's progress is *governed and visible* rather than implied.
`ingest_document` runs all three for callers that do not need to schedule
them separately, and produces an identical record.

### What ingestion explicitly does not do

- **No extraction.** It reads no document contents: no parsing, no text
  extraction, no OCR.
- **No AI.** No LLM, no embeddings, no provider, no Prompt Builder.
- **No knowledge writes.** Neither the Engineering Index nor the Project
  Knowledge Graph. Preparing a document to be extracted from and
  extracting from it are different milestones.

All three are enforced by
`tests/architecture/test_document_ingestion_boundaries.py`, including on
the repository port's own abstract-method set - so the exclusions are a
matter of contract rather than of discipline.

## The lifecycle

```
UPLOADED ──→ QUEUED ──→ PROCESSING ──→ PROCESSED
                ↑                   └─→ FAILED
                └───────── retry ───────┘
```

| State | Meaning |
|---|---|
| `UPLOADED` | A job exists for this document and has not been queued |
| `QUEUED` | Scheduled to run |
| `PROCESSING` | Picked up; the pipeline is running |
| `PROCESSED` | Terminal. The outcome is recorded |
| `FAILED` | Terminal unless retried |

`UPLOADED` is a state of the *job*, not of the document - the document was
already uploaded before any job existed. Keeping it distinct from
`QUEUED` means "accepted" and "scheduled" never become the same fact.

**Every move is validated** against `VALID_TRANSITIONS`
(`ingestion_lifecycle.py`) and an illegal one raises. A job that reached
`PROCESSED` without passing through `PROCESSING` would be a record of
something that never happened. Every state pair is asserted legal or
illegal by test - not a handful of happy paths.

`PROCESSING` is persisted **before** the pipeline runs. A job that fell
over mid-execution would otherwise still read as `QUEUED`, and nothing
would show it had ever been picked up.

`PROCESSED` is terminal: a document needing ingestion again gets a **new
job**, so what was processed when is never overwritten.

## The pipeline's checks

Deterministic, and few on purpose - inventing steps that only look like
work would make the record less honest, not more:

1. **The document exists.** A missing one fails with
   `DOCUMENT_NOT_FOUND`.
2. **Its stored metadata is usable.** A document with no recorded name
   fails with `INVALID_STORED_METADATA`.
3. **The stored format is one this system defines.** See below.
4. **Content identity resolves** (Milestone 25.2) - the bytes are found,
   readable, non-empty and hashable.
5. **The format classifies** (Milestone 25.2) - unknown or contradictory
   evidence fails rather than being resolved arbitrarily.
6. **Metadata is collected** into an `IngestedDocumentSnapshot`.

Steps 4 and 5 run only for a caller that supplied the content ports.
Without them the job runs the metadata-only pipeline Milestone 25.1
shipped - a shallower ingestion, but an honest one: it claims nothing
about content it never examined. "Nobody looked" and "the content is
broken" are different facts and are recorded differently.

The snapshot is a **copy taken at ingestion time**, not a live read. A
document's revision or category can change afterwards, and a job that
silently started describing the current document would make its own
recorded outcome unexplainable. Nothing in the snapshot is derived,
computed or inferred from the document's *contents* - a snapshot that
added a fact would be an extraction.

Since Milestone 25.2 the snapshot also carries `content` (the checksum,
algorithm, size and storage reference) and `format` (the detected format,
its provenance, the stored format and any overruled evidence). Both are
`None` on a job that failed before the step ran, and on every job written
before 25.2 - a historical job reads back as one that examined no
content, which is the truth about it rather than a gap to fill in.

The pipeline itself remains **pure**: it performs no I/O. Content
identity and the leading bytes are resolved by the service through the
ports and handed in, exactly as document metadata already is, which is
what keeps its determinism verifiable rather than merely asserted.

**The stored format is never overwritten by an ingestion.** A document
recorded as `other` whose bytes say `pdf` is not a failure: the snapshot
records both, so the divergence is visible and the backfill can act on it
deliberately rather than a read mutating a document row as a side
effect. If the content changed since a prior job, the new job records the
new checksum and the historical job is left exactly as it was.

### Format policy

**Every format the repository can hold is ingestible**, and all are
treated identically - no drawing-specific behaviour, a DWG passes exactly
the same steps as a PDF.

`other` is included **deliberately**. It is the value a document takes
when nothing classified it, and today's upload endpoint sets no format at
all. Treating it as "unsupported" would mean refusing a document on the
strength of a field nobody ever filled in - the same
absence-of-evidence-is-not-evidence-of-absence error this system refuses
everywhere else, and it would leave the pipeline unable to mark any real
document ready.

`UNSUPPORTED_FORMAT` therefore claims exactly one thing: a format value
this system has no definition of, indicating a row written under a
different schema version. That is a data-integrity condition, not a
judgement about a document.

## The result

| Outcome | Meaning |
|---|---|
| `READY_FOR_EXTRACTION` | The checks passed. **Not** a claim that the document contains anything worth extracting - nobody has read it |
| `FAILED` | A check did not pass; `failure` says which |

`IngestionJob.is_ready_for_extraction` is the one question a future
extraction milestone asks of this record.

## Duplicates, idempotency and retry

- **One job in flight per document.** A second request while one is
  active raises `DuplicateIngestionRequestError`: two jobs racing over one
  document would produce two records of what "the" ingestion concluded,
  with nothing to say which is authoritative.
- **Re-ingestion is a new job.** A document legitimately gets re-ingested
  over its life; the new job is a new record, and the accumulated jobs are
  its audit trail.
- **Idempotent in effect.** The pipeline is deterministic, so two runs
  over an unchanged document conclude identically - only job identity and
  timestamps differ.
- **Retry keeps the same record.** A failed job returns to `QUEUED` on the
  *same* row, incrementing `attempt_count`, because the attempt history
  belongs to the job an engineer is already looking at. Only a failed job
  is retryable.

## Failures

| Code | When |
|---|---|
| `DOCUMENT_NOT_FOUND` | No such document |
| `UNSUPPORTED_FORMAT` | A format value this system does not define |
| `INVALID_LIFECYCLE_TRANSITION` | An illegal move (raised, not recorded) |
| `DUPLICATE_INGESTION_REQUEST` | A job is already in flight (raised) |
| `INVALID_STORED_METADATA` | The document row is unusable - e.g. no recorded name |
| `CONTENT_NOT_FOUND` | The record points nowhere, or carries no storage reference |
| `CONTENT_INACCESSIBLE` | The bytes are there and cannot be opened |
| `EMPTY_CONTENT` | Zero bytes - nothing to identify |
| `CHECKSUM_FAILURE` | The read broke partway, or the content changed while being read |
| `UNKNOWN_FORMAT` | No source had an opinion |
| `CONFLICTING_FORMAT_EVIDENCE` | Two sources disagreed with nothing authoritative to arbitrate |
| `PIPELINE_EXECUTION_FAILURE` | Reserved for a step that fails for a reason genuinely unknown |

Every cause above is **named rather than collapsed** into
`PIPELINE_EXECUTION_FAILURE`. The four content failures send an engineer
to four different places; `UNKNOWN_FORMAT` is a gap where
`CONFLICTING_FORMAT_EVIDENCE` is a contradiction. "Pipeline execution
failure" would tell them none of it.

**A pipeline failure is recorded, not thrown away.** A missing document or
an undefined format produces a `FAILED` *job*, so the attempt stays
visible. Only the two failures where no job could legitimately exist -
duplicate request, illegal transition - raise.

## API

```
POST /documents/ingestion/jobs                 request + queue + execute
POST /documents/ingestion/jobs/{id}/retry
GET  /documents/ingestion/jobs/{id}
GET  /documents/{document_id}/ingestion/jobs
GET  /projects/{project_id}/ingestion/jobs
```

The request body carries **only** a document id - no lifecycle state, no
outcome, no pipeline version, no format override. A caller cannot assert
what ingestion concluded.

A pipeline failure returns **HTTP 201 with a `failed` job**: the request
was well-formed and ingestion answered it correctly. `409` is reserved for
a duplicate request or a retry of a non-failed job; `422` keeps meaning
exactly one thing - a structurally invalid request.

## Persistence

`document_ingestion_jobs`, added by migration `c7a41d8f2b16` and extended
by `d5b93e17ca40` with the content-identity and format columns (both
additive only - no existing table, column or constraint is altered, and
every 25.2 column is nullable, so previously persisted jobs remain
readable unchanged). Deliberately
**no uniqueness constraint on `document_id`**: a document is legitimately
ingested more than once, and the rule that must hold - one job *in
flight* - is about state rather than rows, and could not be expressed as
a column constraint without encoding the lifecycle into the schema.

`content_checksum` is indexed and deliberately **not unique**: "which
jobs saw these exact bytes?" is worth answering quickly, and identical
checksums are recorded without anything being concluded from them.

## Canonical PDF Representation (Milestone 26.1)

```
Document (the uploaded PDF - authoritative, never modified)
    |
    v
Canonical Representation (deterministic, reproducible, versioned)
    |
    v
Future Semantic Extraction (entities, claims, the Engineering Index)
```

The canonical representation is the **single source of truth for every
future semantic extraction**. The original PDF remains authoritative as a
*document* - it is what an engineer signs, prints and archives - but
nothing downstream ever parses it again.

### Why extraction must consume the representation, not the PDF

This is the load-bearing rule of the milestone, so it is worth stating
plainly. A future extractor that opened the original PDF would be
re-decoding bytes that were already decoded once, and that costs three
things this system cannot afford to lose:

1. **Reproducibility.** A representation is a fixed value bound to one
   content checksum, one parser, one parser version and one
   representation version. Re-parsing the same PDF next year under a
   different PyMuPDF release can legitimately yield different text - PDF
   text extraction is not a mathematical constant. If extraction reads
   the PDF, a claim recorded in the Knowledge Graph could silently stop
   being supported by the document it came from, with nothing in the
   system able to show what changed.
2. **Explainability.** "Where did this claim come from?" must resolve to
   a specific page, block and span of a specific representation of
   specific bytes. A path to a file answers none of that. The
   representation carries its own provenance precisely so an engineer can
   reconstruct the chain years later.
3. **One decoding boundary.** PDF decoding is the riskiest,
   most library-coupled operation in the system, and its failure modes -
   encrypted, corrupted, no extractable text - are real and frequent.
   Confining it to one adapter behind one port means every downstream
   milestone inherits *resolved* failures rather than having to handle
   them again, and replacing the library later is a re-canonicalisation
   rather than a system-wide behavioural change.

The `CanonicalRepresentationRepository` port has, deliberately, no method
that returns a path, a handle or raw content. There is no supported way
for a consumer to reach the original bytes through it, which is what
makes the rule structural rather than advisory.

### The model

```
CanonicalPdfDocument      one PDF, at one checksum
  +- CanonicalPdfPage     one page, 1-based, in page order
       +- CanonicalPdfBlock   one parser block, in the parser's own order
            +- CanonicalPdfSpan   one run of same-styled text
```

| Level | Records |
|---|---|
| Document | `document_id`, `content_checksum`, `checksum_algorithm`, `representation_version`, `parser_name`, `parser_version` |
| Page | `page_number` (1-based), `width`, `height` |
| Block | `reading_order`, `kind` (`text` / `image`), bounding box |
| Span | `reading_order`, `line_index`, verbatim `text`, bounding box, font family, font size, bold, italic |

Every level is an immutable value object. A representation cannot be
edited after the fact - only rebuilt from bytes, which is the only thing
that could legitimately change it. There is deliberately **no timestamp**
on the value: when it was built is a fact about the row, and a timestamp
would break the value equality two runs over identical bytes must have.

### What is preserved, and what is refused

Preserved, because the parser supplied it: page number, the parser's own
reading order, verbatim text, bounding boxes, font family, font size,
bold and italic. Image blocks are recorded as observed - with no spans -
rather than dropped, because "there was a figure here" is a fact about
the page. Spans keep the `line_index` they came from, so the parser's own
line grouping is not lost; re-deriving it from coordinates later would be
inference.

Refused, because it would be interpretation:

- no merged paragraphs, no rewritten or repaired text, no de-hyphenation,
  no whitespace normalisation;
- no removal of repeated headers or footers;
- no inferred tables, lists, headings or document sections;
- no engineering entities of any kind;
- no geometric re-ordering of blocks. On a multi-column wiring schedule a
  sorting heuristic would be this system asserting how the page should be
  read - exactly the kind of confident guess that produces plausible
  nonsense three milestones downstream.

There is nowhere in the model or the schema to put any of them, and an
architecture test asserts the columns stay that way.

### The pipeline

```
READY_FOR_EXTRACTION   (an ingestion job said so - Milestone 25.1)
   -> Read PDF         (through DocumentContentPort - Milestone 25.2)
   -> Parse pages      (through PdfParserPort)
   -> Parse blocks
   -> Parse spans
   -> Canonical representation
   -> Persist          (through CanonicalRepresentationRepository)
```

It **starts at `READY_FOR_EXTRACTION` on purpose.** The checksum, the
classified format and the accessibility check ingestion performs are
precisely what make the resulting representation trustworthy; parsing a
document no ingestion job ever accepted would be a second, quieter path
to the same artefact.

The parser port receives **bytes, not a path** - so the adapter cannot
open a file, and Milestone 25.2's content port stays the one governed way
into stored content. An architecture test asserts the signature.

### Supported documents

Only PDF. Everything else - DWG, DXF, spreadsheets, images - produces a
typed `UNSUPPORTED_FORMAT` result. A drawing is not badly-formed text; it
is a different problem, and representing it as text would put nonsense
into the one artefact every future extraction trusts.

**Scanned PDFs remain unsupported.** There is no OCR in this milestone
and no OCR import anywhere in the context. A PDF whose pages carry no
text span at all fails with `NO_EXTRACTABLE_TEXT`, which names an
*observation* and nothing more: it does not claim the document is
scanned, because nothing this milestone reads could support that claim.
Persisting such a representation would hand every future extractor a
document that appears to say nothing - indistinguishable from one that
genuinely does.

### Failures

| Code | When |
|---|---|
| `DOCUMENT_NOT_FOUND` | No such document |
| `UNSUPPORTED_FORMAT` | Not a PDF |
| `NOT_READY_FOR_EXTRACTION` | No ingestion job concluded `READY_FOR_EXTRACTION` |
| `CONTENT_NOT_FOUND` / `CONTENT_INACCESSIBLE` / `EMPTY_CONTENT` | The bytes are missing, unopenable or zero-length |
| `ENCRYPTED_DOCUMENT` | Password-protected. The bytes are intact and someone with the password could read them - a question for whoever supplied the file, not a data-integrity fault |
| `CORRUPTED_DOCUMENT` | Announced itself as a PDF and is not one |
| `PARSER_FAILURE` | The library failed on bytes it accepted - the one genuinely unknown cause |
| `EMPTY_DOCUMENT` | A valid PDF carrying no pages |
| `NO_EXTRACTABLE_TEXT` | Pages, and not one text span anywhere |
| `REPRESENTATION_PERSISTENCE_FAILURE` | Built, and could not be stored |

The five causes shared with ingestion carry identical string values, and
a test asserts they agree. They are **restated rather than imported**:
ingestion answers "may this document proceed?" and knows nothing about
PDF internals, while `ENCRYPTED_DOCUMENT` would mean nothing on an
ingestion job. Two vocabularies, one meaning, no coupling.

No failure persists a partial representation. A half-written one would be
trusted as a whole one.

### Idempotency

Re-running over identical bytes finds the existing representation and
re-uses it - nothing is re-parsed and no second row appears. The API
reports this as `reused: true` with `200` rather than `201`, so the
distinction is observable rather than merely claimed.

Changed bytes carry a different checksum and therefore produce a **new**
representation alongside - never on top of - the old one. Historical
representations stay readable, so a conclusion drawn from last year's
revision remains explainable. A unique constraint on
`(document_id, content_checksum, representation_version)` is the
persistence-level backstop.

### Persistence

Four tables added by migration `b7ded1e07fcd` (purely additive):
`canonical_pdf_representations`, `canonical_pdf_pages`,
`canonical_pdf_blocks`, `canonical_pdf_spans`. They mirror the value
hierarchy rather than holding a serialised blob: the hierarchy is the
contract every future extractor reads, and collapsing it into an opaque
payload would make it unqueryable, unmigratable and unreviewable by
anyone without a Python shell.

Nothing in these tables references or modifies the stored PDF. The
uploaded file is never rewritten, and the `documents` row is never
touched.

### API

```
POST /documents/{document_id}/canonical-representation   build or re-use
GET  /documents/{document_id}/canonical-representation   read the current one
```

`201` when a representation was built, `200` when identical bytes already
had one. A refusal that is a legitimate *answer about the document* - an
unsupported format, an encrypted or corrupted PDF, no extractable text -
returns `200` with a `succeeded: false` result carrying the typed cause,
the same discipline ingestion and the Engineering Engine already follow,
so `422` keeps meaning exactly one thing across this codebase. The three
exceptions are cases where no answer about the document exists: `404` for
a document that is not there, `409` for one no ingestion job has declared
ready, and `500` when the representation was built and storage failed -
this system's fault, not an answer.

### The pre-canonical PDF readers: retired (Milestone 26.2)

Four modules decoded PDFs before the canonical pipeline existed. All four
are **deleted**, and the upload path that used one of them now runs the
consolidated pipeline instead.

| Module | Was | Now |
|---|---|---|
| `app/services/pdf_text_extractor.py` | Live - the upload endpoint's Knowledge Graph path opened the stored PDF directly | Deleted |
| `app/services/pdf_renderer.py` | Unreferenced | Deleted |
| `app/services/document_analyzer.py` | Unreferenced | Deleted |
| `app/services/intelligence/` (`renderer`, `tiler`, `models`) | Unreferenced | Deleted |

`tests/architecture/test_document_pipeline_boundaries.py` asserts both
that the files do not exist and that nothing imports them - the second
check alone would pass against a restored file that nobody had wired up
yet.

## Canonical Text Segmentation (Milestone 27.1)

```
PDF (the uploaded file - authoritative, never modified)
    |
    v
Canonical Representation      what the parser observed
    |
    v
Canonical Text Segmentation   the stable structure over it
    |
    v
Future Engineering Extraction (entities, claims, the Knowledge Graph)
```

The segmentation is the structure every future extractor consumes. It is
built from the Canonical Representation and from nothing else - by this
point in the pipeline the PDF has been decoded exactly once, and nothing
reopens it.

### Why extractors must consume the segmentation, not PDF layout

Milestone 26.1 established why extraction must not re-parse the PDF. This
milestone establishes why it must not work directly against PDF structure
either, even the canonical one.

1. **Layout is not structure, and turning one into the other is a
   decision.** A block, a bounding box and a font size are facts about
   ink on a page. "These lines form a paragraph" and "these tokens are
   one line" are conclusions drawn from those facts. If every extractor
   drew them itself, each would draw them slightly differently - and two
   extractors disagreeing about where a paragraph ends would produce two
   irreconcilable answers about the same document, with nothing to say
   which was right.
2. **The decision is made once, recorded, and versioned.**
   `segmentation_version` is part of the stored key, so when the rules
   change the result is a *new* segmentation stored beside the old one,
   and every conclusion drawn under the old rules stays explainable. A
   heuristic re-implemented inside five extractors has no version and no
   audit trail.
3. **Tokens are the unit extraction actually needs.** An extractor
   looking for equipment designations needs tokens with stable
   boundaries, a deterministic normalised form, and a way back to the
   document. Deriving that from spans on every call is work that would be
   repeated, differently, forever.
4. **The provenance chain survives.** Every token points at the page, the
   block, the span and the exact characters it came from. An extractor
   that started from geometry would have to carry that chain itself, and
   the first one to drop it would break the property the whole system
   depends on: that a claim about a substation can be traced back to the
   document that supports it.

`CanonicalTextRepository` exposes no method returning a page, a block or a
bounding box, so an extractor cannot reach PDF structure through it. An
architecture test additionally pins the set of modules allowed to import
the canonical PDF *models* at all - a future extractor appearing in that
list would be the coupling this milestone removes, growing back.

### The model

```
CanonicalTextDocument      one segmentation, of one representation, under one set of rules
  +- CanonicalTextSection      one page
       +- CanonicalTextParagraph   one PDF block
            +- CanonicalTextLine        one PDF line
                 +- CanonicalTextToken      one whitespace-delimited run inside one span
```

**A section is a page.** Not a chapter, not a heading, not an engineering
section - the page transition is the only division of that size the
parser actually observed. A heading detector deciding "TECHNICAL DATA" is
a section title would be guessing from font size, and every extractor
downstream would inherit the guess as though it were a fact. When a later
milestone learns to recognise real document sections, it adds them as
their own concept; it must not quietly redefine this one.

| Level | Is exactly | Never |
|---|---|---|
| Section | one PDF page | a chapter, heading or engineering section |
| Paragraph | one PDF block, as the parser delimited it | a semantic paragraph, a table, a list |
| Line | one PDF line, as the parser grouped its spans | a sentence, a table row, a field |
| Token | one whitespace-delimited run inside one span | a word, a tag, an equipment reference |

Every level is a frozen value object and **nothing carries a timestamp**,
so segmenting the same representation twice produces values that compare
equal. When a segmentation was built is a fact about the stored row.

### Segmentation rules

Only boundaries the parser already observed are used: **page
transitions**, **block boundaries**, the **line index** Milestone 26.1
preserved on every span, and **whitespace**. Nothing measures a gap,
compares a font size, or decides that a short bold line is a heading.

Empty structures are kept, never pruned. An empty page is still a page,
and dropping it would renumber every section after it and break the
correspondence between a section and the page an engineer is looking at.
An image block becomes an empty paragraph for the same reason.

A token never straddles two spans. A word split across a style boundary -
"MV" in bold followed by "switchgear" - yields two tokens rather than one,
because a merged token would point at no single span, and the provenance
chain is worth more than the tidier word.

### Token normalisation

Two forms are stored for every token: `text`, the original substring
verbatim, and `normalized_text`, its deterministic normalisation. Neither
substitutes for the other - the original is what the document says, the
normalised form is what two documents can be compared on.

The rule is **Unicode NFKC, then strip surrounding whitespace**. That is
all of it: a pure function of the input string, with no dictionary, no
locale and no configuration.

Explicitly not done: no case folding (`mV`, `kV` and `MV` are three
different things); no abbreviation expansion (`CB` is not "circuit
breaker" - that is an ontology lookup wearing a normaliser's clothes); no
spelling correction (a misspelling in a technical document is evidence
about the document); no engineering normalisation (no splitting value
from unit, no decimal-separator conversion, no conversion of any kind);
no stemming or stop-word removal.

> **The known cost of NFKC, stated plainly.** It folds superscripts, so a
> cable cross-section written `mm²` normalises to `mm2` - a real loss of
> a distinction an electrical engineer cares about. It is acceptable only
> because `text` preserves the original verbatim and the provenance
> points at the exact characters, so nothing is destroyed. A test pins
> this behaviour so that changing it has to be deliberate; changing it
> means bumping `CANONICAL_SEGMENTATION_VERSION` and re-segmenting, which
> is what that version is for.

### Provenance

Every token carries the full chain:

```
document -> page -> block -> span -> character range
```

The character offsets are into the originating span's own text, so the
substring can be recovered and checked against the Canonical
Representation without re-parsing anything. An extractor that concludes
something from a token can point at the exact characters it came from -
and a claim about a substation whose evidence cannot be located in a
document is not evidence, it is an assertion.

The chain is stored **as columns on the token row**, not as joins up the
hierarchy: "find this term and tell me exactly where it sits" is the read
every future extractor performs, and it must not cost four joins.

### Failures

| Code | When |
|---|---|
| `CANONICAL_REPRESENTATION_MISSING` | The document has not been canonicalised |
| `INVALID_CANONICAL_REPRESENTATION` | A stored representation no longer satisfies its own invariants - caught on read, before segmentation begins |
| `UNSUPPORTED_REPRESENTATION_VERSION` | Built under a contract this segmenter does not know. Refusing is the only safe answer: a newer representation may carry fields this code would silently misinterpret |
| `SEGMENTATION_FAILURE` | The segmenter failed, or the representation yielded no tokens at all |
| `REPRESENTATION_PERSISTENCE_FAILURE` | Built, and could not be stored |

The one code shared with Milestone 26.1 carries an identical value and a
test asserts they agree. It is restated rather than imported: two
contexts, two vocabularies, no coupling.

A representation that segments to zero tokens is **not persisted**.
Storing it would give every future extractor a document that appears to
say nothing - indistinguishable from one that genuinely does.

### Idempotency

The stored key is `(document_id, content_checksum, segmentation_version)`.
Re-running finds the existing segmentation and re-uses it - nothing is
recomputed and no second row appears, reported as `reused: true` with
`200` rather than `201`. A new checksum (the document changed) or a new
segmentation version (the rules changed) produces a new segmentation
**alongside** the old one, so a conclusion drawn under last year's rules
stays explainable.

### Persistence

Five tables added by migration `26978efc7d15` (purely additive):
`canonical_text_documents`, `canonical_text_sections`,
`canonical_text_paragraphs`, `canonical_text_lines`,
`canonical_text_tokens`. `normalized_text` is indexed - "where does this
term appear?" is the question this table exists to answer.

Nothing in these tables references or modifies the canonical
representation's own tables, the document row, or the stored PDF. A
segmentation is derived *from* a representation, and deriving something
must never modify what it was derived from.

### API

```
POST /documents/{document_id}/canonical-text   segment or re-use
GET  /documents/{document_id}/canonical-text   read the current segmentation
```

`201` when a segmentation was built, `200` when it was re-used, `404`
when the document has no canonical representation, `500` when the
segmentation was built and storage failed. Everything else returns `200`
with a `succeeded: false` result carrying the typed cause, so `422` keeps
meaning exactly one thing across this codebase.

## The consolidated pipeline (Milestone 26.2)

```
Upload
   |
   v
Ingestion                      lifecycle, governed acceptance   (25.1)
   |
   v
Document Identity              checksum, classified format      (25.2)
   |
   v
Canonical PDF Representation   the only PDF decode in the system (26.1)
   |
   v
Canonical Text Segmentation    the structure consumers read      (27.1)
   |
   v
Existing Knowledge Graph consumer
```

Four statements govern this arrangement, and every one of them is
enforced by an architecture test rather than by convention:

1. **The original document remains authoritative.** It is what an
   engineer signs, prints and archives. Nothing in this system modifies
   it, and every artefact below describes it rather than replacing it.
2. **The canonical PDF representation is the parsing source of truth.**
   It is produced by exactly one adapter -
   `app/infrastructure/canonical_pdf/pymupdf_parser.py` - which is the
   only module in the entire application permitted to import a PDF
   library.
3. **Canonical text is the only supported input for semantic consumers.**
   Anything that interprets a document reads the segmentation, through
   `CanonicalTextRepository` or text assembled from it.
4. **No downstream consumer may decode the PDF independently.** The
   closed list of modules allowed to reach stored bytes is asserted by
   test, and Milestone 26.2 made it *smaller*.

### What the upload endpoint does now

`POST /documents/upload` stores the file, classifies its format, records
the document - and then calls **one application workflow**,
`document_pipeline_service.process_uploaded_document`, which sequences
ingestion, canonicalisation and segmentation and hands the assembled text
to the Knowledge Graph.

The router constructs adapters and maps the result onto the response. It
contains no parsing, no sequencing rules and no processing decisions; a
test asserts it never calls the ingestion, canonicalisation or
segmentation services directly, because re-sequencing them in the API
layer would put a second, divergent pipeline there.

**A pipeline failure never fails the upload.** The document is stored,
identified and recorded whatever the Knowledge Graph makes of it - losing
an uploaded file because a downstream analysis stumbled would be the
worst possible trade.

### Failures, by stage

The workflow reports **which stage stopped it** and carries **that
stage's own typed code**, rather than translating everything into a
fourth vocabulary:

| Stage | Reports |
|---|---|
| `ingestion` | An `IngestionFailureCode` - `content_not_found`, `empty_content`, ... |
| `canonical_representation` | A `CanonicalizationFailureCode` - `unsupported_format`, `encrypted_document`, `corrupted_document`, `no_extractable_text`, ... |
| `segmentation` | A `SegmentationFailureCode` - `unsupported_representation_version`, ... |
| `text_assembly` | `no_extractable_text` |
| `downstream_consumer` | `downstream_consumer_failure`, with the consumer's own error in the detail |

The endpoint's `knowledge_graph.status` keeps the exact vocabulary it has
always had - `skipped`, `completed`, `no_text`, `unsupported_file_type`,
`failed` - so a client reading only that field sees no change. Beside it,
`knowledge_graph.failure` now names the stage and the typed cause, so
"failed" is no longer the end of the story.

### Text assembly

Where a consumer needs a string, one is rendered from the segmentation by
`canonical_text_assembler`:

```
for each page that produced text, in page order:
    "--- PAGINA {page_number} ---"
    lines joined by a newline, paragraphs by a blank line
pages joined by a blank line
```

It uses **original token text, never the normalised form**. This is the
rule that matters most: `normalized_text` is NFKC-folded, which turns
`mm²` into `mm2`, and feeding that to a semantic consumer would silently
degrade the engineering text it reads. Superscripts, subscripts, Greek
letters and electrical symbols reach downstream exactly as the document
wrote them, and regression tests assert it.

The page marker is kept verbatim from the retired extractor, because that
string is part of what the consumer reads and changing its wording would
change that consumer's input for no reason anybody asked for.

**Two deliberate differences** from the pre-26.2 text, neither of which
changes the characters a designation is made of:

1. Runs of whitespace inside a line collapse to a single space, because
   tokenisation discarded the original spacing (Milestone 27.1).
2. Paragraph transitions are a blank line, where the old output used a
   single newline.

## What consumes canonical text (Milestone 28.1)

```
Canonical Text Segmentation
    |
    v
Engineering Evidence Extraction   deterministic rules, versioned, no LLM
    |
    v
Future Entity Resolution -> Future Knowledge Graph Population
```

Milestone 28.1 added the first governed consumer of canonical text:
**Engineering Evidence Extraction**. It observes designations, voltages,
currents, powers and cable sections using a small versioned rule
catalogue, and records each observation with full provenance back to the
characters that produced it.

It is emphatically **not** knowledge construction. An evidence item says
a pattern was seen at a place under a named rule; it does not say what
entity it belongs to, and a quantity beside a designation is two
observations rather than a property. See
[engineering_evidence.md](engineering_evidence.md) for the full contract,
the rule and unit catalogues, and the reasons `MANUFACTURER_NAME` is
absent.

The relevant rule for *this* document: extraction reads canonical text
and nothing else. It has no content port, no parser and no PDF library,
so the pipeline described above remains the only route from a stored file
to anything that interprets it.

## Backfilling historical documents

Every document uploaded before Milestone 25.2 is stored as `other`. The
backfill names the ones whose bytes can be classified:

```
python -m scripts.maintenance.backfill_document_formats            # report only
python -m scripts.maintenance.backfill_document_formats --apply    # write
```

**Dry run by default.** Without `--apply` nothing is written - the same
code path decides either way, so the report *is* the run minus the write.
This is also why `record_format` sits on its own narrow port: nothing
calls it during a read, and no ingestion rewrites a document row as a side
effect of examining it.

**Deterministic.** Documents are examined in ascending id order through
the same classifier upload and ingestion use, so two runs over unchanged
data produce the same report.

| Action | Meaning |
|---|---|
| `RECLASSIFIED` | The bytes named a format; `--apply` records it |
| `CONTENT_UNAVAILABLE` | Missing, unreadable or empty - left as `other` |
| `LEFT_UNCLASSIFIED` | Nothing had an opinion - left as `other` |
| `CONFLICTING_EVIDENCE` | Sources disagreed - left as `other` |

It never invents a format, writes only `file_format`, and skips documents
already classified - overwriting a format somebody may have set
deliberately is not its job. It is idempotent: once a document is
classified it is no longer among the rows the backfill examines.
