# Public API Contract

**Status:** As-built reference for the hardened Project and Document APIs
(Milestone 30.1.3). For the client that consumes them, see
[frontend_architecture.md](frontend_architecture.md); for the pipeline
endpoints, see
[knowledge_pipeline_overview.md](knowledge_pipeline_overview.md).

## Authentication (EPIC 30.3)

**Every endpoint requires a session unless it is on the public list.**
That is enforced by middleware rather than per-route dependencies, so a
router added later is protected by default, and
`tests/api/test_api_security.py` walks every path in the live OpenAPI
document asserting it.

```
POST /auth/login    → Set-Cookie: substationos_session (HttpOnly)
                      Set-Cookie: substationos_csrf    (readable)
POST /auth/logout   → 204, always
GET  /auth/session  → who am I, or 401
```

| Status | Meaning |
|---|---|
| `401` | No live session. One message for every cause - no token, unknown, revoked, expired, idle - deliberately, so the API cannot be used to test whether a found token is real. |
| `403` | Authenticated and not permitted, **or** an unsafe request without a valid `X-CSRF-Token`. Never a reason to re-authenticate. |

Public routes, each a deliberate choice: `/`, `/health`, `/auth/login`,
`/auth/logout`, `/auth/session`, `/openapi.json`, `/docs`, `/redoc`. See
[security_architecture.md](security_architecture.md) §7 for why each.

**No response schema anywhere can carry a password, a credential or a
session token** - two OpenAPI tests assert it, one walking every schema
reachable from a response, the other asserting the three request models
that accept a password are unreachable from any response.

`POST /projects/` no longer accepts `created_by`. It used to, which meant
the record of who created a project was whatever the caller typed; it now
comes from the authenticated identity, along with `owner_user_id`.

## Removed endpoints (EPIC 31.1)

Three routes were **removed**, not deprecated:

```
GET /projects/{project_id}/knowledge-graph        removed
GET /projects/{project_id}/entities               removed
GET /projects/{project_id}/entities/{entity_id}   removed
```

They served the legacy Knowledge Graph - LLM-extracted entities written
straight from upload with no review gate. They had carried
`deprecated: true` since Architecture Freeze v1.0, which changed nothing:
a deprecated endpoint serving ungoverned data still serves ungoverned
data. A `410 Gone` shim was considered and rejected, because it preserves
a URL whose only honest answer is that the data should never have been
queryable.

**The governed replacements** are `GET /knowledge-graph/nodes`,
`/knowledge-graph/edges` and `/knowledge-graph/nodes/{node_id}` (EPIC
31), which return only knowledge an engineer approved and carry the
provenance to prove it.

One response field survives its cause: `analysis.entities_found` on
`POST /documents/upload` is now **always `0`**, because an upload no
longer writes any graph. It is kept at zero rather than removed, which
would be a breaking response change this milestone did not need to make.

See [ADR-0025](adr/0025-retire-the-legacy-knowledge-graph.md).

## The rule

**Every public endpoint exposes a governed application schema.** Never an
ORM model, never a filesystem detail, never an ad-hoc dictionary.

Before this milestone `GET /documents/` declared no `response_model` at
all, so its rows were whatever FastAPI could serialise off a `Document`
row — including `file_path`. That is the class of defect this document
exists to prevent.

### Storage location is private backend state

Where a document's bytes live never leaves the backend. Not as
`file_path`, not as `storage_reference`, not in an error message, not in
an example.

The guarantee is structural, not a convention:

- no value object in `app/domain/document_registry` has a storage field,
  so no schema built from one can carry it;
- `DocumentDownload` is the single exception — the transport must hand
  the reference back to the content port — and an architecture test
  asserts it is the only carrier;
- a test walks **every** schema in the OpenAPI document looking for a
  property whose name contains `path` or `storage`.

That last test found a real leak this milestone: `DocumentContentIdentityRead`,
on the ingestion API, was publishing `storage_reference`. It is gone.

## Public document schemas

