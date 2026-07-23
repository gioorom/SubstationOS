# Extraction Prompt — Equipment

## Purpose

Identify every physical piece of apparatus named or drawn in a source
document, and record it using [`equipment_template.md`](../templates/equipment_template.md).
This category feeds Stage 5's mapping onto `EquipmentDefinition` (see
`CLAUDE.md` §4.3).

## Scope — what counts as equipment

Physical, individually-identifiable apparatus: power transformers,
circuit breakers, disconnectors (isolators, earthing switches), instrument
transformers (CTs, VTs), protection relays and their I/O modules, switchgear
cells, cabinets, metering groups, auxiliary devices (fans, heaters, sockets)
when individually labelled.

**Not equipment for this category** (extract elsewhere instead):
- A characteristic value printed for a piece of equipment (rated voltage,
  cross-section, etc.) → `attributes.md`.
- The fact that two items are connected → `relationships.md`.
- A named signal, alarm, or command point → `signals.md`.
- A protection function or trip logic block → `protections.md`.
- A cable → `cables.md`.
- A building, foundation, or civil structure → `civil.md`.

## Extraction prompt

Use this text as the instruction for an AI extraction session working on
one source document:

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "equipment", on the document `<document-code>`.
>
> Read the document page by page. For every distinct, individually
> identifiable piece of physical equipment you find — whether shown as a
> symbol in a diagram, labelled in a title block, or named in a table —
> produce one filled copy of `equipment_template.md`.
>
> Rules, non-negotiable:
> 1. Extract only what is explicitly stated or drawn. Never infer a rating,
>    a manufacturer, or a construction detail that is not printed.
> 2. Every entry must cite the exact page (the document's own page/"Foglio"
>    number) and the exact label as printed.
> 3. If the same equipment symbol appears on multiple pages, extract it
>    once per page it appears on — do not merge across pages. Merging is a
>    later, human decision.
> 4. If you cannot tell whether two labels refer to the same physical
>    equipment or two different ones, extract both and note the ambiguity
>    in `Open questions`. Do not guess.
> 5. Set `Confidence` per the criteria in the template header — do not
>    default to `High`.
> 6. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to
> `outputs/raw/<document-code>/equipment.md`, one filled template per
> entry, in the order encountered in the document.

## Category-specific guidance

- A single physical unit that is drawn or labelled differently on different
  sheets (e.g. a transformer shown as a symbol on a single-line diagram and
  referenced by location tag on a schematic) is still extracted once per
  sighting, per rule 3 above — record the label as it appears on *that*
  page.
- Redundant or paired equipment (e.g. two circuit breakers "52MT1" and
  "52MT2") are separate equipment entries, never combined into one entry
  "just because they're similar."
- If a document's legend defines a symbol but no instance of that symbol
  appears on any page you were given, do not extract it — extraction
  records instances, not legend definitions (legend/terminology material
  belongs in `glossary.md`).

## Illustrative example (not real extracted data)

A generic example of a correctly filled entry, using invented values only,
to show the expected level of detail:

```
Equipment name (as labelled): CB-101
Category: Circuit breaker
Location tag / cell: +BAY-1
Nameplate / rating data explicitly stated: "Rated voltage: 145 kV"
Construction details explicitly stated: Not specified
Confidence: High
```
