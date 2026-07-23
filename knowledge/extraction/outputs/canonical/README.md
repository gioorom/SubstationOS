# outputs/canonical/ — Stage 4: Canonical Knowledge

This directory holds the only knowledge in `knowledge/` that Stage 5
(Ontology) and Stage 6 (YAML Definitions) are allowed to read from. Every
file here represents one real-world entity — one specific transformer, one
specific attribute concept, one specific signal — regardless of how many
source documents or reviewed entries describe it.

## What belongs here

One file per canonical entity, organized by category:

```
canonical/<category>/<entity-id>.md
```

using the nine category names from
[`../../README.md` §5](../../README.md#5-naming-conventions), and a short,
stable, kebab-case `entity-id` chosen at canonicalization time. Once
published, an `entity-id` is a contract, per `CLAUDE.md` §16 — it is not
renamed without a deliberate migration.

Each canonical file is a filled copy of the matching template, with two
differences from a reviewed entry:

- `References` lists **every** reviewed entry (across however many source
  documents) that this canonical record was built from, not just one.
- `Canonical decision` explains, by name, who made the canonicalization
  call, when, and — if multiple reviewed entries disagreed — exactly how
  the disagreement was resolved (e.g. "site as-built drawing S-031
  supersedes the earlier design drawing S-025 per Engineer X, 2026-03-10").
  A canonical file that merges two conflicting sources without this
  explanation is incomplete.

## What must be true before a file is considered canonical

- Every reviewed entry it draws from has an `Engineering review` verdict of
  `Confirmed` or `Corrected` — entries left `Rejected` or as an unresolved
  `Open question` are excluded, not silently folded in.
- Duplicates have been consciously merged into one entity, or consciously
  kept as separate entities with a documented reason (e.g. two physically
  distinct breakers that happen to share a nameplate description are not
  the same entity).
- `Canonical decision` is filled. A canonical file with `Canonical decision`
  still reading `Pending` is not yet canonical, regardless of what
  directory it happens to sit in.

## Who reads this directory

Engineers performing Stage 5 (mapping canonical knowledge onto ontology
concepts) and, ultimately, whoever authors the resulting YAML under
`app/domain/ontology/attributes/*.yaml` and
`app/domain/ontology/equipment_definitions/**/*.yaml`. Per
`CLAUDE.md` §7's YAML rules, that authoring step is expected to reference
the corresponding canonical file(s) so the trail described in
[`../../README.md` §6](../../README.md#6-traceability-philosophy) stays
unbroken all the way into version-controlled domain data.
