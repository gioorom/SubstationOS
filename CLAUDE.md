# CLAUDE.md — SubstationOS Engineering Manual

This document is the single source of truth for how software is designed, written,
tested and shipped in **SubstationOS**. It is written for engineers and for AI
coding agents alike. Read it before writing any code. When in doubt, this manual
wins over habit, over convenience, and over "how the last file did it".

This is a project meant to live for **years**. Every decision in this document is
made to protect long-term clarity over short-term speed.

> Companion documents:
> - `PRODUCT_VISION.md` — product vision, mission, modules and roadmap.
> - `README.md` — quick start (kept intentionally short).

---

## 0. Finding Your Way Around

Read this manual once at task entry — it binds everything below. Then, unless
the change is small and in code you already know, start at
[`docs/ai-context/README.md`](docs/ai-context/README.md) and load **only** the
maps that task needs. Do not read all of them for a one-line fix, and do not
bounce between instructions and maps.

Work in this order: **MAP → SEARCH → READ → TRACE → IMPLEMENT → VERIFY.** The
maps exist so you read *less* of the repository, never as an excuse to preload
it.

**Navigation is not authority.** `docs/ai-context/` is a derived layer. It does
not override this manual, the executable architecture tests, accepted ADRs,
current domain and persistence contracts, migrations, the tests that prove
behavior, or the long-form references in `docs/architecture/`. Where a map and
the repository disagree, the repository wins: investigate, implement against
current authoritative evidence, and say so in your report rather than quietly
following the map. Each map names the baseline it was derived from; when
current code differs materially, re-verify the affected claims before relying
on them (§11 covers keeping the layer current).

**Trace before you change.** For unfamiliar or architecture-significant work,
establish who owns the responsibility, what it consumes and who consumes it,
its ports and adapters, what persists it and under which migration, the ADRs
governing it, the fitness functions guarding it, and the tests proving it.
Never speculate about code you have not opened.

**A context pack is a starting set**, not proof that nothing else is affected
(see
[`docs/ai-context/CONTEXT_LOADING_STRATEGY.md`](docs/ai-context/CONTEXT_LOADING_STRATEGY.md));
dependency discovery is still yours to do.

Nested instructions still apply where they exist: frontend work also follows
`apps/frontend/CLAUDE.md`.

---

## 1. Project Vision

SubstationOS is an **Engineering Operating System** for High-Voltage and
Primary Substations (HV / MV substations).

It transforms any technical documentation — PDF, DWG, DXF, images, technical
specifications, functional and wiring diagrams — into an **interrogable Digital
Twin** of the electrical installation.

SubstationOS is not a chatbot. Its value is not the AI model. Its value is a
rigorous, versioned, first-class model of the **electrical domain**: a proprietary
Electrical Ontology, a Knowledge Graph, and a substation comprehension engine.

The software must reflect that priority. **The domain is the product.** Everything
else — frameworks, databases, AI providers, file formats — is a replaceable detail.

---

## 2. Objectives

The codebase must, at all times, optimize for:

1. **Domain correctness.** An electrical engineer must recognize the model as a
   faithful representation of reality. Domain concepts are named as engineers name
   them, not as programmers find convenient.
2. **Longevity.** Code is read far more often than it is written. Optimize for the
   engineer who opens this file in three years.
3. **Replaceability of infrastructure.** Databases, AI providers, and file formats
   must be swappable without touching the domain.
4. **Testability.** Every domain rule is covered by a fast, deterministic test that
   needs no network, no database, and no AI provider.
5. **Explicitness.** No hidden magic, no implicit global state, no clever tricks.
   Boring, obvious code is a feature.
6. **Incremental delivery.** Small, self-contained, reviewable commits that always
   leave the system green.

---

## 3. Architectural Principles

These principles are aligned with `PRODUCT_VISION.md` and are binding:

