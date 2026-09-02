# ADR-0033: Pseudonymous Reference-Corpus Provenance

## Status

Accepted. Introduced by EPIC 33.R1, under
[Architecture Freeze AF-01](../architecture_freeze_af01.md), which is
`FROZEN_WITH_KNOWN_DEBT`. No AF-01 invariant is weakened, bypassed,
renamed away or reinterpreted. This changes the *meaning of two fields
on one value object*, not the shape of the pipeline.

Amends the provenance contract introduced by EPIC 32.E2 and extended by
[ADR-0030](0030-governed-structural-relationship-semantics.md).

## Context

The reference corpus is the one place in this repository where real
engineering documents are quoted. `ReferenceSource` was designed so that
a transcribed line could be found again in the drawing it came from:

```python
document_code: str    # "as printed on the drawing"
page_number: int
checksum: str         # SHA-256 of the file it was read out of
```

That design is correct for a private repository. It becomes a problem
when the repository is published, for a reason that has nothing to do
with how the documents were obtained:

- `document_code` is a real utility drawing number. Its segments encode
  the issuing organisation, the region, and the works order, so the code
  alone identifies a client, a plant and a sheet.
- `checksum` is a **confirmation oracle**. A digest does not reveal its
  input, but anyone holding the drawing can hash it and prove the corpus
  was built from that installation.

The engineering content quoted in the corpus is not the difficulty. The
transcribed lines are IEC 81346 reference designations and house-style
sheet-index wording — `MORSETTIERA -E1.L +189L`, `TA AT – ALLARMI SF6 TA`
— which carry no ratings, no settings and no topology, and which any
substation engineer writes. What identifies the source is the
combination of **named plant + works order + full drawing code + page +
file digest**. Breaking any one link is sufficient; the cheapest to
break is the identity, not the provenance mechanism.

## Decision

### 1. Source identity becomes a stable pseudonym

`document_code` no longer holds the code printed on the drawing. It
holds a **stable pseudonymous handle** drawn from a `REF-<family>-<sheet>`
scheme, resolved to the real drawing through a private map held outside
this repository.

| Handle family | Corresponds to |
|---|---|
| `REF-A-*` | the reference installation the current corpus is drawn from |
| `REF-B-*` | a second installation, retired from the corpus by EPIC 32.E4 |
| `REF-C-*` | a third installation, appearing only in extraction-format examples |

Installations are named `CP Alfa`, `CP Beta`, `CP Gamma`; the issuing
utility is described as *a single Italian DSO*. The letter families and
the Greek names correspond — `REF-A` is CP Alfa — and that correspondence
is recorded here deliberately rather than left for a reader to infer.

**The sheet suffix is kept.** `REF-A-S-025_01 LINEA AT SCHEMA FUNZIONALE`
retains "LINEA AT SCHEMA FUNZIONALE" because the document *type* is
load-bearing engineering signal: the corpus's central EPIC 32.E4 finding
is a claim about the difference between an HV-line sheet index and a
transformer sheet index. Strip the suffix and that finding becomes
unsupported. The identifying part was the `DD01-…-<works order>-…`
prefix, and that is gone.

### 2. `checksum` becomes `source_ref_digest`, and stops claiming to hash a file

The field is renamed in the dataclass **and in the YAML key**, and its
value becomes `SHA-256` over the pseudonymous `document_code` (UTF-8, no
trailing newline).

Renaming only the Python field would have been worse than doing nothing.
The corpus YAML is human-readable *on purpose*, so a domain expert can
audit the ontology without reading Python; a key still called `checksum:`
holding something that is not a checksum would mislabel it in exactly the
artefact designed for non-programmer review.

What the field still does:

- identifies a source **consistently** — two entries transcribed from one
  drawing carry one handle and one digest;
- distinguishes sources — different handles, different digests;
- is **recomputable by any reader from this repository alone**.

What it no longer does: pin the byte-stream or the revision that was
transcribed. That capability moves to the private map, which is where the
real code, the real digest and the real revision now live.

