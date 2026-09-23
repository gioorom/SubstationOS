# ADR-0038: Project Document Search

## Status

Accepted and implemented. Introduced by the *Engineering Document
Search* milestone, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted. No fitness function is deleted and none
is loosened; two are extended (§9).

AF-01 §22 sorts a change into ordinary evolution, or a change requiring
an ADR that names the invariant it alters. This change is neither: it
alters no AF-01 invariant. It is recorded because CLAUDE.md §11 requires
an ADR for a new bounded context and a persistence choice, and this is
both.

---

## 1. Context

An engineer with a real substation corpus cannot find anything. A
project accumulates single-line diagrams, cable schedules and
specifications; the platform canonicalises them faithfully and can
answer nothing as simple as *where does it say TR1?* without opening
every file.

The material to answer that already exists. `canonical_pdf_spans` holds
each run of PDF text verbatim, and `canonical_cells` holds each cell of
each workbook. Neither is reachable by a question. What was missing was
a way to ask.

### What makes this domain-specific rather than generic search

An electrical document is not prose. It is dense with **reference
designations**, and under IEC 81346 the leading character of one is part
of its meaning:

| Prefix | Aspect | Example |
|---|---|---|
| `-` | product (the component) | `-Q1` |
| `+` | location (where it sits) | `+189L` |
| `=` | function (what it does) | `=K1` |

`-Q1` and `Q1` are different designations. A search that tidies
punctuation away before matching - the obvious first implementation, and
the one this milestone started with - asserts they are the same piece of
equipment. Nobody asked it to make that claim, and in a substation it is
the kind of claim that gets somebody hurt.

---

## 2. Decision

Add a bounded context, `document_search`, holding a **searchable
projection** of what canonical representations already say, and one
project-scoped endpoint to query it.

Five decisions define it.

### 2.1 Search is lexical and deterministic

The same query over the same corpus returns the same hits, in the same
order, forever. There is no ranking by similarity, no inference, and no
model. `document_search` is named in `DETERMINISTIC_CONTEXTS`
(AF-DET-002), so reaching for an LLM here is a visible edit to the
freeze rather than a quiet afternoon's work.

This is a limit on purpose, not a stage on the way to something else. An
engineer searching `TR1` is asking which documents say `TR1`. A system
that answered with `TR2` because the two are alike would be making an
engineering judgement it was not asked for and cannot defend.

### 2.2 An aspect prefix is part of the term

Terms are matched whole and case-insensitively, with accents folded, and
with the aspect prefix carried into the term. `-Q1` and `Q1` are
different terms and neither matches the other.

The prefix is taken only when a letter appears in what follows, which is
what separates a designation from arithmetic: `-Q1` and `+189L` are
designations, `-20` is minus twenty, and a cell holding a negative
number stays findable by its digits. A Unicode dash - U+2212 and the
rest - is folded to ASCII `-` rather than deleted, because a PDF
produced by a plotter routinely carries one where the drawing shows a
hyphen, and deleting it produces exactly the collapse this section
forbids.

**Consequence, accepted:** `-20A` cannot be told apart from minus twenty
amps, because nothing in the text tells them apart. It is read as a
designation, which keeps the prefix visible to the reader rather than
silently discarding it.

### 2.3 A spreadsheet segment is a row, not a cell

A reading an engineer would call one fact is spread across a row: `TR1`
in one column, `150` in another, `kV` in a third. Cell-sized segments
would answer "no results" to a query the sheet plainly contains.

The individual cell is not lost. Each row records where its cells begin,
and the exact cell behind a match is recovered from the offset of the
match. A hit reports `C4` when it can justify `C4`, and reports the row
alone when it cannot.

### 2.4 A location is stated or declared unknown, never inferred

A PDF hit names its page; a workbook hit names its sheet and cell.
Where the coordinates are absent the result says the position is not
available. It does not fall back to page 1, and it does not describe one
source family with the other's vocabulary. A page number that is merely
plausible sends somebody to the wrong drawing.

### 2.5 A near miss is reported, never substituted

When a term matches nothing and the project contains the same
designation under a different aspect prefix, the engineer is told so.
The search is not rerun with it. Which designation they meant is theirs
to decide, and this is the same principle as §2.1 applied to an empty
result.

