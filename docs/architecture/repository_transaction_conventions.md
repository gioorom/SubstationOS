# Repository Transaction Conventions

**Status:** Binding convention, established by Milestone 12 (Knowledge
Platform Hardening) after an audit of every repository adapter's
persistence behavior. New bounded contexts follow this document; it is
updated when a genuinely new transaction shape is needed, not casually.

## The two shapes that exist in this codebase today

### 1. Aggregate-local commit (the default)

Every repository adapter for Project, Engineering Index, Proposed
Claims, Review Workflow, Canonicalization, and Graph Builder
(`SqlAlchemyProjectRepository`, `SqlAlchemyEngineeringIndexRepository`,
`SqlAlchemyProposedClaimRepository`, `SqlAlchemyReviewCandidateRepository`/
`SqlAlchemyReviewHistoryRepository`, `SqlAlchemyCanonicalFactRepository`,
`SqlAlchemyGraphOperationBatchRepository`) **commits inside its own
write method**. A single call - `save()`, `create()`, `update()` -
persists exactly one aggregate (and, where relevant, its own owned
child rows: a claim's evidence, a fact's evidence, a batch's
operations) as one atomic unit, then returns.

This is correct, not merely convenient: each of these use cases really
is "one aggregate root, one write, one commit." A claim and its
evidence are created together or not at all; a batch and its operations
are saved together or not at all. `IntegrityError` from a natural-key
violation (e.g. `DuplicateProposedClaimError`, `DuplicateIndexEntryError`)
is caught, the session is rolled back, and a typed domain exception is
raised - the caller never sees a raw SQLAlchemy exception.

**Rule: a repository may commit its own write when the entire write is
one aggregate's own data**, including its directly-owned child rows.

### 2. Flush-only + explicit Unit of Work (Project Knowledge Graph execution only)

`SqlAlchemyGraphStore` and `SqlAlchemyGraphExecutionRepository` never
call `commit()` or `rollback()`. Every write method only `add()`s and
`flush()`s (flush surfaces `IntegrityError` immediately, and assigns
auto-increment ids, without ending the transaction). `GraphExecutionService.execute_batch`
is the only thing that calls `GraphUnitOfWork.commit()`/`.rollback()`,
exactly once per attempt, after every operation in a
`GraphOperationBatch` has either all succeeded or one has failed.

This is the one case in the codebase where a single logical write
spans **more than one repository call across more than one aggregate
type** (many nodes, many relationships, one execution record) and must
still be all-or-nothing. No other bounded context has this shape today.

**Rule: a repository must be flush-only, and a `GraphUnitOfWork` (or
an equivalent, use-case-specific Unit of Work) is required, only when
one logical write genuinely spans more than one repository call and
must be atomic across all of them.** Do not default to this shape - it
exists because the requirement (execute a batch atomically, retry
idempotently) could not be met otherwise, not because it is generally
"more correct" than aggregate-local commit.

## Who owns rollback

- **Shape 1 (aggregate-local):** the repository itself. It is the only
  thing that opened the transaction (implicitly, via its own
  `add()`/`commit()`), so it is the only thing that rolls it back on
  `IntegrityError`.
- **Shape 2 (Unit of Work):** the service. Repositories participating
  in a Unit of Work never call `session.rollback()` themselves - only
  `GraphUnitOfWork.rollback()` does, and only the service decides when
  to call it (on catching a `GraphExecutionOperationError`).

## How infrastructure exceptions are translated

Every repository catches `sqlalchemy.exc.IntegrityError` at its own
write boundary (never lets it propagate as a raw SQLAlchemy exception)
and raises a typed domain exception instead - e.g.
`DuplicateProposedClaimError`, `DuplicateIndexEntryError`,
`ConcurrentGraphMutationError`. This is what CLAUDE.md SS16
("Translate relevant IntegrityError cases into typed domain/application
errors") means in practice: the domain and service layers never see a
`sqlalchemy.exc.*` exception type.

## How tests verify atomicity

- **Aggregate-local repositories:** a natural-key uniqueness test
  (insert twice, assert the typed duplicate exception, assert exactly
  one row survives) is sufficient - see e.g.
  `tests/infrastructure/test_sqlalchemy_engineering_index_repository.py::test_save_rejects_a_duplicate_natural_key`.
- **The Project Knowledge Graph Unit of Work:** requires two layers of
  proof, both present in this codebase:
  1. A service-level test against fake ports
     (`tests/services/test_graph_execution_service.py`) asserting the
     fake `GraphUnitOfWork.rollback()` was called and the fake store
     holds zero rows after a mid-batch failure - fast, no database.
  2. A real-database test
     (`tests/infrastructure/test_project_knowledge_graph_transaction_atomicity.py`)
     against the actual SQLAlchemy adapters and an isolated in-memory
     database, proving the same guarantee end-to-end: zero
     `project_graph_nodes` rows, exactly one `graph_executions` row
     (the standalone `FAILED` record), and a session that remains
     usable afterward.

Any future bounded context introducing a new Unit of Work must add
both kinds of test, not just the fake-based one.

## What this document deliberately does not do

- **It does not leak `Session` into domain objects.** Every port
  (`ProjectRepository`, `GraphStore`, `GraphExecutionRepository`,
  `GraphUnitOfWork`, ...) is an `ABC` the domain and service layers
  depend on; `Session` appears only inside `app/infrastructure/**`
  adapter `__init__` methods.
- **It does not introduce a global Unit of Work.** Every bounded
  context except Project Knowledge Graph execution uses aggregate-local
  commit, and Milestone 12's audit found no defect (partial write,
  nested commit, impossible rollback) in any of them - `GraphUnitOfWork`
  itself was already decided and recorded in
  [ADR-0007](adr/0007-project-knowledge-graph-persistence.md); this
  document only confirms no other bounded context has since needed one,
  and would not introduce one speculatively if it hadn't (CLAUDE.md
  SS12, YAGNI).