| Schema | Used by | Contains |
|---|---|---|
| `DocumentSummaryRead` | list responses | id, project id **and name**, filename, format, category, revision, scope, uploaded_at |
| `DocumentDetailRead` | `GET /documents/{id}`, upload | the above **plus** content checksum, algorithm, size, `content_available`, ingestion state and outcome |
| `DocumentListResponse` | `GET /documents/` | `items` + `pagination` |
| `DocumentUploadResponse` | `POST /documents/upload` | `document`, `scope`, `analysis`, `warnings` |

### Fields deliberately excluded, and why

| Field | Why it is not public |
|---|---|
| `file_path` | A storage location. Private backend state, always. |
| `content_storage_reference` | The same thing under the ingestion record's name. |
| `project` relationship | An ORM relationship; the caller asked for a document. |

`project_name` **is** on the summary, and it is the one field that looks
like a detail and is not: a registry table spanning several projects has
to say which project each row belongs to, and a numeric id tells a human
nothing. It is denormalised onto the document row already, so it costs no
join.

`content_checksum` is public **on purpose**. The deterministic pipeline
binds every artefact to it, so an engineer comparing a canonical
representation against its document needs to see it. It identifies *the
bytes*, never *where they are*.

## `GET /documents/{document_id}`

Returns `DocumentDetailRead`. `404` when no such document exists.

`content_available` is resolved through the content port at read time. It
is the honest answer to "can I download this?", and it is `false` for a
document whose bytes have gone missing under a registry row that remains.

`content_checksum`, `checksum_algorithm` and `size_bytes` come from the
document's own ingestion record and are `null` for a document that has
never been ingested — an un-run identity is not a zero.

## `GET /documents/{document_id}/content`

The governed download.

**Route naming.** `/content`, not `/download`. Every other per-document
route in this API is a noun naming the artefact it serves —
`/canonical-representation`, `/canonical-text`, `/engineering-evidence`.
`content` is the noun for the original bytes, and it is the name of the
port that serves them. `/download` is a verb and would be the only one.

### Why traversal is unreachable rather than blocked

```
document id (integer)
  → registry            which document is this?
  → storage location    what opaque reference was recorded for it?
  → content port        what is at this reference?
  → bytes
```

**No step accepts a path from the caller.** The only input is an integer;
the reference is whatever the registry recorded. There is no parameter
through which a traversal could be expressed, which is a stronger
guarantee than sanitising one.

### Headers

- `Content-Type` from a **closed table** keyed by stored format. An
  unclassified document is served as `application/octet-stream`: telling
  a browser a file is a PDF when nobody established that is a worse answer
  than telling it nothing.
- `Content-Disposition: attachment; filename="…"`. Always `attachment` —
  a document of unverified provenance must not be rendered by the browser
  in this application's origin.
- The filename is sanitised by an **allow-list** (`[A-Za-z0-9._-]`), so
  separators, `..`, quotes, newlines and control characters cannot
  survive. Both path traversal and header injection live in that string.

### Streaming

Served in 64 KiB chunks through `DocumentContentPort.iter_chunks`, so a
200 MB drawing is never held in memory.

Every failure is resolved **before** the first byte is written: once a
stream has begun the status code is already sent, and a failure could no
longer be reported as one.

### Statuses

| Status | Meaning |
|---|---|
| `404` | No such document, **or** its stored content no longer exists — the message names which |
| `500` | The content exists and could not be read |

"It is not there" and "it is there and I cannot read it" are different
facts with different remedies, and the API keeps them apart.

## `GET /documents/{document_id}/canonical-representation/pages/{page_number}`

Added by EPIC 30.2 for the Engineering Workspace, whose page map renders
one page at a time.

A **strict projection** of the stored canonical representation: the same
blocks, spans, bounding boxes and styles the full read returns for that
page, selected rather than recomputed. It parses nothing, derives no
coordinate, and creates no engineering knowledge. An API test asserts the
response is identical to the corresponding page of the full read, page by
page.

It exists for one reason: the full representation of a 200-page drawing
set carries every span of every page, and a viewer showing page 7 needs
page 7.

### Statuses

| Status | Meaning |
|---|---|
| `200` | The page, as the representation records it |
| `404` | No such document, **or** it was never canonicalised, **or** the representation records no such page |

