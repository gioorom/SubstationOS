# Security Architecture (EPIC 30.3)

> **Status:** identity, authentication, authorization and audit
> foundations. No engineering review workflows, no collaboration, no
> permissions inside the pipeline.

---

## 1. Three questions, kept apart

| Question | Answered by | Lives in |
|---|---|---|
| **Who is making this request?** | Authentication | `services/authentication_service.py` |
| **May this identity do this?** | Authorization | `domain/identity/identity_roles.py`, enforced at the API boundary |
| **Who did this, under which proof of identity?** | Audit identity | `domain/identity/audit_identity.py` |

They are three concerns and are never merged. An architecture test
asserts the authentication service makes no authorization decision, and
another asserts the authorization rule is a pure function of a role and a
capability, with no request, session or database in sight.

```
User → Authentication → Identity → Authorization → Application services → Engineering domain
```

**The engineering domain is unaware of all of it.** An architecture test
walks every module of `canonical_pdf`, `canonical_text`,
`engineering_evidence`, `engineering_entities`, `engineering_facts`,
`engineering_semantics` and `ontology`, and fails if any of them imports
the identity or audit context. A second test walks their ORM models and
fails on a `user_id`, `actor`, `created_by` or `owner` column.

## 2. Why: audit identity attaches to actions, never to artefacts

This is the load-bearing rule of the milestone.

An `EngineeringEntity`, an `EngineeringFact` and a `SemanticStatement`
are functions of a document's bytes and the versioned rules that read
them. If any of them carried a user, then:

- running the pipeline twice under two logins would produce two different
  artefacts;
- idempotency and artefact re-use would break;
- "why does the system believe this?" would acquire an answer involving a
  person.

So identity is recorded on the **event**: `pipeline_executed` by whom, at
what time, against which document, with what outcome. An API test runs
the same stage over the same document as two different engineers and
asserts the artefacts compare equal.

## 3. Authentication mechanism

**Opaque server-side sessions, delivered in an `HttpOnly` cookie.**
Recorded as [ADR-0022](adr/0022-session-authentication-and-password-hashing.md).

```
POST /auth/login   { email, password }  →  Set-Cookie: substationos_session=…  (HttpOnly)
                                           Set-Cookie: substationos_csrf=…     (readable)
```

Why not JWT: a stateless token cannot be revoked. Logout would be a
client-side gesture, disabling an account would not end its sessions
until they expired on their own, and "list and revoke my sessions" would
be unimplementable. Every one of those is a requirement of this EPIC.

Why a cookie rather than a bearer token in a header: a bearer token has
to live somewhere script can read it, which makes an XSS flaw an account
takeover that outlives the page. `HttpOnly` means the credential is not
reachable from JavaScript at all. The cost is CSRF, which is a solved
problem and is solved below.

**Future fit.** SSO produces a session at the end of a redirect flow -
the same `AuthenticationSession`, opened by a different proof. MFA gates
session *creation* without changing anything downstream. Neither requires
the session model to change, which is the point of choosing it.

### The token

- 256 bits from `secrets.token_urlsafe`, via a `SecureTokenGenerator`
  port so randomness stays at the edge.
- Stored as a **SHA-256 fingerprint**, never as the token. A copy of the
  database is therefore not a set of live logins.
- A plain hash is correct here and a slow KDF would not be: a session
  token is high-entropy random, so there is nothing to guess; making
  every authenticated request pay for a memory-hard derivation would buy
  nothing.

## 4. Passwords

**scrypt (RFC 7914), from `hashlib`.** Salted per credential, memory-hard,
and on OWASP's list of acceptable password hashes.

Stored self-describing:

```
scrypt$n=32768,r=8,p=1$<salt>$<digest>
```

Recording the parameters is what makes raising the cost — or moving to
Argon2id — a policy change plus a re-hash on next login, rather than a
schema migration and a forced reset for every user. `needs_rehash`
compares a stored credential against current policy, and
`authentication_service` re-derives a stale one at the single moment the
plaintext password is legitimately in memory: a successful login.

