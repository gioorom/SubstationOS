# Extraction Prompt — Protections

## Purpose

Identify every protection function, interlock, and trip/alarm logic block
described in a source document, and record it using
[`protection_template.md`](../templates/protection_template.md).

## Scope — what counts as a protection function

Any named function whose purpose, as stated or drawn in the document, is to
detect an abnormal condition and produce a protective action: overcurrent,
overvoltage, differential, Buchholz, over-temperature, pressure-relief,
pole-discordance, and similar functions, together with interlocks that
block a command under a stated condition.

**Not a protection function for this category:**
- A bare status/alarm signal with no described trigger logic → `signals.md`
  (a protection function *produces* one or more signals; if the document
  only shows the resulting signal without describing the logic that
  produces it, extract the signal, and note in that entry's `Open
  questions` that the underlying function is not described on this page).
- The equipment being protected, and the fact of protection as a bare
  connection → also record as a `protects` relationship in
  `relationships.md`, in addition to the function entry here.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "protections", on the document `<document-code>`.
>
> Read the document page by page, in particular functional schematics
> labelled with device numbers, RIO/relay alarm and signal sheets, and any
> sigla/description tables that define device-number meanings. For every
> distinct protection function or interlock, produce one filled copy of
> `protection_template.md`.
>
> Rules, non-negotiable:
> 1. Record an ANSI/IEC device number only if the document itself prints
>    one next to the function. Do not infer a standard device number from
>    the function's described behavior (e.g. do not assume "51" for any
>    function that merely sounds like overcurrent protection unless the
>    document itself labels it "51").
> 2. Record `Trigger condition` and `Resulting action` only as far as the
>    document states them on the page you are reading. If the drawing shows
>    the trigger but the resulting action is on a different sheet, record
>    what is shown here and flag the cross-reference in `Open questions`
>    rather than following it.
> 3. Distinct trip and alarm outputs of what is otherwise the same
>    underlying function (e.g. a Buchholz relay's separate "alarm" and
>    "trip" stages) are extracted as separate entries, each with its own
>    tag, since the document itself typically gives them separate tags and
>    separate resulting actions.
> 4. Set `Confidence` per the template's criteria.
> 5. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/protections.md`, one
> filled template per entry, in the order encountered.

## Category-specific guidance

- Multi-stage protection devices (e.g. a level or pressure switch with
  separate "alarm" and "trip"/"scatto" thresholds) should be extracted as
  two entries, cross-referenced to each other via `References`, not
  collapsed into a single entry with two thresholds.
- Where a document explicitly separates "allarme" (alarm-only, no
  breaker action) from "scatto" (trip, causes a breaker or other action),
  preserve that distinction in `Function description` and `Resulting
  action` — do not normalize both into a generic "protection event."

## Illustrative example (not real extracted data)

```
Function tag (as labelled): 51C1
ANSI/IEC device number (if printed): 51
Function description (as labelled): BLOCCO PER MASSIMA CORRENTE
Protected equipment (as labelled): OLTC
Associated device (as labelled): DV7500
Trigger condition (as shown): Overcurrent detected on associated CT input
Resulting action (as shown): Blocks raise/lower command to OLTC
Confidence: High
```
