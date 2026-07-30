# Engineering Workspace (EPIC 30.2)

> **Route:** `/documents/{document_id}/workspace`
> **Status:** read-first. No engineering knowledge is created or edited
> here. Since EPIC 30.4 an engineer may record a **judgement** about a
> semantic statement — appended to the separate Human Review context,
> which changes no pipeline artefact. See §13.

---

## 1. What the Workspace is for

By the end of EPIC 30.1 the platform could produce engineering claims:

```
Document
  → Canonical Representation
  → Canonical Text
  → Engineering Evidence
  → Engineering Entities
  → Engineering Facts
  → Engineering Semantic Statements
```

What it could not do was let an engineer *check* one. The Pipeline page
reports that the stages ran; it does not answer "why does the system
believe `TR1` has a rated power of 630 kVA, and where on the drawing does
that come from?".

The Workspace answers exactly that, by making the support chain
navigable in both directions:

```
Semantic Statement
  → Engineering Fact
  → Engineering Entity
  → Engineering Evidence
  → Canonical Source Location
  → Original Document
```

## 2. Pipeline UI vs Engineering Workspace

The two pages are deliberately separate routes with separate questions.

| | Pipeline (`/pipeline`) | Workspace (`/workspace`) |
|---|---|---|
| Question | Did the pipeline run? | What does the platform claim, and why? |
| Audience | Operator | Engineer validating output |
| Content | Stage state, counts, versions, re-use | Artefacts, support chains, source locations, diagnostics |
| Actions | **Run** a stage | **Inspect**, and record a review (EPIC 30.4) - never edit an artefact |
| Failure meaning | A stage failed | A read failed; other stages stay inspectable |

Neither page is a superset of the other, and the Workspace deliberately
offers no way to run a stage: an engineer who is validating output
should not be able to change it from the same screen.

## 3. Architectural position

**The Workspace is a projection over governed artefacts.** It presents,
navigates, filters, groups, highlights and explains. It does not
interpret.

The frontend never:

- reinterprets a quantity, or does arithmetic on one;
- creates semantic meaning, or renames a predicate into one;
- merges entities, or decides two artefacts are the same;
- infers a support relationship;
- guesses a source location;
- classifies evidence;
- recomputes any pipeline output.

Every relationship it draws comes from a key the backend wrote down:

| Relationship | Backend field it comes from |
|---|---|
| entity → evidence | `EngineeringEntity.evidence[].evidence_key` |
| fact → entities | `fact.subject_entity_key`, `fact.object_entity_key` |
| fact → evidence | `fact.support[].evidence_key` |
| statement → facts | `statement.supporting_fact_keys` |
| statement → quantity | `statement.object_entity_key` |
| evidence → page/line | `evidence.provenance.*` |
| evidence → rectangle | `(page_number, block_reading_order, span_reading_order)` |

`tests/workspace-architecture.test.ts` asserts this structurally: it
fails if a fuzzy-matching library is imported, if two artefacts are ever
compared by `observed_text` or by quantity value, if a rule identifier is
declared in frontend code, or if a write appears.

## 4. Support chain: composition, not a new endpoint

EPIC 30.2 §11 asked for one governed strategy. **Composition was chosen,
and no support-chain endpoint was added.**

The reason is that the four artefact endpoints already return their
document's whole set, with every support reference inline:

```
GET /documents/{id}/engineering-evidence   -> every observation + provenance
GET /documents/{id}/engineering-entities   -> every entity + its evidence refs
GET /documents/{id}/engineering-facts      -> every fact + support + diagnostics
GET /documents/{id}/engineering-semantics  -> every statement + fact keys + diagnostics
```

So the entire chain for every statement in a document costs **four
requests, once**, and every traversal afterwards is a `Map` lookup in
`lib/workspace/model.ts`. There is no request fan-out to avoid, and a
projection endpoint would have duplicated data the client already holds
while adding a second place where support could be described.

If a document's artefact sets ever become large enough that reading them
whole is wrong, the right answer is server-side paging on the existing
endpoints - not a parallel projection of the same relationships.

## 5. The one API addition

```
GET /documents/{document_id}/canonical-representation/pages/{page_number}
    -> CanonicalPdfPageRead
```

Read-only, and a strict projection of the stored representation: the same
bytes the full read returns for that page, selected rather than
recomputed. An API test asserts that equality page by page.

It exists because the canonical page map renders one page at a time. The
full representation of a 200-page drawing set carries every span, style
and rectangle of every page; transferring all of it to draw one page
would be the difference between a usable viewer and an unusable one.

`404` covers both "never canonicalised" and "no such page". Page numbers
are not identities: asking document B for a page only document A has is a
404, not A's page.

## 6. Document viewer decision

Two views, and the distinction between them is the point.

### Mappa canonica (default)

