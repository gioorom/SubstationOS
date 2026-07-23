# Cable — Extraction Record

One copy of this template per cable identified in a cable schedule, cable
list, or wire-routing table. See
[`prompts/cables.md`](../prompts/cables.md) for how a cable-schedule entry
differs from a signal extraction (a cable carries one or more signals; the
cable itself, its physical characteristics and routing, is what this
template records).

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the cable's
  identifier, formation, and both endpoints are printed in the same table
  row; `Medium` when an endpoint must be cross-referenced from a different
  sheet; `Low` when any part is ambiguous.

## Content

- **Cable identifier (as labelled):** — the cable's "sigla"/number exactly
  as printed (e.g. "14", "580").
- **Cable description (as labelled):** — the plain-language description
  printed for this cable, verbatim (e.g. "COMANDI E SEGNALI INTERRUTTORE
  MT TRASFORMATORE").
- **Formation / cross-section (as printed):** — e.g. "16x2.5 mm²",
  "6x1.5+25x0.5". Record exactly as printed, including any composite
  formation notation.
- **Conductor count (as printed):** — if stated separately from the
  formation notation.
- **From (as labelled):** — the origin location tag / terminal block (e.g.
  "+TELAIO").
- **To (as labelled):** — the destination location tag / terminal block
  (e.g. "+DQ1910").
- **Length (if stated):** — as printed, including unit. `Not specified` if
  the schedule leaves length blank or zero (common in design-stage
  schedules) — record that fact rather than treating it as an omission.
- **Cable type / article code (if stated):**

## Description

A one-paragraph, source-grounded description of what this cable carries and
connects, using only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same cable
  (e.g. appearing in both a summary list and a detailed routing sheet), if
  known. `None known yet` otherwise.
- **Related equipment:** — the equipment at each endpoint, and any signals
  (per `signal_template.md`) known to be carried by this cable.

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