- **Domain Driven Design** — the domain layer is the heart of the system.
- **Modular Architecture** — bounded contexts are explicit and isolated.
- **Hexagonal / Ports & Adapters** — the domain defines contracts (ports); the
  infrastructure provides implementations (adapters).
- **Dependency Rule** — dependencies point *inwards*. The domain depends on
  nothing. Infrastructure depends on the domain, never the reverse.
- **AI as a Service** — AI is an adapter behind a domain-owned interface, never a
  hard dependency of the domain.
- **Event Driven** — significant domain changes are expressed as events where it
  adds clarity, not ceremony.
- **Test Driven** — behavior is specified by tests first wherever practical.
- **API First** — external contracts are designed before implementation.
- **Cloud Native** — no reliance on a specific machine, path, or local state.

### The Dependency Rule, concretely

```
        infrastructure  ──depends on──▶  domain  ◀──depends on──  application/API
                                           ▲
                                           │
                              (domain depends on NOTHING)
```

If a domain module imports anything from `infrastructure`, a web framework, an ORM,
an AI SDK, or the filesystem — **it is a bug**, regardless of whether it works.

---

## 4. Domain Driven Design

### 4.1 The layers

| Layer | Location | Responsibility | May import |
|-------|----------|----------------|------------|
| **Domain** | `app/domain/**` | Entities, value objects, domain services, business rules, ports (abstract repositories) | Only the standard library and other domain modules |
| **Infrastructure** | `app/infrastructure/**` | Adapters: YAML loaders, filesystem/DB repositories, AI providers | Domain + external libraries |
| **Application / Services** | `app/services/**` | Orchestration, use cases, pipelines | Domain + infrastructure contracts |
| **Interface / API** | `app/routers/**`, `app/schemas/**` | HTTP endpoints, request/response DTOs | Application + domain |
| **Persistence models** | `app/models/**`, `app/database/**` | ORM models and DB session wiring | External libraries |

### 4.2 Building blocks

- **Value Object** — immutable, identity-less, defined by its attributes.
  Implemented as `@dataclass(frozen=True, slots=True)`.
  Example: `AttributeDefinition`, `EquipmentAttribute`, `EquipmentDefinition`.
- **Entity** — has a stable identity (`id`) that persists across state changes.
- **Aggregate** — a cluster of objects treated as a unit; accessed only through
  its aggregate root.
- **Domain Service** — a stateless operation that doesn't belong to a single
  entity (e.g. validation across a set of definitions).
- **Repository (Port)** — an abstract contract (`ABC`) for loading/saving
  aggregates. Lives in the **domain**. Its implementation lives in
  **infrastructure**.
- **Factory** — builds domain objects from raw input (e.g. a parsed YAML `dict`),
  enforcing invariants at construction time.
- **Catalog / Engine** — in-memory, queryable collections of domain definitions
  and the logic that operates over them.

### 4.3 The ontology bounded context (reference pattern)

`app/domain/ontology` is the canonical example every new context must imitate:

```
domain/ontology/
  models.py                 # shared value objects & enums (e.g. AttributeDataType)
  attribute_models.py       # value objects for a concept
  attribute_factory.py      # build value objects from dicts, enforcing invariants
  attribute_repository.py   # ABC port: contract for loading definitions
  attribute_catalog.py      # in-memory queryable collection
  attribute_validator.py    # domain rules / validation
  attribute_engine.py       # higher-level domain operations
  attribute_service.py      # domain-facing orchestration
  attribute_exceptions.py   # typed errors, all deriving from OntologyError
  attributes/*.yaml         # declarative domain data (the ontology itself)
  equipment_types/*.yaml    # declarative equipment definitions

infrastructure/ontology/
  attribute_yaml_loader.py            # reads & parses YAML into dicts
  filesystem_attribute_repository.py  # adapter implementing the domain port
```

**Rule of thumb:** the domain declares *what* an attribute is and *what rules it
obeys*; the infrastructure decides *where the bytes come from*.

---

## 5. Folder Structure