Alternatives rejected:

- **Keep the name, change the value.** Dishonest in the one file meant
  for non-programmer review.
- **A salted digest of the real file.** Preserves byte-level pinning, but
  makes the docstring false, makes the public repository depend on a
  secret it does not contain, and lets nobody recompute anything.
- **Delete the field.** Tempting, and nearly right: the "two entries came
  from one drawing" fact is carried by `document_code` equality, not by
  the digest, so deleting loses less than it appears to. Rejected because
  EPIC 33.R1 §7 requires converting provenance to a publication-safe form
  rather than removing it, and because a source handle that cannot be
  checked for internal consistency is weaker than one that can.

### 3. The architecture assertion is made meaningful again

`test_designation_evidence_boundaries.py` asserted `len(checksum) == 64`.
Under a surrogate that assertion still passes and tests nothing: it
would say only that a 64-character string is 64 characters long.

It is replaced by an assertion that the digest **equals** `SHA-256` of
the document code — which is a real property, fails if either field is
edited independently, and enforces the shared-source invariant that was
previously guarded by nothing at all.

### 4. What did not change

- No `lines:` entry and no `expected:` annotation was touched. The
  measured baseline stays at 33 matches, 3 false positives, 1 miss, and
  precision 0.917 / recall 0.971. Pseudonymisation cannot move a metric
  computed from transcribed text and hand annotations.
- `ReferenceDocument.is_real_source` is derived from the *presence* of a
  `source:` block, not from any value inside it, so the real-versus-
  authored distinction is immune to this change by construction.
- No evidence type, entity type, fact predicate, statement type, graph
  vocabulary or reasoning family changed.
- `corpus_version` moves **3.0 → 3.1**. A corpus is immutable data and
  editing it changes the version, but nothing about what *correct* means
  moved — only the metadata naming the source. The minor bump records an
  edit that does not invalidate evaluations recorded against 3.0.

## Consequences

### Good

- The repository can be published without naming a client, a plant or a
  works order, and without shipping an oracle that confirms which
  drawings were used.
- The provenance *architecture* survives intact. Real evidence stays
  distinguishable from authored fixtures, entries sharing a source still
  demonstrably share one, and the corpus still refuses an incomplete
  `source:` block.
- One previously unguarded invariant is now guarded.

### Costs and risks

- **A public reader cannot verify the corpus against the original
  drawings.** That is deliberate, and it is a real loss: the corpus is
  now trustworthy on the maintainer's word plus internal consistency,
  where before it was checkable by anyone holding the source. This is the
  price of publication and should not be described as anything else.
- **The private map becomes load-bearing.** If it is lost, the link from
  `REF-A-S-025_01` back to a real drawing is lost with it, and the corpus
  can never be re-derived or extended from the same sources.
- **Aggregate measurements remain**, and are a weaker oracle of the same
  class as the digest: "171 pages, 52 location aspects, LINEA AT
  functional diagram" is checkable by someone who already holds the
  drawing set. They are kept because they are the measured basis for the
  extraction rules — the four-character designation bound, the location
  pattern's 268 observations — and blunting them would falsify the
  reasoning those rules rest on. The asymmetry is acknowledged rather
  than hidden: a digest is a precise oracle for anyone, an aggregate is a
  weak one for someone who already has the documents.

### Debt recorded, not paid

- The private pseudonym map has no defined custody, format or backup
  procedure. It needs one before the corpus is extended.
- Prose describing the corpus must now say *a single Italian DSO's
  drawing standard* rather than any plural. The extraction bounds are
  defensible because the corpus is one issuer's house style; a plural
  would silently convert a bounded measurement into an overclaim.

## References

- [ADR-0030: Governed Structural Relationship Semantics](0030-governed-structural-relationship-semantics.md)
- [ADR-0032: Upstream Identity in Derived-Set Reuse](0032-upstream-identity-in-derived-set-reuse.md)
- [Architecture Freeze AF-01](../architecture_freeze_af01.md)
- IEC 81346-1, *Structuring principles and reference designations*