Only a term that matches **nothing on its own** is reported. In
`TR1 XYZ` it is `XYZ` that failed; naming `TR1` because the query as a
whole returned nothing would tell the reader something untrue about
their own query.

---

## 3. The persistence choice

One table, `document_search_segments`, added by migration
`b41d7e9c0a35`. It stores each segment's source text, its normalized
form, its location and - copied from the document it was read from -
`document_id`, `content_checksum` and `project_id`.

### 3.1 It is a projection, and disposable

Every row is derived from a canonical representation that stays
authoritative. Nothing reads this table to establish a fact. Dropping it
loses nothing but the work to rebuild, which is why it carries no
identity of its own and no lifecycle, and why it is absent from the
deterministic identity chain (AF-PROV-*): it derives nothing and
provenance never passes through it.

If the copied `content_checksum` ever disagreed with the document row,
**the document row wins** and this table is rebuilt.

### 3.2 `project_id` is copied, not joined

It is the column every search filters on first. A search that had to
join to find the project would be one refactor away from a search that
forgot to.

**Known consequence.** The copy is taken at index time and is not a
foreign key. Two things follow, both recorded in the Debt Register
below: a document moved between projects would leave a stale index, and
a project id that was reused would let a new project inherit the old
one's text.

### 3.3 Why not SQLite FTS5

FTS5 is available in the SQLite this project runs (3.50.4) and was
rejected. Tests build their schema with `Base.metadata.create_all` while
deployments run Alembic; a virtual table exists in one and not the
other, and this repository has no event listeners to bridge them. A
search proven green against a schema that is not the deployed schema is
not proven.

The plain table costs a scan of one project's text per term. That is
acceptable at the corpus size this milestone targets and is the reason
`MAX_QUERY_TERMS` exists (§4.2). Adopting FTS5 later is a migration and
an adapter change; no domain module would notice.

### 3.4 A second term index over the same bytes

`canonical_text_tokens.normalized_text` already exists and answers
"where does this term appear?" for the token stream. This table is a
second index over the same source bytes, with its own folding rules.

That duplication is accepted rather than overlooked. The two answer
different questions: the token index serves extraction, which needs
tokens and their character spans; this one serves a reader, which needs
the verbatim line, the aspect prefix intact and a position to show. The
folding rules here are deliberately *not* the extraction rules - §2.2
preserves punctuation extraction has no reason to keep. Merging them
would mean one of the two consumers accepting the other's normalization.

---

## 4. Boundaries

### 4.1 Indexing reads representations, never documents

Indexing never parses a file. It reads the canonical PDF spans and the
canonical cells, because those are what this system has agreed is a
faithful reading of the bytes. Re-parsing the original here would create
a second, unreviewed opinion about what a document says.

A document with no canonical representation indexes to nothing. That is
not a failure; it is the honest answer that nothing has yet established
what the document contains.

### 4.2 Search is scoped to a project by the URL

The endpoint is `GET /projects/{project_id}/search`. The port has no
"search everything" method and every repository read applies the project
inside the statement, not to the results afterwards. A caller that could
omit the project would eventually omit it by accident.

`MAX_QUERY_TERMS` (24) and `MAX_QUERY_CHARACTERS` (200) bound the work
one request can buy: every term is a separate scan, and past roughly a
thousand terms SQLite refuses the expression tree outright.

### 4.3 Indexing is wired at the composition root

The upload endpoint calls the indexing service after the lineage has
run. It is not a pipeline stage: indexing reads what the pipeline
produced, and the pipeline's contract is to report where processing
stopped. A store fault while indexing does not fail the upload; anything
else raised from there is a defect rather than a condition to absorb.

### 4.4 Replacing is the only way out of the index

Indexing replaces everything held for a document, so re-processing
cannot double a hit and re-indexing a document that can no longer be
read clears it. There is deliberately **no** deletion operation: this
codebase has no way to delete a document, and a port method for a caller
that cannot exist is a promise nothing keeps.

---

## 5. What this ADR does not decide