`page_number` is 1-based, as the representation records it and as an
engineer reads it.

**Page numbers are not identities.** Asking document B for a page that
only document A was canonicalised into is a `404`, not A's page — a test
asserts it. No storage location appears in the response; a test asserts
that too.

## `POST /documents/upload`

Returns `DocumentUploadResponse`, replacing the bare `dict` that OpenAPI
could not describe.

```json
{
  "document":  { … DocumentDetailRead … },
  "scope":     "project",
  "analysis":  { "status": "completed", "entities_found": 4, "failure": null },
  "warnings":  []
}
```

**There is no `reused` field.** Upload does not deduplicate: Milestone
25.2 established that an identical checksum is recorded and nothing is
concluded from it, so a document is always newly registered.
`reused: false` on every response would imply a comparison that never
happens.

`analysis` keeps the status vocabulary the endpoint has always reported
(`completed` / `skipped` / `failed` / `no_text` / `unsupported_file_type`)
under a name that says what it is. A failure there **never** fails the
upload.

`warnings` are non-fatal and actionable: an unclassifiable format, a
filename that had to be sanitised for storage.

### Upload storage safety

The uploaded filename never becomes a path. Before this milestone it was
joined to the storage directory directly, so `../../app/main.py` was
written wherever that resolved, and two uploads with the same name
silently overwrote each other. Now:

- the stored name is derived by the same allow-list, plus a random suffix
  for uniqueness;
- the computed path is resolved and checked to be **inside** the storage
  root before anything is written — a security control enforced only by
  an earlier step is one refactor away from not being enforced;
- the **original** filename is still recorded and is what an engineer
  sees. Only the storage name is sanitised; conflating the two would
  rename people's documents.

## Pagination

One convention, every list endpoint: **`page` / `page_size`**.

| Parameter | Default | Bound |
|---|---|---|
| `page` | 1 | ≥ 1 (1-based) |
| `page_size` | 25 | 1 … **100** |

A page size above the maximum is **refused with 422, never clamped**: a
caller who asked for 10 000 and silently received 100 would believe it had
read the whole registry.

Every list response is:

```json
{
  "items": [ … ],
  "pagination": {
    "page": 1, "page_size": 25, "total": 137,
    "total_pages": 6, "has_next": true, "has_previous": false
  }
}
```

`total` is the whole result set, not the page length — a client cannot
tell whether it has seen everything without it. It is counted by the
database over the filtered set, never by measuring a list loaded first.

Both `ProjectListResponse` and `DocumentListResponse` are typed
separately and share only the `PageMetadata` value object: a generic
untyped envelope would leave OpenAPI unable to name what is inside.

## Filtering and search

Every filter is a **closed enum member or a typed value object**. There is
no field name, no operator, no expression, and no mapping from caller
input to a column. A column name never travels.

### Projects — `GET /projects/`

| Filter | Type |
|---|---|
| `status` | `ProjectStatus` (delivery phase) |
| `lifecycle_state` | `ProjectLifecycleState` (record state) |
| `include_deleted` | boolean, default `false` |
| `search` | free text over **name, code, customer, location** |

`status` and `lifecycle_state` are separate on purpose: a project can be
`energized` **and** `archived` — the substation is live and the file is
closed. Merging them would make that ordinary state unrepresentable.

`include_deleted` is a **visibility** decision, not a lifecycle filter.
Asking for `lifecycle_state=deleted` without it returns nothing rather
than silently overriding the default.

`description` is deliberately **not** searched: it is long prose, and
including it would make a search for "CP-01" match every project whose
description mentions one.

### Documents — `GET /documents/`

| Filter | Type |
|---|---|
| `project_id` | integer |
| `scope` | `DocumentScope` |
| `file_format` | `DocumentFormat` |
| `category` | `DocumentCategory` |
| `search` | free text over **filename, project name** |

### Matching rules — the same everywhere

- **case-insensitive**;
- **partial** — a substring, not a prefix and not a whole word;
- **trimmed** at both ends;
- internal whitespace **significant**: `"CP 01"` does not match `"CP01"`.
  Collapsing it would be a normalisation nobody asked for;
