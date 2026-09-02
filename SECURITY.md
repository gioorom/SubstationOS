# Security policy

## Supported versions

SubstationOS is pre-1.0 and under active development by a single author.
Only `main` is supported. There is no backported-fix branch.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting — the **Security** tab, then
*Report a vulnerability*. It opens a private channel visible only to the
maintainer, so nothing is disclosed while a fix is being prepared.

If that is unavailable to you, write to
`pietro_giovanni@elettroimpiantiromano.it` — the address in [`LICENSE`](LICENSE).

Please include what you did, what happened, and what you expected. A proof of
concept helps but is not required. Expect an acknowledgement within a few days;
this is a single-maintainer project, not a staffed security team, and it is
better to say so than to imply a response time nobody is on call to meet.

## Scope

This repository is engineering software, not a deployed service. There is no
production instance to attack and no bug-bounty programme.

Two things are worth stating plainly, because they shape what counts as a
vulnerability here:

- **Documents are untrusted input.** The pipeline ingests third-party PDFs and
  spreadsheets. Anything that lets a crafted document read or write outside its
  own derivation, execute code, or exhaust the host is in scope and is the class
  of report most worth sending.
- **Deployment hardening is knowingly incomplete.** Session cookies do not yet
  set `Secure`, because that behaviour has to become environment-aware before it
  is switched on. This is recorded debt rather than an unknown flaw, and it must
  be closed before any deployment. Reports of it are welcome but not novel.

## What this project does not do

No credentials, customer data, or engineering source documents are stored in
this repository. The reference corpus is pseudonymised; identities resolve only
through a private map held outside the repository.