- **Whether the Canonical Library is searchable.** Its documents are
  never canonicalised, so today they index to nothing and no
  project-scoped search can reach them. Whether shared reference
  material *should* be searchable, and under what scope, is open.
- **Ranking.** Results arrive in reading order, not relevance order.
  Ordering by relevance is a judgement about which of two documents
  answers better, and this milestone does not make it.
- **Phrase matching.** Terms are combined with AND, so
  `=G1+K2-Q3` matches a row containing `=G1+K1-Q3` and `+K2`
  separately. The reader sees the actual text and can judge it, which is
  why this is a limit rather than a defect - but a composed designation
  is not a searchable unit today.
- **Per-project authorisation.** There is none in this codebase; search
  grants exactly the reach the existing document read endpoints already
  grant.

---

## 6. Debt Register

| # | Debt | Why it is accepted here |
|---|---|---|
| D-1 | `projects.id` is not `AUTOINCREMENT`, while `documents.id` is (migration `8f21c04ab7de`). A hard-deleted project's id could be reused and inherit the previous occupant's indexed text. | Not reachable today: project deletion is a soft lifecycle transition and nothing issues a physical `DELETE`. Closing it is its own migration against the `projects` table and does not belong in this change. |
| D-2 | A document moved between projects would leave a stale index. | No code path moves one: `Document.project_id` is written once, at upload. If a move is ever added it must re-index, and this row is the reminder. |
| D-3 | A soft-deleted project's text stays searchable. | Consistent with `GET /projects/{id}`, which also answers for one; inconsistent with the project list, which hides it. Deciding which is right is a lifecycle question, not a search question. |
| D-4 | Indexing reads `app.models.canonical_pdf` directly, reconstructing lines from spans. | `document_management.md` says consumers should reach PDF structure only through canonical text - but canonical text lines carry no verbatim text, only tokens, and §2.2 needs the source spelling. The existing fitness function pins importers of the canonical PDF *domain* models, not the ORM, so this is permitted by test and contested by prose. Recorded rather than resolved. |
| D-5 | The latest-representation lookup is duplicated from the canonical PDF and workbook adapters rather than reusing their `find_latest_for_document` ports. | Those return whole aggregates; indexing wants four columns. The ordering rule (`id` descending) is identical and was verified against both, but it is correct by duplication rather than by reuse. |

---

## 7. Consequences

**Good.** An engineer can find a designation across a project's
documents and is shown the document, the position and the source text,
with what they searched for highlighted. A designation keeps its
meaning. An empty result explains itself. Indexing happens on upload, so
there is no second step to forget.

**Costly.** A second term index over the same bytes (§3.4). A scan per
term per query. Five pieces of recorded debt.

**Risky.** The index can silently diverge from the representations it
was built from - nothing re-indexes when a representation changes. The
`content_checksum` on every row makes the divergence detectable, and
§3.1 fixes which side wins, but no process currently checks.

---

## 8. Alternatives rejected

- **Normalize punctuation away.** The obvious implementation, and the
  one this milestone began with. It makes `-Q1` and `Q1` one entity,
  which is a false engineering claim (§2.2).
- **Match substrings.** `TR1` would match `TR15`, and `kV` would match
  `kVA`. In this domain a 150 kV transformer and a 150 kVA one are not a
  near miss; they are different equipment.
- **Silently search the prefixed variant when the bare one misses.**
  Helpful, and wrong: it decides which piece of equipment the engineer
  meant (§2.5).
- **Index cells rather than rows.** Loses every query that spans columns
  (§2.3).
- **Semantic or vector search.** Would answer a question nobody asked
  and cannot be defended to an engineer (§2.1).

---

## 9. Fitness functions

| Guard | Change |
|---|---|
| `AF-DET-002` (`test_architecture_freeze_af01.py`) | `document_search` added to `DETERMINISTIC_CONTEXTS`, so no module of this context may import an LLM provider or runtime. |
| `test_bounded_context_dependencies.py` | `document_search` added to `ALLOWED_DOMAIN_DEPENDENCIES` with an **empty** set: it depends on no other context, and acquiring one is a visible edit. |

The domain layer's purity is additionally covered by the existing global
sweeps that forbid `sqlalchemy` and `app.models` imports anywhere under
`app/domain/`.
