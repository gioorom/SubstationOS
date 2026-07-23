# Protection Logic — Extraction Record

One copy of this template per protection function, interlock, or trip/alarm
logic block identified in a source document. See
[`prompts/protections.md`](../prompts/protections.md) for how a protection
function differs from a plain status signal (captured instead on
`signal_template.md`).

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`. In particular: never infer a
protection function's ANSI/IEC device number from its behavior if the
document itself does not print that number.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the function is
  explicitly labelled with a device number or name; `Medium` when only the
  logic is shown and the function name must be read from a legend on a
  different sheet of the same document; `Low` when the function's scope is
  ambiguous.

## Content

- **Function tag (as labelled):** — e.g. "51C1", "97TS", "SCATTO 87L".
- **ANSI/IEC device number (if printed):** — record only if the document
  itself prints a standard device number; otherwise `Not specified` — do
  not infer the ANSI number from the function's behavior.
- **Function description (as labelled):** — the plain-language description
  printed for this function, verbatim (e.g. "BLOCCO PER MASSIMA CORRENTE").
- **Protected equipment (as labelled):** — the equipment this function is
  shown protecting or interlocking.
- **Associated device (as labelled):** — the relay, RIO module, or
  protection device that implements this function, if named (e.g.
  "DV7500", "RIO 4 TR").
- **Trigger condition (as shown):** — what the drawing shows as the
  triggering input(s) for this function. Verbatim from the document; do not
  paraphrase into a general protection principle not stated in the source.
- **Resulting action (as shown):** — what the drawing shows this function
  doing when triggered (e.g. opens a specific breaker, blocks a specific
  command, raises an alarm only). `Not specified` if the resulting action
  is not shown on this sheet.

## Description

A one-paragraph, source-grounded description of this protection function,
using only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same function
  (e.g. the same tag on a different sheet), if known. `None known yet`
  otherwise.
- **Related equipment:** — protected equipment, associated device, and any
  other equipment named in the same logic block.

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