- an empty or whitespace-only term is the **absence** of a search, not a
  filter matching everything;
- `%` and `_` are escaped, so a search for `100%` means `100%` and not
  everything;
- filters combine as **AND**. There is no `OR`, no negation, no grouping.

## Sorting

Closed vocabularies. An unsupported field is refused with 422.

| Resource | Fields | Default |
|---|---|---|
| Projects | `created_at`, `updated_at`, `name`, `code` | `created_at desc` |
| Documents | `uploaded_at`, `filename`, `revision`, `document_format` | `uploaded_at desc` |

Direction is `asc` or `desc`. There is no third option.

**Every sort breaks ties by `id`.** Without it, paging over a non-unique
key (two projects created in the same second, six documents with the same
name) can show one row twice and skip another.

## Failures

| Status | Meaning |
|---|---|
| `404` | The resource does not exist, or its content does not |
| `409` | A domain conflict — duplicate code, invalid lifecycle transition, edit to a read-only project |
| `422` | The request itself is invalid — bad enum value, page size out of range, scope and project reference disagreeing |
| `500` | Persistence or infrastructure failure |

A registry read that fails for an infrastructure reason answers
`"The document registry could not be read."` and nothing more. The
driver's message, the table name and the connection string go to the log,
where they help, rather than into a response, where they only help an
attacker.

## Boundaries

```
router      →  application service  →  repository / port  →  database / storage
```

- Routers construct **no queries**, hold no column names, and (for
  `projects.py`) import no ORM module at all. Asserted on the AST.
- Pagination, filtering, search and sorting are the **adapter's** work.
  An adapter that loaded the table and sliced it in Python would satisfy
  the type and defeat the purpose; the count is a `SELECT COUNT`, and a
  test asserts routers contain no sequence slice.
- The `_SORT_COLUMNS` tables are keyed by **enum member**, never by
  string, and no adapter calls `getattr` to resolve a column.

## OpenAPI drift

The contract snapshot lives at `apps/backend/openapi.json` and is
committed on purpose: it is the version of the API the frontend was
written against, so a diff on it is exactly the review signal a breaking
change should produce.

```bash
python scripts/export_openapi.py
```

`apps/frontend/tests/contracts.test.ts` compares every frontend enum,
every filter parameter and the page-size bounds against it. A failure
there means the frontend is describing an API that no longer exists.

## Known gaps

- `POST /documents/upload` answers **200**, where every other create in
  this API answers 201. Changing it is a breaking change this milestone
  was not asked to make, and the response body was already changing.
- Other routers (`knowledge_graph`, `engineering_index`, …) still hold
  sessions and build queries directly. The architecture tests scope
  themselves to `documents.py` and `projects.py` and say so, rather than
  claiming a guarantee that does not hold.
- `project_intelligence` still counts documents with its own query rather
  than through the registry.
- No indexes were added. Search is `ILIKE '%term%'`, which cannot use a
  B-tree; at current registry sizes this is not measurable, and adding a
  speculative index would be guessing.
- **Authorisation is per-role, not per-project.** Any authenticated
  engineer can read any project and any document, including its original
  bytes; only user administration and the audit trail are restricted.
  Project membership is the next milestone. (Authentication itself
  arrived in EPIC 30.3.)
- **No rate limiting on `POST /auth/login`.** scrypt makes each attempt
  expensive, which slows a brute force without stopping one, and gives an
  unauthenticated caller a way to consume CPU.
- **Cookies are set without `Secure`** so the platform runs over plain
  HTTP in development. A TLS deployment must set it.
- The artefact endpoints (`/engineering-evidence`, `/engineering-entities`,
  `/engineering-facts`, `/engineering-semantics`) return a document's
  **whole** set, unpaged. The Engineering Workspace depends on that, and
  it is correct at realistic per-document artefact counts. If a document
  ever produces sets large enough to make it wrong, the answer is paging
  on these endpoints — not a second, parallel projection of the same
  relationships (ADR-0021).
