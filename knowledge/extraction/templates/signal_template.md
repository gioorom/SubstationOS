# Signal — Extraction Record

One copy of this template per named measurement, command, status/position
feedback, alarm, or trip point identified on a functional or wiring
schematic. See [`prompts/signals.md`](../prompts/signals.md) for how a
signal differs from a protection function (captured instead on
`protection_template.md`) and from a bare cable core (captured on
`cable_template.md`).

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the signal has an
  explicit label/tag printed at its origin; `Medium` when the label is
  implied by an adjacent terminal-block or sigla table; `Low` when uncertain
  which of several nearby labels applies.

## Content

- **Signal tag (as labelled):** — the exact designator printed on the
  schematic (e.g. "26QA", "SCATTO 87L", "VSC IN MARCIA").
- **Signal description (as labelled):** — the plain-language description
  printed alongside the tag, verbatim (e.g. "ALLARME TEMPERATURA
  TRASFORMATORE").
- **Signal type (as shown):** — one of: measurement (analog), command
  (output to a device), status/position feedback (input from a device),
  alarm, trip, interlock permissive — chosen by what the drawing shows the
  signal doing, not by assumption.
- **Engineering unit (if analog):** — e.g. "A", "V", "°C". `Not specified`
  for digital signals.
- **Voltage/logic level (if stated):** — e.g. "110 Vdc", "24 Vdc dry
  contact". `Not specified` if not printed.
- **Source device (as labelled):** — the device or equipment this signal
  originates from.
- **Destination device (as labelled):** — the device or equipment this
  signal is delivered to.
- **Cable/terminal reference (if shown):** — the cable identifier and/or
  terminal-block numbers the signal is routed through on this drawing.

## Description

A one-paragraph, source-grounded description of what this signal represents
and what it is used for, using only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same signal
  (e.g. the same tag appearing on a different sheet), if known. `None known
  yet` otherwise.
- **Related equipment:** — the source and destination equipment, and any
  intermediate equipment (e.g. a terminal block cabinet) the signal passes
  through on this drawing.

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
