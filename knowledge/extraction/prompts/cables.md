# Extraction Prompt — Cables

## Purpose

Identify every cable listed in a cable schedule, cable list, or
wire-routing table, and record it using
[`cable_template.md`](../templates/cable_template.md).

## Scope — what counts as a cable entry

Any row in a "Lista Cavi" / cable schedule table, or any cable identifier
referenced on a "Foglio di Posa Cavi" / wire-routing sheet, that names a
cable and at least one physical characteristic (formation, cross-section)
or endpoint.

**Not a cable entry for this category:**
- The individual signal(s) carried by the cable's conductors → `signals.md`
  (a cable entry may list which signals it is known to carry, if the
  schedule states this, but each signal still gets its own entry there).
- The equipment at either end → already captured under `equipment.md`; the
  cable entry references it by label, it does not re-describe it.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "cables", on the document `<document-code>`.
>
> Read every cable schedule ("Lista Cavi") and wire-routing sheet ("Foglio
> di Posa Cavi" or equivalent) in the document. For every distinct cable
> identifier, produce one filled copy of `cable_template.md`.
>
> Rules, non-negotiable:
> 1. Record the formation/cross-section notation exactly as printed,
>    including composite formations (e.g. "6x1.5+25x0.5") — do not simplify
>    or reinterpret the notation.
> 2. Record `From` and `To` using the location tags exactly as printed in
>    the schedule's own "Destinazione" (or equivalent) columns.
> 3. If a length column is present but reads "0 m" or is blank, record that
>    literally — a schedule with all lengths at "0 m" typically indicates a
>    design-stage document where lengths have not yet been surveyed; do not
>    interpret a zero as a real physical length and do not omit the field.
> 4. If the same cable identifier appears in both a summary "Lista Cavi"
>    table and a detailed "Foglio di Posa Cavi" routing sheet, extract both
>    occurrences as separate entries and cross-reference them via
>    `References` — do not merge them during extraction.
> 5. Set `Confidence` per the template's criteria.
> 6. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/cables.md`, one filled
> template per entry, in the order encountered.

## Category-specific guidance

- A wire-routing sheet often lists individual conductor-to-terminal
  mappings within a single cable (e.g. "wire 1 = blue = terminal A"). This
  level of detail belongs in `Description` as supporting narrative, not as
  separate cable entries — the cable entry is one per physical cable, not
  one per conductor.
- Where a schedule provides a "Codice articolo" (article/part code) column,
  record it in `Cable type / article code` even if the rest of the row's
  fields (e.g. length) are unpopulated in the source.

## Illustrative example (not real extracted data)

```
Cable identifier (as labelled): 14
Cable description (as labelled): COMANDI E SEGNALI INTERRUTTORE MT TRASFORMATORE
Formation / cross-section (as printed): 16x2.5 mm²
From (as labelled): +TELAIO
To (as labelled): +CELLA TR/TV MT
Length (if stated): 0 m
Confidence: High
```