Monorepo root:

```
SubstationOS/
  apps/
    backend/                 # Python backend (primary application)
      app/
        domain/              # DDD domain layer — the heart
        infrastructure/      # adapters (YAML, filesystem, DB, AI)
        services/            # application/use-case orchestration
        routers/             # HTTP API endpoints
        schemas/             # API DTOs (request/response)
        models/              # persistence/ORM models
        database/            # DB session & wiring
        main.py              # application entry point
      tests/
        domain/              # fast, pure domain tests
        infrastructure/      # adapter tests (filesystem, loaders)
        integration/         # end-to-end pipelines
        fixtures/            # valid/ and invalid/ test data
      pytest.ini
  packages/                  # shared reusable libraries
  infrastructure/            # deployment, IaC, environment
  scripts/                   # operational & maintenance scripts
  storage/                   # local/dev artifact storage
  docs/                      # long-form documentation
  PRODUCT_VISION.md
  CLAUDE.md                  # this manual
  README.md
```

Placement rules:

- A new domain concept goes in `app/domain/<context>/` and **must not** know about
  YAML, HTTP, or a database.
- A new way to read/write data goes in `app/infrastructure/<context>/`.
- One concept per file. Files are grouped by concept prefix
  (`attribute_*`, `equipment_definition_*`), not by technical type.

---

## 6. Python Conventions

Target runtime: **Python 3.14**.

- **Always** start every module with `from __future__ import annotations`.
- Use modern built-in generics and unions: `list[str]`, `dict[str, object]`,
  `X | None`. Never import from `typing` what the built-ins now provide.
- **Type-annotate everything**: all function parameters, return types, and
  non-trivial locals. Public domain APIs are fully typed.
- Prefer **immutability**. Domain value objects are
  `@dataclass(frozen=True, slots=True)`. Use `field(default_factory=...)` for
  mutable defaults (`tuple`, `dict`).
- Prefer `tuple[X, ...]` over `list[X]` for collections that must not be mutated
  after construction (as in `EquipmentDefinition.attributes`).
- Ports are `abc.ABC` with `@abstractmethod`; the body is a docstring plus
  `raise NotImplementedError`.
- **No side effects at import time.** Modules must be safe to import.
- **No global mutable state.** Dependencies are passed explicitly via constructors
  (see `FilesystemAttributeRepository.__init__`).
- Constructor injection with sensible defaults:
  `loader: AttributeYamlLoader | None = None` then `self._loader = loader or ...`.
- Prefix internal attributes with a single underscore (`self._root`).
- Raise **typed, domain-specific exceptions** (deriving from a context base error
  such as `OntologyError`), never bare `Exception` or `ValueError` from the domain.
- Keep functions short and single-purpose. If a function needs a comment to explain
  a block, that block probably wants to be its own well-named function.
- Formatting: keep lines readable (≤ 79–88 cols); one import per logical group;
  standard library, third-party, then local imports, separated by blank lines.
- Follow **PEP 8** and **PEP 20** (The Zen of Python). Explicit is better than
  implicit.

---

## 7. YAML Conventions

YAML files under `app/domain/**` are **domain data**, not configuration. They *are*
the ontology and deserve the same rigor as code.

- **One concept per file.** Filename = the concept `id` in `snake_case`
  (`rated_voltage.yaml`, `breaker.yaml`).
- Files are **small, flat, and declarative**. No logic, no anchors/aliases gymnastics,
  no environment-specific values.
- Keys are `snake_case`. Values use domain terminology.
- **Stable, mandatory fields first**, then optional descriptive fields, then
  `metadata` last.

Attribute definition shape:

```yaml
id: rated_voltage
name: Rated Voltage
data_type: float
description: Nominal voltage assigned to equipment under specified operating conditions.
unit: kV
metadata:
  domain: electrical_rating
```

Equipment type shape:

```yaml
id: breaker
name: Circuit Breaker
category: primary_equipment
description: Device capable of making, carrying and interrupting electrical current under normal and fault conditions.
aliases:
  - CB
  - Circuit Breaker
  - Interruttore
tags:
  - switching
  - protection
  - high_voltage
```

Rules:

- `id` is immutable once shipped — other data and the Knowledge Graph reference it.
- `description` is a full, engineer-grade sentence.
- `aliases` are real-world synonyms and **may include other languages** (e.g.
  `Interruttore`) because they mirror how documents in the field name equipment.
- Units follow standard electrical notation (`kV`, `A`, `kA`, `Hz`).
- Every YAML domain file must be covered by a loader/factory test that proves it
  parses into a valid domain object.
- YAML is parsed with **safe** loading only. Never execute or eval YAML content.

---

## 8. Naming Conventions

Names are the primary interface of the codebase. Get them right.

- **Speak the domain.** Use the vocabulary of substation engineering:
  `EquipmentDefinition`, `AttributeDefinition`, `rated_voltage`,
  `breaking_capacity`, `current_transformer`. Never invent programmer synonyms for
  established electrical terms.
- **Identifiers are always English**: classes, functions, variables, files,
  modules, YAML keys, commit messages, and top-level documentation
  (`CLAUDE.md`, `PRODUCT_VISION.md`, `docs/`). This keeps the codebase legible to
  any engineer, regardless of first language, and matches the existing module
  naming (`attribute_catalog.py`, `EquipmentDefinition`, ...).
- **Docstrings and inline comments may be written in English or Italian**,
  whichever communicates the domain rule most precisely to the team maintaining
  this code. Do not mix languages within the same docstring or comment block.
  Domain-realistic string *data* such as `aliases` may also include Italian terms,
  since they mirror how equipment is named in the field.
- Files & modules: `snake_case.py`, grouped by concept prefix.
- Classes: `PascalCase` (`FilesystemAttributeRepository`).
- Functions, variables, YAML keys: `snake_case`.
- Constants & enum members: `UPPER_SNAKE_CASE` (`AttributeDataType.FLOAT`).
- Abstract ports read as contracts: `...Repository`, `...Loader`, `...Provider`.
- Concrete adapters name their technology: `Filesystem...`, `Yaml...`, `Claude...`.
- Domain errors end in `Error` and are specific: `AttributeDefinitionNotFoundError`,
  not `NotFound`.
- Boolean names are predicates: `required`, `is_valid`, `has_attribute`.
- Test files: `test_<module>.py`; test functions: `test_<behavior>()` describing
  the behavior, not the method name.
- No abbreviations except universally understood electrical ones (`CB`, `CT`, `VT`,
  `HV`, `MV`). If an engineer wouldn't recognize it, spell it out.

---

## 9. Testing

Testing is not optional and not an afterthought. The domain must be provable.

- Framework: **pytest**. Configuration in `apps/backend/pytest.ini`.
- Test layout mirrors the source layout:
  - `tests/domain/` — pure, fast, deterministic. No I/O, no DB, no network, no AI.
  - `tests/infrastructure/` — adapters against real files/fixtures.
  - `tests/integration/` — end-to-end pipelines across layers.
  - `tests/fixtures/valid/` and `tests/fixtures/invalid/` — canonical test data.
- **Test behavior, not implementation.** A test names an expected behavior and
  asserts on observable outcomes (see `test_equipment_definition_models.py`).
- Prefer many small, focused tests over few large ones. One reason to fail per test.
- Every domain rule, every invariant, and every custom exception path has a test.
- Every new YAML domain file is validated by a test proving it loads and is well
  formed.
- Tests are **independent and order-free** — no shared mutable state between tests.
  Shared setup lives in fixtures (`conftest.py` / `tests/fixtures/`).
- Bug fixes start with a **failing test** that reproduces the bug, then the fix.
- The full suite must be **green before every commit**:
  `python -m pytest` from `apps/backend/`.
