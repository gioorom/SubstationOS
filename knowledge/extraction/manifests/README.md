# manifests/ — Manifest Specification

Every source PDF that enters this pipeline gets exactly one manifest,
regardless of how many knowledge categories are eventually extracted from
it. The manifest is the audit record of that document's journey through the
pipeline: what it is, what has been done to it, and by whom.

A manifest is created the moment a document is first read for extraction
(Stage 2) and is updated — never recreated — as that document moves through
review and canonicalization. It is the single place to answer "has document
X been processed, by whom, and how completely?" without opening every raw,
reviewed, and canonical file that might reference it.

## File naming

```
manifests/<document-code>.md
```

using the drawing code exactly as printed on the document's own title
block — the same identifier used throughout `outputs/raw/` and
`outputs/reviewed/`, per
[`../README.md` §5](../README.md#5-naming-conventions).

## Required fields

Every manifest is a filled copy of [`manifest_template.md`](manifest_template.md)
and must contain the following fields. None may be omitted; a field with no
applicable value is filled with `Not specified`, never left blank.

| Field | Meaning |
|---|---|
| **Document name** | The full title of the document, as printed on its title block (e.g. "TRASFORMATORI AT/MT - SCHEMI ELETTRICI FUNZIONALI"). |
| **Project** | The project or plant the document belongs to, as printed on its title block (e.g. "C.P. Gamma (XX)"). |
| **Revision** | The document's revision index and date, as printed on its title block (e.g. "Rev. 00, 27.09.2025"). A manifest is tied to one specific revision — a new revision of the same drawing code gets its own manifest, cross-referenced (see `Related manifests` below). |
| **Discipline** | The engineering discipline the document belongs to (e.g. Electrical, Civil, Protection & Control, Instrumentation). |
| **Document type** | The category of document (e.g. Single-Line Diagram, Functional Schematic, Cable Schedule, Commissioning Procedure, Civil Drawing). |
| **Pages** | Total page count, and the document's own internal page numbering scheme if different from the PDF page index (e.g. "119 pages; internal numbering 'Foglio 1–119', offset +1 from PDF page index"). |
| **Extraction status** | One of: `Not started`, `In progress`, `Raw complete`, `Reviewed`, `Canonicalized`. Reflects the furthest pipeline stage this document has reached, across all categories. |
| **Reviewer** | The name of the engineer who performed Stage 3 review. `Not specified` until review begins. |
| **Extraction date** | The date Stage 2 (AI Extraction) was performed. |
| **Knowledge version** | A version marker for the extraction methodology used (see [Knowledge versioning](#knowledge-versioning) below), so a future methodology change never leaves ambiguity about which rules produced a given file. |

## Additional required tracking

Beyond the ten fields above, every manifest tracks, per category:

| Category | Raw | Reviewed | Canonicalized |
|---|---|---|---|
| equipment | ☐ | ☐ | ☐ |
| attributes | ☐ | ☐ | ☐ |
| relationships | ☐ | ☐ | ☐ |
| signals | ☐ | ☐ | ☐ |
| protections | ☐ | ☐ | ☐ |
| cables | ☐ | ☐ | ☐ |
| commissioning | ☐ | ☐ | ☐ |
| civil | ☐ | ☐ | ☐ |
| glossary | ☐ | ☐ | ☐ |

Not every document contains material for every category — a cable schedule
PDF will never populate `protections`. Categories with no applicable
material are marked `N/A` rather than left unchecked, so an empty box is
always distinguishable from "not applicable to this document."

## Knowledge versioning

`Knowledge version` records which revision of this extraction methodology
(this `README.md`, the prompts, and the templates, taken together) was in
effect when the document was extracted. Use the methodology's own change
history (tracked the same way `CLAUDE.md` §11 tracks convention changes) —
in the absence of a formal version scheme yet, record the date the
methodology was last deliberately changed. This lets a future reviewer tell
whether a given raw/reviewed file was produced under rules that have since
been tightened, and therefore whether it is due for re-extraction.

## Related manifests

If a document supersedes, is superseded by, or is a different revision of
another manifested document, that relationship is recorded explicitly in a
`Related manifests` field (see the template) — never inferred from file
names alone.
