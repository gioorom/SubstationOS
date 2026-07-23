# Attribute — Extraction Record

One copy of this template per reusable characteristic identified in a
source document — a rating, a setting, a dimension, a data point that could
apply to more than one piece of equipment (anything that would eventually
become an `AttributeDefinition`, per `CLAUDE.md` §4.3 and the YAML shape in
`CLAUDE.md` §7). See [`prompts/attributes.md`](../prompts/attributes.md)
for what counts as an attribute versus a one-off equipment nameplate value
already captured on an `equipment_template.md` entry.

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the attribute
  name, value, and unit are all printed explicitly next to each other;
  `Medium` when the value is printed but its unit or exact scope must be
  read from a legend or adjacent table; `Low` when any part is uncertain.

## Content

- **Attribute name (as labelled):** — the exact term the document uses
  (e.g. "Tensione nominale", "Rated Voltage"). Do not translate or
  normalize the term here — record it verbatim; normalization into a
  canonical `id` is a Stage 5 decision.
- **Value:** — the value as printed, verbatim, including its original
  notation (e.g. "132 kV", not "132000 V").
- **Unit:** — the unit as printed, separately from the value, for clarity
  (e.g. "kV"). `Not specified` if the document gives a value with no unit.
- **Data type (as it appears):** — numeric, text, boolean, enumerated list,
  etc., based only on how the value is presented in the document.
- **Allowed / alternative values:** — if the document presents a set of
  options (e.g. a selector position list, a range), list them verbatim.
  `Not specified` if only a single value is given.

## Description

A one-paragraph, source-grounded description of what this attribute
represents, using only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same attribute
  concept, if known. `None known yet` otherwise.
- **Related equipment:** — the equipment (as labelled in the source
  document) this attribute value was stated for. An attribute extracted
  without a clear equipment association is still valid — record
  `Not specified` here rather than guessing which equipment it belongs to.

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
