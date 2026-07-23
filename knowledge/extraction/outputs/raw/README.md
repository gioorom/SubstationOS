# outputs/raw/ — Stage 2: AI Extraction

This directory holds the direct, unreviewed output of an AI extraction
session. It is the least trusted artifact in the entire pipeline.

## What belongs here

One Markdown file per `(document, category)` pair, at:

```
raw/<document-code>/<category>.md
```

using the drawing code exactly as printed on the source document's title
block, and one of the nine category names listed in
[`../../README.md` §5](../../README.md#5-naming-conventions).

The file is a sequence of filled copies of the matching template from
[`../../templates/`](../../templates/) — one filled template per fact
extracted, in the order it was encountered in the source document. Nothing
is summarized, deduplicated, or reordered by significance; that is a later
stage's job.

## What must be true of every entry

Every extraction rule in
[`../../README.md` §4](../../README.md#4-extraction-rules) applies in full:
explicit source and page for every fact, `Confidence` never omitted,
`Not specified` instead of any assumption, no automatic merging of
apparent duplicates, conflicts recorded rather than resolved.

The `Engineering review` and `Canonical decision` fields of every template
are left as `Pending` here — filling them in is what turns a raw file into a
reviewed one (Stage 3).

## What does not belong here

- Anything not traceable to an explicit statement in the source PDF.
- Any file not named after an existing document code and category.
- Any attempt to resolve a conflict, pick between duplicates, or fill an
  `Open questions` entry with a best guess.

## Who reads this directory

Engineers performing Stage 3 review, and no one else. Nothing in `raw/` is
ever cited directly by `outputs/canonical/`, by YAML domain definitions, or
by the Python domain model. A fact only leaves this directory's authority
once it has been reviewed and copied forward — it is never referenced
in place.
