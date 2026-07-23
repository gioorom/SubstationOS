# Extraction Prompt — Relationships

## Purpose

Identify every explicit connection, containment, or dependency between two
pieces of equipment, and record it using
[`relationship_template.md`](../templates/relationship_template.md). This
category is what eventually lets the ontology answer "what is connected to
what" and "what protects what" — the substation's topology.

## Scope — what counts as a relationship

A drawn connection line between two equipment symbols; an explicit textual
statement of connection, feeding, or containment; a shared location tag
that the document itself uses to assert containment (e.g. equipment listed
under a cell's own ubicazione/location table); an explicit protection
association shown on the same drawing element as both the protection
function and the protected equipment.

**Not a relationship for this category:**
- Two items merely appearing near each other with no drawn or stated
  connection — proximity on a page is never sufficient.
- A signal traveling between two devices — record that under `signals.md`;
  a relationship entry may *reference* a signal or cable that realizes a
  connection, but the signal/cable itself is extracted in its own category.
- A protection function's internal logic — that belongs to
  `protections.md`; a relationship entry only records *that* a protection
  function is associated with a piece of equipment, not how the function
  works.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "relationships", on the document `<document-code>`.
>
> Read the document page by page, in particular single-line diagrams and
> location/ubicazione tables. For every explicit connection, containment,
> or protection association between two named or labelled equipment items,
> produce one filled copy of `relationship_template.md`.
>
> Rules, non-negotiable:
> 1. Extract only relationships the document actually draws or states. A
>    relationship inferred purely from typical substation topology (e.g.
>    "breakers are usually between a busbar and a transformer") is not
>    permitted — if the document does not draw or state the connection
>    explicitly on the page you are reading, do not extract it.
> 2. Use the document's own vocabulary for the relationship type
>    (connects to / feeds / contains / protects / measures) rather than
>    inventing new relationship categories.
> 3. If a connection passes through intermediate equipment (CTs,
>    disconnectors, cables) on a single-line diagram, list every
>    intermediate item in `Intermediate equipment`, in drawing order.
> 4. If direction is not shown, set `Directionality` to `Not specified` —
>    do not assume power flow direction from typical substation
>    conventions.
> 5. Set `Confidence` per the template's criteria.
> 6. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/relationships.md`, one
> filled template per entry, in the order encountered.

## Category-specific guidance

- A single-line diagram often shows a long chain of equipment (busbar →
  disconnector → CT → breaker → CT → transformer). Extract this as one
  relationship entry per document if the document itself presents it as one
  continuous connection, with the full chain recorded in `Intermediate
  equipment` — do not artificially split it into several two-item
  relationships unless the document's own structure (e.g. separate tables)
  suggests that finer grain is more faithful.
- A protection relay associated with protected equipment via a labelled
  "RIO" or device tag is a `protects` relationship — extract it here in
  addition to (not instead of) the corresponding `protections.md` entry
  describing the function's logic.

## Illustrative example (not real extracted data)

```
Equipment A (as labelled): SBARRA AT
Equipment B (as labelled): CB-101
Relationship type (as shown): connects to
Directionality (if shown): Not specified
Intermediate equipment (if any): TA-101 (current transformer)
Confidence: High
```