An SVG rendering of the canonical representation: each span drawn at the
`bounding_box` the parser recorded, inside a `viewBox` of the page's own
`width`/`height`. **Highlights live here**, because here every rectangle
is a governed coordinate rather than a guess about where rendered text
sits.

### Originale

The document's own bytes, from `GET /documents/{id}/content`, in an
`<iframe>` handed to the browser's built-in PDF viewer, positioned with
the standard `#page=N` open parameter. Authoritative, and deliberately
un-annotated.

### Why not PDF.js / react-pdf

| Criterion | Native embed + canonical map | PDF.js / react-pdf |
|---|---|---|
| Navigate to a page | Yes (`#page=`) | Yes |
| Highlight overlays | Yes, on the canonical map, at governed coordinates | Yes, but at coordinates re-derived by a second parser |
| Bundle / SSR | No dependency, no worker, no SSR shim | Worker setup, large bundle, SSR care needed |
| Maintainability | Two small components | A rendering stack to keep current |
| Security | No third-party PDF execution in our bundle | Configurable, but ours to get right |

The decisive argument is not bundle size. It is that PDF.js would give
the Workspace a **second source of geometry** — its own layout of the
document — while the backend's canonical representation already records
where the parser saw each span. Highlighting against PDF.js coordinates
would mean an observation's provenance and its highlight came from two
different parsers, and no test could tell you when they disagreed.

Recorded as [ADR-0021](adr/0021-engineering-workspace-document-viewer.md).

### Non-PDF formats

Not interpreted. A DWG, DXF, XLSX or unclassified document shows a stated
fallback and a download link. Nothing is handed to the browser to guess
at, which is what keeps a file that claims one format and contains HTML
from being rendered as HTML.

## 7. Source location model

`lib/workspace/source-location.ts` defines one contract, and every field
in it is a transcription:

```ts
SourceLocation {
  document_id
  page_number          // provenance.page_number, 1-based
  paragraph_index      // provenance.paragraph_index - one PDF block
  line_index           // provenance.line_index
  section_index        | null   // one page
  block_reading_order  | null
  token_start / end    | null
  spans                []       // span_reading_order + character range
  excerpt              | null   // provenance.source_text, verbatim
}
```

**There is no `bounding_box` field, on purpose.** Evidence carries no
geometry. Rectangles are resolved separately, by joining the location's
`(page_number, block_reading_order, span_reading_order)` against the
canonical page — and when that join finds nothing, the result is *no
highlight*, never an approximate one. An architecture test asserts the
field's absence, because a field with nothing true to put in it
eventually gets something plausible put there.

### Known limits

| Artefact | Location available | Consequence |
|---|---|---|
| Evidence | page, paragraph, line, tokens, spans, excerpt | Full highlight |
| Entity / fact support | page, paragraph, line, tokens | Page navigation; highlights come via the referenced evidence |
| Fact diagnostic | page, paragraph, line | Navigable to the line; nothing to highlight |
| Semantic diagnostic | none | Navigable through the subject entity only |

A semantic diagnostic names a *subject*, not a line — which line carried
the meaning is precisely what the rules could not decide. The Workspace
reports that rather than picking one.

## 8. State vocabulary

Six states, kept apart everywhere. Each is carried by colour, by a glyph
and by a word, so none depends on colour alone.

| State | Means |
|---|---|
| `interpreted` ◆ | A versioned rule produced this. **Not** approved by anyone. |
| `ambiguous` ◇ | The artefact exists and inherits a declared upstream ambiguity. |
| `declined` ⊘ | A rule was evaluated and deliberately produced nothing. |
| `empty` ○ | The stage ran and produced a valid set of zero artefacts. |
| `unrun` · | The stage has produced nothing yet (the read was a 404). |
| `failed` ✕ | The read or the execution failed; what exists is unknown. |
| `reused` ↺ | Nothing was created; an existing artefact was returned. |

The four the pipeline most easily blurs:

> **Unrun ≠ empty. Empty ≠ failed. Ambiguous ≠ rejected. Diagnostic ≠
> semantic statement.**

**`interpreted` is not green.** Green reads as approval, and nothing in
this milestone has been approved. It is rendered in a neutral blue, and
the UI copy says in as many words that "interpretato" means produced by a
rule, not verified by an engineer.

## 9. Diagnostics

Diagnostics are content, not a warning banner. A declined construction is
the rules working: candidates existed, a rule was evaluated, and it chose
not to guess.

They are shown in their own explorer, selectable, and navigable to the
artefacts they name. They are addressed by a key the Workspace derives
from governed fields (`fact:<reason>:<page>:<paragraph>:<line>`,
`semantic:<reason>:<subject_entity_key>`) purely so a selection can live
in the URL. That address is never sent to the backend and carries no
claim the backend would recognise.

A subject with no interpreted meaning appears in **Diagnostiche** and
nowhere else. It never appears in the statements list.

## 10. Partial availability

