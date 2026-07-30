# Frontend Architecture

**Status:** As-built reference for the SubstationOS frontend after
EPIC 30.1.2 (Frontend–Backend Integration) and Milestone 30.1.3 (Public
API Hardening). For the contract it consumes, see
[public_api.md](public_api.md); for the pipeline it presents, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md); to run
it, see [developer_setup.md](../developer_setup.md).

> Replaces the empty `frontend_arcgitecture.md`, which was a
> zero-byte file with a misspelled name.

## The one rule

**The backend is the contract.** The frontend is a client of the public
API and knows nothing beneath it — no repository, no ORM, no database, no
filesystem path, no PDF parser, no canonical-representation internals, no
engineering algorithm. When the two disagree, the frontend is wrong.

Everything below follows from that.

## Layers

```
app/**            routes and pages          — composition only
components/**     presentation              — props in, markup out
hooks/**          state                     — useResource / useMutation
lib/resources/**  one module per router     — the only callers of the client
lib/api/**        the one HTTP client       — the only caller of fetch
lib/contracts/**  the backend's vocabulary  — transcribed, never invented
lib/validation/** form rules                — restatements of backend rules
```

Dependencies point one way, down the list. A component never calls a
resource module's transport; a resource module never formats a message
for a user; `lib/contracts` imports nothing at all.

## The API client

`lib/api/client.ts` is the **only** module in the application that calls
`fetch`. It owns:

| Concern | Behaviour |
|---|---|
| Base URL | `NEXT_PUBLIC_API_BASE_URL`, default `http://127.0.0.1:8000` |
| JSON | `json:` serialises and sets the header; `body:` passes `FormData` through untouched so the browser sets the multipart boundary |
| Query | `undefined` and `""` parameters are dropped, never sent empty |
| Timeout | 30 s default; `PIPELINE_TIMEOUT_MS` (120 s) for stages that parse a PDF |
| Cancellation | the caller's `AbortSignal` is composed with the timeout, and the two outcomes stay distinguishable |
| Retry | `GET`/`HEAD` only, transport faults only. **A `POST` is never replayed** — a repeated create is a second project |
| Errors | one typed class per failure mode |
| Raw reads | `raw: true` returns the `Response` for the one endpoint that serves bytes. Failures are still translated into the same typed errors: a raw read changes what a *success* looks like, never what a failure does |

### The error model

```
ApiError
├── ValidationError      422   — carries per-field violations
├── NotFoundError        404
├── ConflictError        409
├── RequestError         other 4xx
├── ServerError          5xx
├── NetworkError         no response at all
├── TimeoutError         no response in time
└── RequestCancelledError superseded or unmounted — not a failure
```

FastAPI answers 422 in **two** shapes and both arrive intact: Pydantic's
per-field array (bound onto form inputs by `fieldMessages`) and a plain
string raised by a domain rule (rendered as the sentence it is).

`describeError` produces the user-facing text. Its rule: **never invent a
cause.** When the backend explains itself — a duplicate project code, a
read-only project, an unsupported format — that explanation is what the
user reads. The copy in `messages.ts` covers only the cases where the
backend says nothing a person could act on. A cancelled request returns
`null`, because a superseded request is not something the user did wrong.

This is why the string "Si è verificato un errore" appears nowhere in the
application.

## State management

Two primitives, in `hooks/useResource.ts`:

- **`useResource`** — a read that can be refreshed. Exposes `data`,
  `loading` (first load), `refreshing` (subsequent), `error` (a sentence),
  `failure` (the typed cause), `reload` and `set`.
- **`useMutation`** — a write. Exposes `run`, `pending`, `error`,
  `failure`, `reset`. `run` **re-throws** so a caller can navigate on
  success and keep the form open on 422.

Both abort in-flight work on unmount and when their inputs change, so a
superseded response can never overwrite a newer one.

**Callers must pass stable functions** — `read` and `perform` wrapped in
`useCallback`, `copy` declared as a module constant. That requirement is
what keeps the dependency arrays honest and the hooks free of the
render-time ref writes React 19's compiler rejects.

The domain hooks (`useProjects`, `useProject`, `useDocuments`,
`useHealth`, `useProjectIntelligence`, `useKnowledgeGraph`,
`usePipeline`) are thin wrappers over those two. Before this EPIC each
one hand-rolled its own loading/error/reload triple — five times, five
definitions of "error", none of them cancelling anything.

### Cache invalidation

After a successful create or upload the list is corrected from **the
server's own copy** of the new resource, never from the submitted form.
Nothing is optimistically inserted before the backend confirms it: a
project row that exists on screen and not in the database is worse than
a half-second wait.

## The Pipeline UI

`/documents/{id}/pipeline` renders the deterministic pipeline stage by
stage:

```
Uploaded → Canonical Representation → Canonical Text →
Engineering Evidence → Engineering Entities → Engineering Facts →
Engineering Semantic Statements
```

`usePipeline` reads all seven stage endpoints in parallel and derives one
`StageView` each, carrying state, count, timestamp, reuse, ambiguities,
errors, the version triad the stage ran under, and which actions are
available.

