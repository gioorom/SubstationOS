# ADR-0034: Spreadsheet Canonical Representation

## Status

Accepted. Introduced by the *Spreadsheet Canonical Representation &
Cable Register Evidence* milestone, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted.

AF-01 §22 classifies this change as neither ordinary evolution nor an
invariant relaxation. It is a **structural addition** - the first fork in
a derivation chain that has been linear since it was built - and is
recorded here for that reason.

Extends the identity contract of
[ADR-0032](0032-upstream-identity-in-derived-set-reuse.md) to a second
source family. Adds no governed vocabulary, no graph capability, and no
engineering semantics.

## Context

### What the platform can and cannot read today

`ClassifiedFormat.XLSX` has existed since Milestone 25.2. The classifier
already separates a spreadsheet from a Word document by MIME and
extension after the ZIP signature honestly abstains - a ZIP header says
"this is a ZIP", not "this is a spreadsheet" - and ingestion already
accepts every classified format, because it orchestrates and does not
read. An uploaded workbook therefore reaches `READY_FOR_EXTRACTION`
today.

It then stops. `SUPPORTED_CANONICALIZATION_FORMATS` admits only PDF, so
the workbook is refused with `UNSUPPORTED_FORMAT`. That refusal is
correct under the current architecture, and it is the whole gap: cable
registers, equipment lists and I/O lists are routinely delivered as
workbooks, and a tabular source is frequently a *higher* confidence
source than the equivalent hand-drawn PDF table, because its structure
is stated by the file rather than inferred from ink.

### Why the PDF representation cannot be reused

The canonical PDF representation is not a general document model. It is
a faithful record of what a *page parser* observed, and every level of
it is page-shaped and `NOT NULL` in the schema: page number, page width
and height, a bounding box on every block and span in PDF user-space
points, a `reading_order` that is explicitly "the index the parser
produced, not a reading order this system worked out", and a block kind
closed at `TEXT` and `IMAGE`.

A worksheet has none of these. It has no page until it is printed, and
print pagination is a rendering decision that changes with the margins.
A cell has a row and a column, not a rectangle; column width is a
display setting, not content. A grid has no parser-supplied reading
order at all. A cell holds a number, a date, a boolean, an error or a
cached formula result, none of which is `TEXT` or `IMAGE`.

Reusing the model would mean writing invented values into `NOT NULL`
columns - exactly what the canonical PDF model forbids when it says it
records what the parser observed, never what the document probably
means.

The same holds one stage down. A `CanonicalTextSection` *is exactly one
PDF page* and a `CanonicalTextParagraph` *is exactly one PDF block*.
Calling a worksheet a section would do to that table what a heading
detector would have done: redefine a level that was named honestly.

### The repository already refuses to fabricate a page

This principle is not introduced here. `document_retrieval_models`
already returns no page references for "documents whose mentions carry
non-page locators (a spreadsheet cell range, a CAD layout) - never a
fabricated page number", and `IndexEntryLocatorKind` already declares
`SHEET` and `CELL_RANGE`. The Engineering Index has honoured the rule
since Milestone 24. The canonical and evidence chain has never had to.

### Where the pressure lands

`EvidenceProvenance` has nine mandatory fields, six of which are PDF
coordinates, all `nullable=False`. Four of them - page number, paragraph
index, line index and the token range - are hashed into the stored
`evidence_key`.

An `EngineeringEvidence` item for a cell therefore cannot exist without
six invented values, four of which would enter a persisted identity.
That is not an inconvenience. Under the evidence model's own rule - "an
observation whose source cannot be located is not evidence; it is an
assertion, and this system does not store assertions" - it would make
the item an assertion.

## Decision

### 1. A spreadsheet is a second source family, forking the chain at the root

`ArtifactKind` gains `CANONICAL_SPREADSHEET` and
`SPREADSHEET_EVIDENCE_SET`. Their upstream is `source_identity` - the
bytes - exactly as `CANONICAL_PDF`'s is:

```
SOURCE ─┬─► CANONICAL_PDF ─► CANONICAL_TEXT ─► EVIDENCE_SET ─► ...
        └─► CANONICAL_SPREADSHEET ─► SPREADSHEET_EVIDENCE_SET
```

The families never meet. Nothing in the spreadsheet lineage imports
`canonical_pdf` or `canonical_text`, and nothing in the PDF lineage
imports the spreadsheet contexts. Both directions are asserted by
fitness function.

### 2. The representation is spreadsheet-native and borrows no PDF word

```
CanonicalWorkbook        one workbook, at one content checksum
  └─ CanonicalWorksheet  one worksheet, at its ordinal position, by its name
       └─ CanonicalRow   one row, by its 1-based row number
            └─ CanonicalCell   one cell, by its 1-based column number
```

The words `page`, `page_number`, `block`, `span`, `bounding_box`,
`reading_order`, `line_index`, `paragraph` and `section` appear nowhere
in this context, and a fitness function asserts it. A worksheet is not a
page and a row is not a line; naming them so would be the same mistake
as calling a heading a section, and every consumer downstream would
inherit it.