- Domain tests must run in well under a second each. Slowness is a design smell.

---

## 10. Git Workflow

- **Main branch:** `main`. It is always releasable and always green.
- **Branch for real work.** Never build a feature directly on `main`; create a
  focused branch (`feature/...`, `fix/...`, `refactor/...`).
- **Small, atomic commits.** One logical change per commit. A commit compiles,
  passes tests, and leaves the system consistent.
- **Commit messages** are imperative and describe intent, matching the existing
  history style:
  - `Implement attribute catalog and validation`
  - `Add tests for YAML ontology loader`
  - Format: a concise subject line (~50 chars), then a blank line, then a body
    explaining *why* when the change is non-obvious.
- Do not mix refactoring and behavior change in the same commit.
- Do not commit generated artifacts, local databases (`*.db`), virtual
  environments (`.venv/`), caches (`.pytest_cache/`), or secrets (`.env`).
- Rebase local work to keep history linear and readable; do not rewrite shared
  history.
- Only commit or push when explicitly asked to do so.

---

## 11. Documentation

- **CLAUDE.md** (this file) — how we build. Update it when a convention changes.
- **PRODUCT_VISION.md** — what and why we build. The product north star.
- **README.md** — minimal quick start only.
- **docs/** — long-form architecture notes, decision records, and domain
  references.
- **docs/ai-context/** — derived navigation for finding your way around the
  repository (§0). It is regenerated from the codebase rather than maintained
  as a spec, so stale navigation is reported and refreshed when a material
  architecture change lands, not patched inside unrelated work.
- **Docstrings** document *intent and contract*, not mechanics: what a thing is,
  what it guarantees, what it raises. Ports document the contract implementers must
  honor.
- Every bounded context should carry a short note (docstring or `docs/`) explaining
  its responsibility and boundaries.
- Prefer self-documenting code over comments. Comments explain **why**, never
  **what** the code plainly already says.
- **Architecture Decision Records (ADRs):** significant, hard-to-reverse decisions
  (a new bounded context, a persistence choice, an external dependency) are recorded
  in `docs/` with context, decision, and consequences.
- When code and documentation disagree, that is a bug — fix whichever is wrong in
  the same change. The one exception is `docs/ai-context/`, which is derived
  rather than authored: report its drift instead of patching it inside
  unrelated work.

---

## 12. Refactoring

- Refactoring is **continuous and deliberate**, not a special event.
- **Refactor only under a green test suite**, and keep it green after every step.
- **Behavior-preserving changes are separate commits** from behavior changes.
- Leave code **cleaner than you found it** (the Boy Scout Rule) — but keep the
  cleanup proportionate and in scope.
- Prefer many tiny, verifiable steps over one large risky rewrite.
- When a concept starts leaking across layers, extract a port and push the detail to
  infrastructure — do not let the domain absorb accidental complexity.
- Delete dead code aggressively; version control remembers it.
- Never refactor to introduce speculative generality ("we might need it"). Build for
  the requirement in front of you (YAGNI).

---

## 13. Pre-Commit Checklist

Before **every** commit, verify all of the following:

1. **Tests pass** — `python -m pytest` from `apps/backend/` is fully green.
2. **The dependency rule holds** — no new domain import of infrastructure, web,
   ORM, AI SDK, or filesystem.
3. **Types are complete** — new/changed public functions are fully annotated.
4. **New behavior is tested** — including error paths and new YAML files.
5. **Names speak the domain** — no programmer jargon where an engineering term
   exists.
6. **No stray artifacts staged** — no `*.db`, `.venv/`, `__pycache__/`,
   `.pytest_cache/`, `.env`, editor files.
7. **No secrets** — no keys, tokens, credentials, or customer data.
8. **The commit is atomic** — one logical change, refactor separated from behavior.
9. **The message is clear** — imperative subject describing intent.
10. **Docs updated** — if a convention, contract, or structure changed, this manual
    or `docs/` reflects it. `docs/ai-context/` is excepted: it is refreshed when
    a material architecture change lands, not inside every commit.

If any item fails, the commit is not ready.

---

## 14. What You Must NOT Do

- **Do not** let the domain depend on infrastructure, frameworks, the filesystem,
  an ORM, HTTP, or an AI SDK. Ever.
- **Do not** put business rules in routers, loaders, ORM models, or YAML.
- **Do not** hardcode absolute paths, machine-specific values, or environment
  assumptions.
- **Do not** commit secrets, credentials, local databases, or generated artifacts.
- **Do not** introduce a new external dependency without a clear reason and, for
  significant ones, an ADR.
- **Do not** mutate frozen value objects or introduce hidden global state.
- **Do not** swallow exceptions silently or catch broad `Exception` to hide errors.
- **Do not** ship behavior without a test, or leave the suite red.
- **Do not** mix refactoring with feature work in one commit.
- **Do not** invent programmer-friendly names for established electrical concepts.
- **Do not** add speculative abstractions for imagined future needs (YAGNI).
- **Do not** copy-paste domain logic; extract and reuse it.
- **Do not** use `eval`, unsafe YAML/pickle loading, or execute untrusted input.
- **Do not** commit or push unless the user explicitly asks.
- **Do not** weaken this manual to make a shortcut pass. Change the manual
  deliberately, with reason, or follow it.

---

## 15. Coding Standards

- **Single Responsibility.** A module, class, or function does one thing.
- **Explicit over implicit.** Dependencies are injected, not discovered.
- **Fail fast, fail typed.** Validate at construction (factories) and raise
  specific domain errors early.
- **Immutability by default.** Reach for mutability only with a concrete reason.
- **Small surface area.** Keep public APIs minimal; hide internals behind `_`.
- **Pure domain.** Domain functions are deterministic and side-effect free; I/O
  lives at the edges (adapters).
- **Composition over inheritance.** Inheritance is for ports/contracts, not for
  code reuse.
- **No premature optimization.** Write clear code first; optimize only with a
  measured need.
- **Errors are values with meaning.** Each failure mode is its own exception type
  carrying the relevant identifiers (e.g. `attribute_id`).
- **Consistency beats personal preference.** Match the surrounding code's idioms,
  comment density, and naming.
- **Readability is the metric.** If a reviewer needs the author to explain it, it
  needs to be rewritten.

---

## 16. Enterprise Guidelines

This is enterprise software for utilities, TSOs, DSOs, and EPC contractors. It must
be trustworthy over a multi-year lifespan.

- **Backwards compatibility of the ontology.** Once an `id` is published, it is a
  contract. Renames are migrations, not edits.
- **Traceability.** Every meaningful change is a small, described commit; every
  significant decision is an ADR. Future engineers can reconstruct *why*.
- **Security by default.** No secrets in code or history; least privilege;
  safe parsing only; treat all external documents and inputs as untrusted.
- **Data integrity.** Domain invariants are enforced in code, not assumed. Bad data
  is rejected loudly at the boundary, never silently accepted.
- **Provider independence.** AI providers, storage, and databases sit behind
  domain-owned ports so any of them can be replaced without touching the domain.
- **Observability.** Prefer clear, structured errors and meaningful failures over
  silent degradation. A wrong answer is worse than a visible error in this domain.
- **Reproducibility.** Behavior must not depend on the machine, the wall clock, or
  ambient state. Given the same inputs, the system yields the same outputs.
- **Auditability of the domain model.** The ontology (YAML) is human-readable on
  purpose so domain experts can review it without reading Python.
- **Scalability of the codebase, not just the runtime.** New bounded contexts
  follow the ontology reference pattern so the team can grow without the
  architecture eroding.
- **Long-term over short-term.** When a fast path conflicts with clarity,
  correctness, or the domain model, choose the durable option. We are building for
  the engineer who arrives in three years.

---

*Understanding Electrical Infrastructure.*