Four properties this view exists to preserve:

- **A stage that has never run is `ready`, not failed.** Every stage read
  404s until it has run once; that is the normal state of a fresh
  document and rendering it as an error would be a lie.
- **A stage that ran and found nothing is `empty`, not failed.** The card
  says so in words: *"È una risposta valida delle regole, non un errore."*
- **A re-used artefact is reported as re-used.** The result body's
  `reused` flag is what the UI reads — never the status code.
- **Ambiguity is shown, not hidden.** A declined fact line or an
  uninterpreted subject is displayed with the reason, because a stage
  that constructed nothing has the most to explain.

### Timestamps

Most stages report *"Non esposto (artefatto deterministico)"* rather than
a date. That is deliberate and it is the backend's design, not a gap in
this UI: pipeline artefacts carry no timestamp precisely so that two runs
compare equal and determinism stays assertable. Only the upload and the
ingestion job have real timestamps, and only those are shown.

### Quantities

`value` and `base_value` arrive as **strings** — the backend serialises
`Decimal` to JSON strings so a rated voltage cannot pick up a rounding
error. They are rendered as strings and never parsed into a JS number. A
test asserts `20.500 kV` survives as `20.500 kV`.

## The Engineering Workspace

`/documents/{id}/workspace` is a **separate route with a different
question**, and the separation is deliberate:

| | Pipeline (`/pipeline`) | Workspace (`/workspace`) |
|---|---|---|
| Question | Did the pipeline run? | What does the platform claim, and why? |
| Content | Stage state, counts, versions, re-use | Artefacts, support chains, source locations, diagnostics |
| Actions | **Run** a stage | **Inspect** only — no writes at all |

Three regions: the source document, the engineering artefacts, and the
selected artefact's identity and support chain. Selecting anywhere moves
the other two, and every move follows a reference the backend wrote down
(`entity.evidence[].evidence_key`, `fact.subject_entity_key`,
`statement.supporting_fact_keys`).

Four properties specific to this view:

- **The support chain is composed client-side, from four reads.** Each
  artefact endpoint returns its document's whole set with support
  references inline, so a traversal is a `Map` lookup rather than a
  request. No support-chain endpoint exists, and one was rejected rather
  than forgotten — see ADR-0021.
- **Stages settle independently.** `useWorkspace` uses
  `Promise.allSettled`, so a semantic endpoint that fails leaves Evidence
  inspectable. This is where it differs from `usePipeline`, which asks one
  question about the pipeline as a whole.
- **Highlights are drawn on the canonical representation, never on the
  PDF.** A span's rectangle comes from the parser that recorded the
  provenance citing it, joined by
  `(page_number, block_reading_order, span_reading_order)`. When that
  join finds nothing, there is no highlight — never an approximate one.
- **`interpreted` is not `approved`, and is not green.** A versioned rule
  produced the statement; no engineer has confirmed it, and this
  milestone has no way for one to.

`lib/workspace/` holds the read model: normalised indexes, the
`SourceLocation` contract, the closed selection vocabulary, and the
state/predicate copy. `tests/workspace-architecture.test.ts` asserts
structurally that no fuzzy match, no engineering rule, no direct `fetch`
and no write exists in any of it.

Full detail: [engineering_workspace.md](engineering_workspace.md).

## Lists are paged, filtered and sorted by the server

Since Milestone 30.1.3 the backend owns paging, filtering, search and
sorting, and the frontend's job is to **send the query and render the
page it gets back**.

```ts
const { query, setFilter, setPage } = useDocumentQuery();
const { documents, pagination, ... } = useDocuments(query);
```

Three consequences, each asserted by test:

- **Nothing filters the returned page.** The result is one page;
  filtering it would hide matches on every other. The client-side
  `useMemo` filters this application used to have are gone.
- **Filter options come from the contract's enums**, not from the values
  present on the current page. Deriving them from the page was correct
  only while the client held the whole registry.
- **Changing a filter resets to page 1.** Staying on page 4 of the
  previous result set shows an empty page and reads as "no matches".

Search is debounced 300 ms — typing should not fire a request per
keystroke.

After a create or an upload the page is **re-read** rather than spliced:
where a new row lands depends on the active sort and filters, which only
the server knows.

`Pagination` is the one control, and it reports the **total** — without
it a user cannot tell whether they have seen everything, which is the
same reason the API returns it.

## Document detail and download

`useDocument(id)` reads `GET /documents/{id}`. Before Milestone 30.1.3
this page had to find its document inside the whole list, because no
per-document read existed.

Its `download()` fetches `GET /documents/{id}/content` through the same
client, hands the blob to the browser, and uses the filename from the
response's `Content-Disposition` — which the backend already sanitised.
**The frontend never constructs a storage URL and never sees a path.**
The button is disabled when `content_available` is `false`, which is the
backend's honest answer for a document whose bytes have gone missing.

## Type synchronisation

