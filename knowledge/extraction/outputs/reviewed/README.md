# outputs/reviewed/ — Stage 3: Engineering Review

This directory holds raw extractions after a qualified engineer has read
them against the source PDF and rendered a verdict on every entry. It is
still not canonical: review confirms or corrects individual statements, it
does not yet decide how multiple statements about the same real-world
entity combine.

## What belongs here

The same file structure as `outputs/raw/`, mirrored path-for-path:

```
reviewed/<document-code>/<category>.md
```

Each reviewed file starts as a copy of its `raw/` counterpart. The reviewer
then, for **every** entry in the file, fills the `Engineering review` field
with one of:

- `Confirmed` — the source supports the statement exactly as extracted.
- `Corrected: <explanation>` — the extraction was inaccurate; the corrected
  statement and the reason are recorded in full, the original extracted
  text is left visible (struck through or quoted), never silently deleted.
- `Rejected: <reason>` — the statement should not have been extracted at
  all (e.g. it was inferred rather than stated); the entry is kept, marked
  rejected, and excluded from Stage 4, rather than deleted — a rejected
  extraction is itself a useful record of what an AI session got wrong.
- `Open question: <question>` — the reviewer cannot confirm or reject
  without more information (e.g. a second document, a site visit, an
  answer from the design engineer). The entry proceeds no further until
  resolved.

Reviewers do not change `Confidence`, `Source document`, or `Page` — those
describe the extraction, not the review. Disagreement with the source
document itself (e.g. a suspected drafting error) is recorded as an
`Open question`, never silently corrected against the document.

## What must be true before a file is considered "reviewed"

Every entry has a non-empty `Engineering review` field. A file with any
entry still reading `Pending` has not completed Stage 3 and must not be
used as input to Stage 4, regardless of how many other entries in the same
file are done.

## Who reads this directory

The engineer or knowledge owner performing Stage 4 canonicalization. As
with `outputs/raw/`, nothing here is cited directly by YAML domain
definitions or the Python domain model — only `outputs/canonical/` is.
