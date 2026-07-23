# Extraction Prompt — Signals

## Purpose

Identify every named measurement, command, status/position feedback, alarm,
or trip point shown on functional and wiring schematics, and record it
using [`signal_template.md`](../templates/signal_template.md).

## Scope — what counts as a signal

Any individually-tagged I/O point on a functional or control schematic:
analog measurements (currents, voltages, temperatures), digital commands
(open/close, raise/lower), status or position feedback (open/closed,
running/stopped), and alarm/trip outputs that are not themselves a full
protection logic block (a bare trip contact tag is a signal; the logic that
produces it is captured under `protections.md`).

**Not a signal for this category:**
- A protection function's decision logic (trigger condition → resulting
  action) → `protections.md`.
- The cable that physically carries the signal → `cables.md` (the signal
  entry may reference the cable identifier if shown; the cable's own
  physical characteristics are extracted separately).
- A design-time rating or setting with no live/runtime character →
  `attributes.md`.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "signals", on the document `<document-code>`.
>
> Read the document page by page, in particular functional schematics,
> terminal-block tables, and sigla/description tables. For every
> individually tagged signal, produce one filled copy of
> `signal_template.md`.
>
> Rules, non-negotiable:
> 1. Extract the signal tag and description exactly as printed.
> 2. Classify `Signal type` only from what the drawing shows the signal
>    doing (an input arrow into a device is status/feedback; an output
>    arrow from a device is a command; a labelled alarm/trip box is
>    alarm/trip) — never guess a type from the tag name alone if the
>    drawing itself is ambiguous; in that case set `Confidence` to `Low`
>    and explain in `Open questions`.
> 3. Record source and destination devices exactly as labelled at each end
>    of the signal path shown on this page. If a signal's path continues
>    onto another page (common via "→ /NN.X" style cross-references), only
>    record what is shown on the current page and note the cross-reference
>    in `Open questions` rather than following it — a separate extraction
>    pass covers the linked page.
> 4. Set `Confidence` per the template's criteria.
> 5. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/signals.md`, one
> filled template per entry, in the order encountered.

## Category-specific guidance

- Sigla/description/position tables (common on Poppler-style functional
  schematics, listing tag, description, and terminal position in three
  columns) are an efficient, high-confidence source for this category —
  each row is normally one signal entry.
- A signal that fans out to multiple destinations on the same page (e.g.
  one alarm feeding both a local lamp and a remote telecontrol point) is
  extracted as separate entries per destination, each referencing the same
  `Signal tag`, so every destination is independently traceable.
- Signals whose only stated destination is "Disponibile" / "Available" /
  "Spare" are still extracted — record `Destination device` as
  `Not specified — spare/unused per source` rather than omitting the entry.

## Illustrative example (not real extracted data)

```
Signal tag (as labelled): 26QA
Signal description (as labelled): ALLARME TEMPERATURA
Signal type (as shown): alarm
Engineering unit (if analog): Not specified
Source device (as labelled): RIO 4
Destination device (as labelled): DV7500
Confidence: High
```
