# Equipment — Extraction Record

One copy of this template per physical piece of apparatus identified in a
source document (a transformer, a circuit breaker, a disconnector, an
instrument transformer, a protection relay, a cabinet, a switchgear cell —
anything that would eventually become an `EquipmentDefinition`, per
`CLAUDE.md` §4.3). See [`prompts/equipment.md`](../prompts/equipment.md)
for what counts as equipment for this category.

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`.

## Identification

- **Source document:** — the document's own title, as printed on its title
  block.
- **Drawing code:** — the drawing code exactly as printed (e.g.
  `AA00-XXX-YYY-ZZ00.1.000000-0-S-027`).
- **Page:** — the page number printed in the document's own title block
  (its "Foglio" or equivalent), not the PDF page index, unless the document
  has no internal numbering (state that explicitly if so).
- **Confidence:** `High` / `Medium` / `Low` — `High` only when the
  equipment is named or labelled explicitly and unambiguously; `Medium`
  when the label is present but the exact scope is inferred from drawing
  context (e.g. a symbol without a text label, disambiguated only by its
  position in a single-line diagram); `Low` when the identification is
  tentative.

## Content

- **Equipment name (as labelled):** — the exact designation printed next to
  or inside the equipment symbol (e.g. "TR ROSSO AT/MT", "52AT").
- **Category:** — the broad category the document itself implies or states
  (e.g. power transformer, circuit breaker, disconnector); do not assign an
  ontology `category` value here — that mapping happens at Stage 5.
  Describe only what the document supports.
- **Location tag / cell:** — the electrical location designator used in the
  document, if any (e.g. `+GST002`, `+CELLA TR/TV MT`).
- **Nameplate / rating data explicitly stated:** — list every rated value
  printed for this equipment (voltage, power, current, etc.) verbatim,
  each with its own unit as printed. If none are printed on this document,
  write `Not specified` — do not look up typical values.
- **Construction details explicitly stated:** — anything the document
  states about construction (number of windings, cooling type, tap-changer
  presence, bushing arrangement, etc.), verbatim. `Not specified` if none.

## Description

A one-paragraph, source-grounded description of what this equipment is and
does, using only wording the document supports. Do not add general
engineering knowledge about the equipment type not present in the source.

## Traceability

- **References:** — list of every other extraction entry (raw, reviewed, or
  canonical) that also describes this same physical equipment, if known at
  the time of writing. Leave `None known yet` if this is the first sighting.
- **Related equipment:** — other equipment this item is shown connected to,
  contained in, or dependent on in this document, each with its own label
  as printed. This is a pointer for the `relationships` category, not a
  substitute for it — do not describe the relationship type here.

## Review

- **Open questions:** — anything ambiguous, illegible, or apparently
  contradictory about this equipment in this document. `None` if there are
  none.
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