**Argon2id is the better choice and is not used yet.** It means a
compiled dependency (`argon2-cffi`) in a repository that currently has
**no dependency manifest at all** — see §12. Adding a binary dependency
that nothing records is a worse position than a standard-library KDF that
is genuinely adequate, and the upgrade path is built rather than
promised.

**Policy:** minimum 12 characters, maximum 1024 (a cost bound, not a
strength rule — an unbounded input would make an unauthenticated request
perform unbounded work). No composition rules, following NIST SP 800-63B:
`P@ssw0rd!` satisfies every classic rule and is worthless.

Password **reset** is architecturally prepared and deliberately not
built: `change_password` exists and requires the current password; a
reset requires a mail channel, a single-use token and an expiry, which is
its own milestone.

## 5. Session lifecycle

```
login → ACTIVE ──idle 2h──────→ IDLE_EXPIRED
              ├─absolute 12h──→ EXPIRED
              └─logout / disable → REVOKED
```

Two independent clocks, and a session must satisfy both:

| Clock | Default | Bounds |
|---|---|---|
| **Idle** — since last use | 2 hours | An unattended logged-in workstation |
| **Absolute** — since issue | 12 hours | The value of a stolen token |

The absolute ceiling is fixed at creation and cannot be extended by
working. `SessionPolicy.status_at` is a pure function of a session and a
timestamp, so every expiry rule is tested without waiting for one.

**Multiple sessions are supported.** An engineer at a workstation and on
a laptop is one person with two logins, and one must not end the other.

**All four rejection reasons are answered to the client as the same
`401`.** The distinction is recorded for the audit trail; disclosing it
would let the API be used to test whether a found token is real.

`last_seen_at` is written at most once a minute, so a read-only page load
does not become a database write.

## 6. Authorization

Three levels, and deliberately only three:

| | |
|---|---|
| **anonymous** | The absence of an identity. Not a role — there is no `Role.ANONYMOUS`, because a member there would be a value storable on a user row. |
| **engineer** | The ordinary authenticated user. May read and run everything the pipeline exposes, manage projects, and record engineering reviews. |
| **administrator** | Additionally manages identities and reads the audit trail. |

Capabilities, as of EPIC 30.4:

| Capability | engineer | administrator |
|---|---|---|
| `use_engineering_platform` | ✓ | ✓ |
| `manage_projects` | ✓ | ✓ |
| `record_engineering_review` | ✓ | ✓ |
| `manage_users` | | ✓ |
| `read_audit_trail` | | ✓ |

`record_engineering_review` is deliberately separate from
`use_engineering_platform`, which covers *reading* reviews: an auditor
role that may read every judgement without passing one is a role the
separation already admits, with no route changing. No "reviewer" role was
invented - reviewing the pipeline is what an engineer on this platform is
for, and a separate role would be a second one every engineer would have
to be granted on day one.

Routes declare a **capability**, never a role:

```python
Depends(require_capability(Capability.READ_AUDIT_TRAIL))
```

so that when project membership arrives, a capability can be granted from
a second source without any route changing. `403` on refusal, never
`401`: the caller is authenticated, and signing in again as the same
person cannot change the answer.

## 7. API security: deny by default

Every route is authenticated unless it appears in `PUBLIC_ROUTES`
(`app/routers/security.py`). A router added next year is protected
because nobody did anything.

`tests/api/test_api_security.py` walks **every path in the live OpenAPI
document** and requires each to be either declared public or to answer an
anonymous caller `401`. A companion test asserts the sweep can build a
URL for every route, so a new path parameter cannot make a hole look like
a pass.

### The public routes, and why

| Route | Why |
|---|---|
| `GET /` | A liveness banner naming the service and nothing else |
| `GET /health` | Read by orchestrators that hold no credential |
| `POST /auth/login` | Where a credential is exchanged for a session |
| `POST /auth/logout` | Ending a session must never require a live one |
| `GET /auth/session` | Answers "am I signed in?" — `200` or `401`, no data |
| `/openapi.json`, `/docs`, `/redoc` | The contract, not the content |

The API documentation is public **deliberately and revisitably**: it
describes the shape of the API, discloses no engineering data, and is
already committed to this repository as `openapi.json`. A deployment that
treats its API surface as confidential should remove those three.

## 8. Audit trail