### 3. The workbook records; it does not compute

A formula is recorded as the formula text and, separately, the value
some other application cached into the file. Nothing evaluates a
formula. Evaluation depends on a calculation chain, a date system and an
iteration setting, and a value this platform computed would be
indistinguishable in the record from a value the engineer's spreadsheet
computed.

The distinction is structural, not documentary. A cached value is
reachable only through `cell.formula.cached_result` - an object whose
type says the value came from a formula and whose field says it was
cached rather than computed. There is no `CanonicalCell.value` property
that would transparently return literal-or-cached, and the factory
enforces that a cell carries a literal or a formula, never both.

A workbook written by a script and never opened by a spreadsheet
application carries a formula and no cached value at all. That is
recorded as exactly what it is - `cached_result is None`, meaning no
application has ever computed a value into this file for this cell - and
never as a blank cell, an empty string, a zero, or a parse failure.
Those four are lies of different sizes, and the last three would be
indistinguishable downstream from a register that genuinely says nothing
there.

### 4. Absence is the record

A cell with no value and no formula is not materialised. A workbook
declares a grid of 1,048,576 by 16,384 cells; almost all of it is
nothing, and nothing is not an observation. Sparse rows keep the
workbook's own 1-based numbers, so a gap is visible and addressable and
is never re-indexed.

The used range is derived from the cells actually observed, never from
the file's declared `<dimension>` element, which producers routinely
omit or get wrong.

### 5. What the reader does not supply is not modelled

The reader streams in read-only mode, which is what bounds the cost of a
hostile file. In that mode `openpyxl` does not expose merged ranges or
hidden row and column flags. Those fields therefore do not exist on this
model.

The alternative - defaulting a `merged_ranges` field to an empty tuple -
would assert "this worksheet has no merged cells", a claim the parser
never made. Worksheet visibility *is* exposed and is recorded, including
for hidden and very-hidden sheets, which are parsed in full: a cable
register left on a hidden sheet is still what the document contains.

### 6. There is nowhere to record a header

There is deliberately no `header_row`, no `column_name`, no `field_name`
and no `record` anywhere in this model.

Deciding that row 1 - or row 7, after a title block - is a header is an
inference, and it is the same inference `canonical_text` refuses when it
declines to call a bold line reading "TECHNICAL DATA" a section title.
Every structural rule that appears to work has a silent failure mode:
"row 1" breaks on an introductory block; "the first all-text row" breaks
on a register whose first data row is also all text; merged multi-row
headers have no non-semantic rule for which row is *the* header.

Decisively: this milestone forbids semantic matching, so nothing in it
can *validate* a header guess. A guess that cannot be checked will be
wrong silently, on one sheet in fifty, and the wrong answer propagates
as a whole mislabelled register. A wrong answer is worse than a visible
error in this domain.

Header identification belongs to a later milestone that consumes this
model, may use vocabulary this one is forbidden to touch, and can route
its result through human review as the judgement it is. That milestone
loses nothing: exact coordinates, verbatim text, blank-versus-absent and
formula-versus-literal are all already here.

### 7. One adapter opens a workbook, and it receives bytes

`WorkbookReaderPort` declares `reader_name`, `reader_version` and
`read(content: bytes, ...) -> WorkbookReadResult`. Bytes, not a path, so
the adapter cannot open a file or reach storage, and the document
content port stays the one governed route into stored content.

`openpyxl` is imported in exactly one module. It remains forbidden
across the document-identity surface, where an existing fitness function
already bans it. The reader raises nothing and returns a typed failure.
Its name and version are recorded on every workbook and are inputs to
the representation's identity, because a library upgrade that silently
reused the old representation would carry a stale reading through every
stage below.

### 8. Tokenisation is not a persisted stage

Spreadsheet evidence extraction reads `CanonicalWorkbook` directly and
tokenises a cell's text in process, under its own policy version.

This is where the spreadsheet family deliberately diverges from the PDF
one. `canonical_text` exists as a separate persisted artifact because
PDF spans must be *grouped* into lines, paragraphs and sections - real
structural derivation, over which rules change independently of the
parser. A cell is already the atomic addressable unit; splitting its
text on whitespace is not a derivation of comparable weight. Persisting
it as a further deterministic artifact, with its own tables, its own
identity and its own audit entry, would be generality introduced before
any evidence that it is needed.

If tokenisation rules ever do become independently versioned, the stage
can be extracted then, with the evidence to justify it.

### 9. Spreadsheet evidence is a restated family, not a widened one

`SpreadsheetEvidence` carries a `CellEvidenceProvenance` of worksheet
index, worksheet name, row number, column number, column label,
character range and source text. Its `evidence_key` is a SHA-256 over
the same ten-slot shape the PDF family uses, with cell coordinates where
page coordinates stood.

`EngineeringEvidence` and `EvidenceProvenance` are **not** modified.
Their provenance columns stay `NOT NULL`, their key formula stays fixed,
and the fitness function pinning the evidence domain's imports stays
exactly as written.

