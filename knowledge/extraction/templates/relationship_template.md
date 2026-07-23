# Relationship — Extraction Record

One copy of this template per stated connection, containment, or dependency
between two pieces of equipment. See
[`prompts/relationships.md`](../prompts/relationships.md) for what counts
as a relationship worth extracting versus incidental drawing proximity.

Do not fill in a field with an inference. A relationship is only extracted
if the document shows or states it directly (a drawn connection line, an
explicit "feeds", "contains", "protects" statement, a shared cell/location
tag) — never because two items are merely plausible neighbors.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the connection is
  an unambiguous drawn line or explicit statement; `Medium` when it is
  implied by shared location tags or table structure; `Low` when the
  drawing is ambiguous about which of several nearby items is connected.

## Content

- **Equipment A (as labelled):**
- **Equipment B (as labelled):**
- **Relationship type (as shown):** — describe using the document's own
  vocabulary or graphical convention, e.g. "connects to" (drawn line),
  "feeds" (labelled power flow), "contains" (equipment inside a cell),
  "protects" (protection function associated with equipment), "measures"
  (instrument transformer associated with a circuit). Record what the
  document actually shows, not a category from an external taxonomy.
- **Directionality (if shown):** — e.g. "A feeds B", "bidirectional", or
  `Not specified` if the document does not indicate direction.
- **Intermediate equipment (if any):** — anything the document shows between
  A and B on the same connection (a CT, a disconnector, a cable) that this
  relationship passes through, listed in order.

## Description

A one-paragraph, source-grounded description of the relationship, using
only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same
  relationship, if known. `None known yet` otherwise.
- **Related equipment:** — any other equipment mentioned on the same
  drawing element that is relevant context for this relationship but is not
  Equipment A or B (e.g. a shared busbar both connect to).

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