The five reads are settled independently (`Promise.allSettled`), and each
stage carries its own status. A semantic endpoint returning 500 shows a
failure on the *Significato* tab and leaves Evidence, Entities and Facts
fully inspectable. This is the difference between `useWorkspace` and
`usePipeline`: the pipeline view asks one question about the whole
pipeline, and an all-or-nothing read is honest there.

## 11. Performance

- Four artefact reads per document, once. Selection changes re-read
  nothing.
- Canonical pages are read lazily, one per displayed page, and
  superseded reads are aborted by `useResource`.
- Indexes are memoised on the snapshot; every traversal is a `Map`
  lookup.
- Explorer lists render 60 rows and offer "Mostra altri". No
  virtualization: it would cost a dependency and a scroll implementation
  to save a paint that a bound already saves, and every row stays a real
  focusable element.
- The document binary is never fetched into JSON, never base64-encoded,
  and requested only when the *Originale* tab is open.

## 12. Security assumptions

- Every read goes through `lib/api/client.ts`. An architecture test
  fails on any `fetch`, `XMLHttpRequest` or `axios` in Workspace code.
- No file path or storage reference appears in Workspace code, in a
  request, or in rendered output. Tests assert all three.
- The content URL is composed from the API base and the **document id**
  only.
- Selection query parameters are validated against a closed vocabulary
  before use, and a selection resolves by lookup in an already-loaded
  index — no value in the URL can reach an endpoint.
- Excerpts and filenames are rendered as React text nodes.
  `dangerouslySetInnerHTML` appears nowhere.
- Non-PDF formats are never handed to the browser to interpret.

**Known limit, stated rather than papered over:** the *Originale* tab
hands the PDF to the browser's built-in viewer, which is where any
JavaScript embedded in the PDF would be handled. That execution happens
inside the browser's own PDF sandbox and is **not** additionally disabled
by SubstationOS. The canonical map — the surface the Workspace actually
depends on for traceability — executes nothing from the document at all.

**Access control is out of scope for this EPIC.** There is no
authentication and no authorisation: any caller who can reach the API can
read any document. That is a deliberate deferral, not an oversight, and
it must be resolved before any deployment outside a trusted network.

## 13. Review: what the Workspace now writes, and what it still does not

EPIC 30.2 shipped this screen as inspection-only, and said why: an
approval is not a UI control but a governed domain concept, needing an
actor, a timestamp, a reason, an audit trail and a rule for what a
pipeline re-run does to it. A button recording a judgement into nothing
would have been worse than no button.

**EPIC 30.4 built that context**, and the Workspace gained exactly one
action.

Selecting a semantic statement now shows a **review panel** beneath its
support chain: the current decision, who passed it and when, the reason,
the rule version it was passed under, the full history, and a control to
record a judgement. It is a dedicated region — the rest of the screen
stays read-first.

The statement list carries **two badges per row**, and they say different
things:

- the pipeline badge (`interpreted` / `ambiguous`) — what the rules
  produced;
- the review badge (`Approvato` / `Respinto` / `Da approfondire` / `Mai
  revisionato`) — what an engineer decided.

Collapsing them into one would be the confusion between engineering truth
and engineering judgement that both milestones exist to prevent.

### What is still absent, and structurally so

The Workspace **still cannot change what the pipeline said**. There is no
correct-value, no edit-entity, no merge, no author-a-fact and no
annotate. A review references an immutable artefact by key and is
appended to a separate context; the statement, its facts, its entities
and its evidence are untouched by it, and an API test asserts the
semantic set compares equal before and after.

`Mai revisionato` is a **state, not a decision** — nobody has judged the
statement, which is neither an approval nor a rejection — and
`interpreted` still means *produced by a versioned rule*, never
*approved*. Both are asserted by tests.

See [human_review.md](human_review.md) and
[ADR-0023](adr/0023-human-review-append-only-judgement.md).

---

## Files

| Concern | Location |
|---|---|
| Route | `apps/frontend/app/documents/[documentId]/workspace/page.tsx` |
| Read model & indexes | `apps/frontend/lib/workspace/model.ts` |
| Source locations & geometry | `apps/frontend/lib/workspace/source-location.ts` |
| Selection vocabulary | `apps/frontend/lib/workspace/selection.ts` |
| State & predicate copy | `apps/frontend/lib/workspace/presentation.ts` |
| Components | `apps/frontend/components/workspace/` |
| Hooks | `apps/frontend/hooks/useWorkspace*.ts`, `useCanonicalPage.ts` |
| Page endpoint | `apps/backend/app/routers/canonical_pdf.py` |
| Review panel | `apps/frontend/components/workspace/Review*.tsx` |
| Tests | `apps/frontend/tests/workspace*.test.ts(x)`, `apps/frontend/tests/review.test.tsx`, `apps/backend/tests/api/test_canonical_pdf_api.py` |