`audit_events` is append-only. The repository port declares `record` and
`list_recent` and **no update or delete** — a trail an application can
edit proves nothing, so the interface offers no way to try. An
architecture test asserts the absence.

Every event carries the five fields the EPIC named: **actor, timestamp,
action, resource, outcome.**

Recorded today: `login_succeeded`, `login_failed`, `logout`,
`password_changed`, `user_created`, `user_disabled`, `project_created`,
`document_uploaded`, `pipeline_executed`, `engineering_review_recorded`,
`engineering_review_superseded`, `access_denied`.

The two review actions were added by EPIC 30.4. A review is already an
attributable, immutable record, so the trail is not its only account - it
is there because *"what did this person do on Tuesday?"* is asked of the
audit trail, and a governed engineering decision is exactly that kind of
action. See [human_review.md](human_review.md).

**Nothing sensitive is representable.** There is no field for a password,
a token, a fingerprint or a request body — structural, not conventional:
a value with nowhere to go cannot be written by accident. The actor is
either verified (copied from an `AuditIdentity`) or anonymous, and
`authenticated` says which. An address typed at a login form is recorded
as *what was attempted*, never as who attempted it.

`actor_user_id` is deliberately **not** a foreign key: the trail must
outlive the identities it records.

**An audit write that fails does not fail the audited action.** A login
that worked, refused at the last moment because the trail could not be
appended to, is worse than a login that worked and is missing from the
trail — and refusing every request when the audit table is unwritable
turns a logging fault into an outage. The failure is logged at
`exception` level. This is a deliberate, uncomfortable trade and a test
pins it.

## 9. Project ownership

`projects.owner_user_id`, recorded from the authenticated identity at
creation. Nullable, and staying nullable: every project created before
this milestone has no owner, and inventing one would be recording a fact
nobody established.

`created_by` used to be **accepted from the request body** — the record
of who created a project was whatever the caller typed. It is now taken
from the identity, and the field is gone from `ProjectCreate`.

One rule consults ownership, and only one:

```python
may_administer_project(identity, owner_user_id)
```

Enforced on **project deletion** — the destructive operation, and the one
worth guarding while no membership model exists. An administrator may
delete any project; an owner may delete their own; a project with no
owner may be deleted by any engineer, which is exactly what those
projects allowed yesterday.

The long-term shape is `user → project membership → permissions`. None of
it is built, and building it now would mean a table, an invitation flow
and a permission catalogue committed to ahead of a requirement.

### Governed retrieval, and why it opens nothing (EPIC 31.2)

`GET /projects/{id}/governed-retrieval/assets` requires
`use_engineering_platform` — the same capability
`/knowledge-graph/nodes` requires, because it reads exactly the same
rows, through a port (`GovernedKnowledgeReader`) with no write method at
all.

`project_id` on a governed retrieval query is **filtering, not
enforcement**, inherited unchanged from §9: any authenticated engineer
may read any project's governed knowledge, exactly as they already
could through the graph API. This milestone did not widen that and could
not have narrowed it without the membership model §9 describes — a
retrieval-shaped fix would have been project authorization implemented
in one endpoint and nowhere else, which is worse than the gap.

## 10. Hardening

| Threat | Answer |
|---|---|
| **Password disclosure** | Never stored, never reversible. No response schema can carry one — an OpenAPI test walks every schema reachable from a response and fails on `password`, `credential`, `secret`, `api_key`. A companion test asserts the three request models that *do* carry a password are unreachable from any response. |
| **Session fixation** | Unrepresentable. A session is created only by `authenticate`, its token only by the generator, and no input can influence it. There is no path by which a caller-supplied token becomes a session. |
| **CSRF** | `SameSite=Lax` plus a token bound to the session: `sha256(session_token + "|substationos-csrf")`, set in a readable cookie and echoed in `X-CSRF-Token` on every unsafe method, compared with `hmac.compare_digest`. Session-bound rather than plain double-submit, so a token captured from one session is useless against another. |
| **Credential leakage** | The session token leaves the server exactly once, in a `Set-Cookie` header. No body contains it, no schema has a field for it, and the frontend uses no web storage at all — asserted structurally on both sides. |
| **Timing attacks** | Digest comparison via `hmac.compare_digest`. An address nobody has registered still costs one full key derivation, so a non-existent account does not answer measurably faster than a real one. |
| **User enumeration** | Unknown address, wrong password and disabled account produce the identical status and body. The account status is checked *after* the password, so a disabled account is not distinguishable by trying a wrong password against it. |
| **Unsafe redirects** | There is no `?next=` parameter and no redirect from a supplied address. A frontend test fails on `window.location =`, `location.href =`, `redirect_uri`, `returnUrl` or `next=`. |
| **XSS → account takeover** | `HttpOnly` on the session cookie. An injected script can act as the user while it runs; it cannot walk away with a credential. No `dangerouslySetInnerHTML` or `innerHTML` anywhere — asserted. |