This is the idiom the repository already uses for this problem:
`CanonicalizationFailureCode` restates five of `IngestionFailureCode`'s
values rather than importing them, with a test asserting they agree,
precisely so that one context's concerns do not leak into another that
has none.

What is reused rather than restated: `EvidenceType`, `EvidenceStatus`
and the pinned rule catalogues. These are shared, stable vocabulary
containing no PDF concept, and reusing them read-only is what keeps
"there is exactly one designation pattern in this system" true. The
extraction catalogue and its pinned fingerprint are untouched.

### 10. The chain stops at evidence

This milestone produces observations about a workbook and nothing else.
Nothing in the spreadsheet lineage imports `engineering_entities`,
`engineering_facts`, `engineering_semantics`,
`governed_knowledge_graph`, `human_review` or the promotion service, and
a fitness function asserts the absence rather than trusting the intent.

**No `Cable`, `Circuit`, `Terminal`, `From`, `To` or `CONNECTS` concept
is introduced anywhere.** A cable register read by this milestone yields
cells containing designation-like text at stated coordinates. That two
of them sit in the same row is an observation about a grid - exactly as
two observations on the same line of a PDF are two observations that
happen to be adjacent, not a property of that equipment. Row adjacency
is a fact about the file; a connection is a judgement, and there is
nowhere in this model to record one.

**No cross-document identity.** Every identity here is composed from one
`document_id` and one `content_checksum`. Two workbooks naming the same
designation are two sets of observations.

## Consequences

### Good

- A workbook becomes a first-class governed source with a deterministic,
  identity-keyed, reusable representation - the same reproducibility
  guarantee a PDF has had since Milestone 26.1, and the first time a
  cable register is readable at all.
- **Nothing is fabricated.** No page number, bounding box, reading order
  or line index is invented for a cell, and no existing `NOT NULL`
  provenance column is loosened. The rule the Engineering Index has
  stated since Milestone 24 now holds across the canonical chain too.
- Every existing invariant, fitness function and pinned catalogue
  survives unedited.
- ADR-0032's identity contract is shown to extend to a second lineage
  with no change to the identity builder - evidence that the primitive
  was designed at the right level.

### Costs and risks

- **Two evidence stores now exist, and nothing downstream consumes the
  second.** Entity resolution reads the PDF evidence repository and will
  not see a spreadsheet observation. That is deliberate for a foundation
  milestone - resolving entities over cell-scoped evidence is a semantic
  question with its own review obligations - but it is real debt, and
  this milestone must not be described as making spreadsheets usable end
  to end.
- **The reuse-boundary audit becomes two lineages.** It was written
  against a flat tuple; expressing a fork is an edit to the audit
  itself, which is exactly the kind of edit that must be justified
  rather than made quietly.
- **`openpyxl` is a new external dependency** in the highest-risk
  position in the system - the one place untrusted bytes are decoded. It
  is confined to one adapter behind one port, so replacing it is a
  re-canonicalisation rather than a rewrite, but the risk is the same
  class as PyMuPDF's.
- **Merged ranges and hidden row flags are not recorded at all**, because
  read-only streaming does not expose them. A later milestone that needs
  them must either accept a non-streaming read and its cost, or read the
  worksheet XML directly.
- **`.xlsm` classifies as `XLSX`.** A macro-enabled workbook is read for
  cells only; macros are never parsed and never executed. This is safe,
  but "we support xlsm" would be heard as more than it is.

### Debt recorded, not paid

- **How entities consume two evidence families is undecided.** It needs
  its own ADR, and the choice - one resolver reading both, or two - is a
  semantic decision this milestone deliberately does not pre-empt.
- **Nothing reads a spreadsheet's structure as a table.** Which row is a
  header, which columns form a record, and what a register's rows denote
  are all open, all inferences, and all out of scope. The first pressure
  on this ADR will be a request for a `header_row` field. It must be
  refused here and answered by a reviewed, versioned rule in a context
  of its own.
- **A number's lexical form is not preserved.** The reader parses a
  numeric cell to a Python value before this system sees it, so for a
  non-integer the file's own characters are already gone. The recorded
  text is the reader's rendering, and is documented as such. Exact
  numeric fidelity would require reading the worksheet XML directly.
- **`.xls` (BIFF), `.xlsb`, CSV and ODS are unsupported**, and are not
  the same problem: a legacy `.xls` is a different container, and CSV has
  no worksheet, no types and a delimiter-guessing problem that deserves
  its own honest milestone.

## References

- [Architecture Freeze AF-01](../architecture_freeze_af01.md)
- [ADR-0032: Upstream Identity in Derived-Set Reuse](0032-upstream-identity-in-derived-set-reuse.md)
- [ADR-0008: Database Migration Governance](0008-database-migration-governance.md)
- [ADR-0006: AI as Interpretation/Presentation Layer](0006-ai-as-interpretation-presentation-layer.md)
- [document_management.md](../document_management.md)
- ECMA-376 / ISO/IEC 29500, *Office Open XML File Formats*
