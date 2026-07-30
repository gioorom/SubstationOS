# ADR-0021: Engineering Workspace document viewer and support-chain strategy

## Status

Accepted.

## Context

EPIC 30.2 introduces the Engineering Workspace: a document-centric
environment where an engineer validates the platform's engineering claims
against the source document. Two decisions in it are hard to reverse and
therefore recorded here.

**First**, how the source document is displayed. The Workspace must
navigate to a page, highlight the exact place an observation was read
from, and remain compatible with the existing Next.js architecture. The
candidates were the browser's built-in PDF viewer, PDF.js directly, and
`react-pdf`.

**Second**, how the support chain is loaded. The chain runs
`statement → facts → entities → evidence → source location`, and a naive
client would issue one request per link, producing an uncontrolled
fan-out.

## Decision

### 1. Two source views, and highlights only on the canonical one

The Workspace shows the source document two ways:

- **Mappa canonica** — an SVG rendering of the canonical representation.
  Each span is drawn at the `bounding_box` the parser recorded, inside a
  `viewBox` of the page's own `width`/`height`. Highlights are drawn
  here.
- **Originale** — the document's own bytes from
  `GET /documents/{id}/content`, handed to the browser's built-in viewer
  in an `<iframe>`, positioned with the `#page=N` open parameter. Not
  annotated.

**No PDF rendering library is added.**

The decisive argument is not bundle size, SSR, or maintenance, though all
three favour this choice. It is that PDF.js would introduce a **second
source of geometry**. The backend's canonical representation already
records where its parser saw every span, and evidence provenance cites
those spans by `(page_number, block_reading_order, span_reading_order)`.
Highlighting against coordinates re-derived by a different parser would
mean an observation's provenance and its highlight came from two
independent layout engines, with no test able to detect the day they
disagreed. Drawing on the canonical representation makes the highlight
and the provenance the same artefact by construction.

The trade-off is accepted openly: the canonical map is a *map of what was
extracted*, not a facsimile. It shows no images, no vector geometry and
no lines of a wiring diagram. The original bytes remain authoritative and
are one click away, and the UI says which is which.

### 2. Non-PDF formats are not interpreted

DWG, DXF, XLSX and unclassified documents show a stated fallback and a
download link. Nothing is handed to the browser to guess at.

### 3. The support chain is composed client-side; no projection endpoint is added

The four artefact endpoints already return their document's whole set,
with every support reference inline. The complete chain for every
statement in a document therefore costs four requests, once, and every
traversal afterwards is a `Map` lookup over a normalised index.

A `support-chain` projection endpoint was considered and rejected: with
no fan-out to eliminate, it would only duplicate data the client already
holds, and create a second place in which a support relationship is
described. Two descriptions of the same relationship is exactly the
condition under which they diverge.

### 4. One page-scoped read endpoint is added

```
GET /documents/{document_id}/canonical-representation/pages/{page_number}
```

Read-only, and a strict selection from the stored representation. It
exists so the page map can read the page it displays rather than every
page of the document. An API test asserts that its response is byte-for-
byte the corresponding page of the full read.

## Consequences

**Positive**

- No new frontend dependency, no PDF worker, no SSR shim.
- Highlight coordinates and evidence provenance are the same governed
  artefact; a drift between them is not representable.
- Support traversal is instantaneous and offline once the four sets are
  loaded, and needs no new backend surface.
- The distinction between "the document" and "what we extracted from it"
  becomes visible to the engineer instead of being an implementation
  detail — which is itself part of the product's trust story.

**Negative**

- The canonical map does not render images or vector graphics, so a
  purely graphical drawing shows little there. Mitigated by the original
  view, and by the fact that the pipeline has nothing to say about
  content it did not extract either.
- The original view cannot carry highlights.
- Paging within the original view re-requests the document from the
  browser's cache. Accepted: it is the browser's own viewer, and the
  canonical map is the traceability surface.
- Composition assumes a document's artefact sets are reasonably sized.
  If that stops holding, the answer is server-side paging on the existing
  endpoints, not a parallel projection.

**Neutral**

- Embedded JavaScript in a PDF is handled by the browser's own sandboxed
  viewer in the *Originale* tab and is not additionally disabled by
  SubstationOS. Documented in `engineering_workspace.md` §12.

## Rejected Alternatives

**PDF.js or `react-pdf` for the source viewer.** Rejected because either
would introduce a second source of page geometry alongside the canonical
representation the provenance already cites. Highlight coordinates and
evidence provenance would come from two independent layout engines, and
no test could detect the day they disagreed. Bundle size, worker setup
and SSR were secondary considerations pointing the same way.

**A dedicated `support-chain` projection endpoint.** Rejected because the
four artefact endpoints already return each document's whole set with
support references inline, so there is no request fan-out to eliminate.
It would only duplicate data the client holds and create a second place
in which a support relationship is described — which is the condition
under which two descriptions diverge.

**Bounded batch-read endpoints.** Rejected for the same reason, with the
added cost of a batching protocol nobody needs at current artefact
counts.

**Reading the whole canonical representation client-side instead of
adding a page endpoint.** Rejected because it transfers every span of
every page of a drawing set to render one page. The page-scoped read is a
strict projection and an API test asserts it returns exactly what the
full read holds for that page.

**Drawing approximate highlights when a span cannot be resolved.**
Rejected outright. A plausible rectangle in the wrong place on a wiring
diagram is worse than no rectangle, because the engineer cannot tell the
difference.

## Related

- `docs/architecture/engineering_workspace.md`
- ADR-0006 (AI as interpretation/presentation layer) — the same
  principle applied to a different layer: presentation may describe what
  the domain produced, never add to it.