`lib/contracts` is a hand-written transcription of the backend's schemas,
one file per bounded context, each naming its source module. It is the
**only** place an API enum, request body or response body is declared.
No component writes `"planning" | "active"` inline.

`tests/contracts.test.ts` compares every enum against the backend's own
OpenAPI document, exported by `scripts/export_openapi.py` to
`apps/backend/openapi.json` — a **committed contract snapshot**, so a
diff on it is the signal a reviewer wants when a backend enum changes.

That test is what turns "the types match" from a claim into an assertion.
It is also how this EPIC found `ProjectStatus` shipping `active`,
`on_hold`, `completed` and `cancelled` — four values the backend has
never accepted.

## Validation

`lib/validation/project.ts` restates backend rules and **only** backend
rules; its limits come from `PROJECT_FIELD_LIMITS`, transcribed from the
Pydantic schema. Its purpose is to fail fast, not to be authoritative:
the backend's 422 is still bound field by field when the two disagree, and
the backend wins visibly.

Select options are generated from the contract's enums, so a value the
API would reject cannot be offered.

## Testing

`vitest` + `@testing-library/react` + `jsdom`. `tests/_backend.ts`
stubs the API with the **exact** status codes and bodies the routers
return; an undeclared request fails the test rather than resolving to
nothing. 91 tests across six files:

| File | Covers |
|---|---|
| `api-client.test.ts` | base URL, query, JSON/multipart, 422 (both shapes), 404, 409, 500, network, timeout, cancellation, retry policy |
| `contracts.test.ts` | every enum against the backend's OpenAPI document |
| `projects.test.tsx` | create, list, validation, 422/409/500, empty and error states |
| `documents.test.tsx` | list, upload multipart, scope refusals, read-only projects |
| `pipeline.test.tsx` | stage states, running, reuse, ambiguity, artefact inspection |
| `state.test.tsx` | cancellation, stale-response protection, refresh vs load, mutation outcomes |

## What is deliberately absent

- **No mock data.** `lib/demo-commissioning.ts` (905 lines),
  `lib/demo-timeline.ts` and the components that consumed them are
  deleted. Commissioning and relay testing have no backend, so the UI
  does not pretend they do.
- **No placeholder counters.** The dashboard's hardcoded `0` projects,
  `0` commissioning activities, "AI Assistant: Offline" tile and
  "+12% questo mese" trend are gone. Every figure on screen is read from
  an endpoint.
- **No commissioning or relay-testing metrics.**
  `GET /projects/{id}/intelligence` returns constant zeros for
  `commissioning`, `relay_testing` and `issues` — the backend's own
  placeholders. They are in the contract and typed, but not rendered: a
  fabricated 0% beside a real documentation figure reads as a
  measurement, and it is not one.
- **No dead navigation.** `/commissioning`, `/relay-testing`, `/ai`,
  `/reports` and `/settings` were sidebar links to routes that do not
  exist.
- **No document download or detail view.** The backend exposes neither
  endpoint. Building one client-side would be a second, quietly diverging
  contract.
- **No human review in the Workspace.** No approve, reject, correct,
  edit, merge, override or annotate, and no button implying one. An
  approval needs an actor, a timestamp, a scope, a reason and an audit
  trail — a governed Human Review bounded context, not a control. A
  button that recorded a judgement into nothing would be worse than none.
- **No PDF rendering library.** PDF.js and `react-pdf` were both
  evaluated and rejected: either would give the Workspace a second source
  of page geometry alongside the canonical representation. See ADR-0021.

## Gaps that Milestone 30.1.3 closed

Every item the EPIC 30.1.2 audit recorded as a backend gap has been
fixed, and the frontend consumes the result:

| Was | Now |
|---|---|
| `GET /documents/` returned ORM rows including `file_path` | `DocumentListResponse`, and no storage field exists to leak |
| No `GET /documents/{id}` | `useDocument(id)` reads it |
| No download endpoint | `GET /documents/{id}/content`, governed and streamed |
| `POST /documents/upload` returned a bare `dict` | `DocumentUploadResponse`, described in OpenAPI |
| No pagination | `page` / `page_size`, max 100 |
| No server-side search or filtering | Both, over documented closed vocabularies |

See [public_api.md](public_api.md) for the contract.

## Remaining gaps

- `POST /documents/upload` answers **200** rather than 201, unlike every
  other create in this API. A deliberate non-change: the response body
  was already changing and the status was not in this milestone's scope.
- There is no page-size selector in the UI; the default of 25 is used
  everywhere except the two places that need a whole small list (the
  upload target picker and a project's own documents), which ask for 100.
- No E2E test against a live backend — the 205 tests stub HTTP.
- **No authentication or authorisation anywhere.** Any caller who can
  reach the API can read any document, and the Workspace inherits that.
  A deliberate deferral, and one that must be resolved before any
  deployment outside a trusted network.
- The Workspace's canonical page map renders extracted text at its
  recorded coordinates; it shows no images and no vector geometry, so a
  purely graphical drawing looks sparse there. The original document is
  one tab away, and the pipeline has nothing to say about content it did
  not extract either.