**No security primitive is invented.** scrypt from `hashlib`,
`secrets.token_urlsafe`, `hmac.compare_digest`, SHA-256. An architecture
test names them so replacing one is a deliberate act, and fails on a
hand-rolled construction.

## 11. Deployment requirements

Two things a deployment **must** do that the code cannot do for itself:

1. **Serve over TLS and set `Secure` on the cookies.** They are set
   without it so the platform runs over plain HTTP in development. Over
   the network without TLS, the session token is readable in transit and
   everything above is void.
2. **Serve the frontend and the API from one origin, or one reverse
   proxy.** `SameSite=Lax` cookies travel same-site; "site" is scheme plus
   registrable domain, and ports are ignored. In development both use
   `localhost` (which is why `config/env.ts` defaults to
   `http://localhost:8000` and **not** `127.0.0.1` — they are different
   hosts, and the cookie would silently not travel).

## 12. Known gaps and assumptions

- **No dependency manifest.** `apps/backend` has no `requirements.txt`,
  no `pyproject.toml` and no lockfile; dependencies exist only in a
  developer's `.venv`. This is why Argon2id was not adopted, and it is
  the single largest piece of operational debt in the repository. It
  should be fixed before any deployment.
- **No rate limiting on `/auth/login`.** scrypt makes each attempt
  expensive, which slows a brute force but does not stop one, and gives
  an unauthenticated caller a way to consume CPU. A rate limit and
  account lockout are the next hardening step.
- **No MFA and no SSO.** Explicit non-goals of this EPIC; the session
  model was chosen to accommodate both.
- **No password reset flow.** The architecture supports it; the workflow
  (mail channel, single-use token, expiry) is future work.
- **No secret rotation, and no signing key**, because nothing is signed —
  a consequence of opaque sessions, and one of their advantages.
- **The audit trail is unpaged.** `list_recent` is bounded by a mandatory
  `limit` (max 500, refused rather than clamped), which is adequate now
  and is not a substitute for paging.
- **Security headers** (`Content-Security-Policy`, `X-Frame-Options`,
  `Strict-Transport-Security`) are not set. They belong to the reverse
  proxy in this deployment model, and are not yet documented as a
  requirement anywhere but here.
- **Access control is per-role, not per-project.** Any authenticated
  engineer can read any project and any document, and may record a review
  against any statement in any of them. Project membership remains the
  next step.

---

## Files

| Concern | Location |
|---|---|
| Identity domain | `apps/backend/app/domain/identity/` |
| Audit domain | `apps/backend/app/domain/audit/` |
| Password hashing | `apps/backend/app/infrastructure/identity/scrypt_password_hasher.py` |
| Session tokens | `apps/backend/app/infrastructure/identity/secrets_token_generator.py` |
| Authentication service | `apps/backend/app/services/authentication_service.py` |
| API boundary | `apps/backend/app/routers/security.py` |
| Auth / users / audit API | `apps/backend/app/routers/{authentication,users,audit}.py` |
| Bootstrap | `scripts/create_administrator.py` |
| Frontend session | `apps/frontend/hooks/useSession.tsx` |
| Frontend guard | `apps/frontend/components/auth/` |
| Tests | `tests/domain/test_identity_domain.py`, `tests/infrastructure/test_password_hashing.py`, `tests/api/test_{authentication,api_security,audit}_api.py`, `tests/architecture/test_identity_boundaries.py`, `apps/frontend/tests/{authentication,security-architecture}.test.*` |
