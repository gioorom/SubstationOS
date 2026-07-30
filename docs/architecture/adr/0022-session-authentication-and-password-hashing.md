# ADR-0022: Session authentication and password hashing

## Status

Accepted.

## Context

EPIC 30.3 introduces authenticated identity, so that every future
engineering action can be attributed to a verified person. Two decisions
in it are hard to reverse — changing either later means a migration and a
forced credential reset — and are therefore recorded here.

**First**, how a request proves who is making it. The candidates were
stateless JWT bearer tokens, opaque bearer tokens in an `Authorization`
header, and opaque server-side sessions in a cookie.

**Second**, how a password is stored. The candidates were Argon2id
(`argon2-cffi`), bcrypt, and scrypt from the standard library.

The context that constrains both: a **private** engineering platform, for
enterprise deployment, that must accommodate SSO, MFA and richer RBAC
later without re-architecting; and a repository that has **no dependency
manifest of any kind** — dependencies exist only in a developer's
`.venv`.

## Decision

### 1. Opaque server-side sessions, in an `HttpOnly` cookie

A login exchanges a password for a 256-bit random token. The token is
returned only as an `HttpOnly`, `SameSite=Lax` cookie and is stored
server-side as a **SHA-256 fingerprint**, never as itself.

**JWT was rejected because a stateless token cannot be revoked.** Logout
would be a client-side gesture; disabling an account would not end its
live sessions until they expired on their own; "which sessions do I have
open, and end that one" would be unimplementable. All three are explicit
requirements of this EPIC, and a refresh-token scheme that reintroduces
server-side state to fix them is a session table with extra ceremony.

**A bearer token in a header was rejected because it has to live where
script can read it.** `localStorage` makes a cross-site scripting flaw an
account takeover that outlives the page; holding it in memory only loses
the session on every refresh. `HttpOnly` removes the credential from
JavaScript's reach entirely. The cost is CSRF, which is a solved problem
and is solved by a session-bound token echoed in a header.

The session token is stored hashed with **plain SHA-256**, and that is
correct rather than lax: it is 256 bits from a CSPRNG, so there is
nothing to guess, and the only requirement is that the stored form cannot
produce the token. A slow KDF would tax every authenticated request and
buy nothing.

### 2. scrypt from `hashlib`, in a self-describing format

Passwords are stored as `scrypt$n=32768,r=8,p=1$<salt>$<digest>` —
salted per credential, memory-hard, RFC 7914, on OWASP's list of
acceptable password hashes, and in the standard library.

**Argon2id is the better algorithm and is deliberately not used yet.** It
requires a compiled dependency, and this repository has nowhere to record
one: there is no `requirements.txt`, no `pyproject.toml` and no lockfile.
Adding a binary dependency that nothing declares is a worse position than
using a standard-library KDF that is genuinely adequate for the threat.

The move is **prepared for rather than promised**. Every credential
records the algorithm and parameters it was produced under; `needs_rehash`
compares them against current policy and returns true for any other
algorithm; and the authentication service re-derives a stale credential at
the one moment the plaintext password is legitimately in memory — a
successful login. Introducing Argon2id later is a new adapter and a
policy constant, with no migration and no forced reset.

### 3. Two independent session clocks

An idle timeout (2h, since last use) and an absolute lifetime (12h, since
issue). A session must satisfy both. The absolute ceiling is fixed at
creation and cannot be extended by working, which is what bounds the
value of a stolen token for a user who never stops.

### 4. Deny by default at the API boundary

Authentication is middleware plus a short list of explicitly public
routes, not a dependency on each of a hundred endpoints. A router added
next year is protected because nobody did anything; opening a route is a
visible edit to one file.

### 5. Three roles, and capabilities rather than roles at call sites

`engineer` and `administrator`, plus anonymous as the absence of an
identity. Routes declare a `Capability`, so a future project-membership
model can grant one from a second source without any route changing.

## Consequences

**Positive**

- Logout, forced sign-out, account disabling and session enumeration all
  work, because the server holds the session.
- A stolen database is not a set of live logins, and not a set of
  passwords.
- An XSS flaw in the frontend does not yield a credential that outlives
  the page.
- SSO and MFA fit without changing the session model: SSO opens the same
  session by a different proof, MFA gates its creation.
- No new dependency, and no invented cryptography.

**Negative**

- CSRF becomes this system's problem. Answered with `SameSite=Lax` plus a
  session-bound token, but it is a mechanism that must stay correct.
- Every authenticated request costs a session lookup and a user read. The
  user re-read is deliberate — it is what makes "disable this account"
  take effect immediately rather than whenever sessions happen to expire.
- The frontend and API must be same-site, or the cookie will not travel.
  In development this forces both onto `localhost`; in production it
  means one origin or one reverse proxy. Documented, and a real
  constraint.
- scrypt is a compromise. It is adequate and it is not the best available,
  and the gap is closed by adding a dependency manifest first.

**Neutral**

- `Secure` is not set on the cookies, so the platform runs over plain
  HTTP in development. A TLS deployment must set it;
  `security_architecture.md` §11 says so where an operator will look.
- There is no rate limiting on `/auth/login`. scrypt makes each attempt
  expensive, which slows a brute force without stopping one.

## Rejected Alternatives

**Stateless JWT bearer tokens.** Rejected because a stateless token
cannot be revoked. Logout would be a client-side gesture; disabling an
account would leave its sessions authenticating requests until they
expired; session enumeration and revocation would be unimplementable.
Adding a refresh-token store to fix those reintroduces exactly the
server-side state the format was chosen to avoid.

**Opaque bearer token in an `Authorization` header.** Rejected because
the token must then live where script can read it. `localStorage` turns
any XSS flaw into an account takeover that outlives the page; keeping it
in memory only loses the session on every refresh. The `HttpOnly` cookie
removes the credential from JavaScript's reach at the cost of CSRF, which
is a solved problem.

**Argon2id via `argon2-cffi`.** The better algorithm, rejected *for now*
because it is a compiled dependency and this repository has no dependency
manifest to record it in. Revisited as soon as that debt is paid; the
credential format, `needs_rehash` and the login-time re-hash exist so the
change is an adapter swap rather than a migration.

**bcrypt.** Rejected because it is not memory-hard, caps the input at 72
bytes (silently truncating a passphrase), and would still be a new
dependency — paying the dependency cost for a weaker algorithm than the
one already in the standard library.

**A single session timeout instead of two.** Rejected because idle and
absolute bound different things: an idle-only policy lets a session live
forever while it is used, and an absolute-only policy leaves an
unattended workstation open for the full lifetime.

**Per-endpoint authentication dependencies instead of middleware.**
Rejected because it fails silently the day somebody forgets one across a
hundred endpoints, and nothing tells them. Deny-by-default fails loudly
in the other direction, which is the direction that is safe.

**A role per future permission (reviewer, approver, auditor, …).**
Rejected as speculative. Every role is one that must be migrated,
documented and reasoned about for the life of the product; routes declare
capabilities so the catalogue can grow when a real permission needs it.

## Related

- `docs/architecture/security_architecture.md`
- ADR-0001 (project-centric architecture) — the Project boundary that a
  future membership model will hang from.
- NIST SP 800-63B, on length over composition rules for passwords.
- OWASP Password Storage and CSRF Prevention cheat sheets.
