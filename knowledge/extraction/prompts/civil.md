# Extraction Prompt — Civil

## Purpose

Identify every civil-works structure named or drawn in a source document
(buildings, foundations, fencing, roads, drainage, oil containment), and
record it using [`equipment_template.md`](../templates/equipment_template.md).

There is no separate `civil_template.md`: a civil structure is, for
traceability purposes, the same kind of record as a piece of electrical
equipment — an individually identifiable, physical item with a label, a
location, and (sometimes) stated dimensions or characteristics. Using the
same template keeps every physical asset in the substation, electrical or
civil, in one consistent shape and lets `references` and
`related equipment` fields point across the two without translation. This
mirrors the existing ontology's own `civil` equipment category under
`app/domain/ontology/equipment_definitions/civil/`.

## Scope — what counts as civil for this category

Control buildings, transformer and equipment foundations, fencing, roads,
drainage systems, oil containment pits (bund walls), and similar physical
site infrastructure that is shown or labelled in the source document.

**Not civil for this category:**
- Electrical equipment housed inside a civil structure (a cell, a cabinet,
  a relay) → `equipment.md`.
- A dimension or capacity value stated for a civil structure (e.g. an oil
  pit's containment volume) → also extract as an `attributes.md` entry, in
  addition to the equipment-style entry here.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "civil", on the document `<document-code>`.
>
> Read the document page by page, in particular general-arrangement and
> foundation drawings. For every distinct civil structure named or drawn,
> produce one filled copy of `equipment_template.md`, using its
> `Category` field to record the civil structure type as the document
> states or implies it (e.g. "control building", "transformer foundation",
> "oil containment pit") rather than an electrical equipment category.
>
> Rules, non-negotiable:
> 1. Extract only what is explicitly labelled or dimensioned. Do not infer
>    construction materials, standards compliance, or capacity from typical
>    civil-engineering practice if the document does not state it.
> 2. Record dimensions and capacities exactly as printed, with their units,
>    as an `attributes.md` entry cross-referenced from this one.
> 3. Set `Confidence` per the template's criteria.
> 4. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/civil.md`, one filled
> template per entry, in the order encountered.

## Category-specific guidance

- A fence or road that runs the length of a drawing, with no single
  labelled dimension, is still extracted as one entry — set `Nameplate /
  rating data explicitly stated` to `Not specified` rather than estimating
  a length from the drawing scale.
- Oil containment/bund structures associated with a specific transformer
  should have that transformer recorded in `Related equipment`, so the
  relationship is discoverable even before a formal `relationships.md`
  entry is written for it.

## Illustrative example (not real extracted data)

```
Equipment name (as labelled): FONDAZIONE TR-01
Category: Transformer foundation
Location tag / cell: Not specified
Nameplate / rating data explicitly stated: Not specified
Construction details explicitly stated: Reinforced concrete slab, per plan view
Confidence: Medium
```
