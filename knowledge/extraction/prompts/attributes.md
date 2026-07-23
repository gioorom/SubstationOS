# Extraction Prompt — Attributes

## Purpose

Identify every reusable characteristic value stated in a source document,
and record it using [`attribute_template.md`](../templates/attribute_template.md).
This category feeds Stage 5's mapping onto `AttributeDefinition` (see
`CLAUDE.md` §4.3 and the YAML shape in `CLAUDE.md` §7).

## Scope — what counts as an attribute

Any named value that describes a characteristic, rating, setting, or
dimension — of equipment, of a system, or of a signal — that could apply to
more than one equipment instance in principle (rated voltage, rated
current, breaking capacity, insulation level, tap-changer range, oil
volume, torque setting, temperature threshold).

**Not an attribute for this category:**
- The equipment the value belongs to — that is captured on the equipment
  entry's own `Nameplate / rating data` field as well; the attribute entry
  here exists to give that value its own traceable, reusable record with a
  proper name and unit, independent of which specific equipment it was
  first observed on.
- A one-off descriptive label with no numeric or enumerated value (e.g. a
  free-text note) — that belongs in `Description` fields elsewhere, not as
  an attribute.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "attributes", on the document `<document-code>`.
>
> Read the document page by page. For every explicitly stated
> characteristic value — a rating, a setting, a dimension, a threshold —
> produce one filled copy of `attribute_template.md`.
>
> Rules, non-negotiable:
> 1. Extract the value and its unit exactly as printed. Never convert units,
>    never round, never normalize notation.
> 2. Record the attribute's name exactly as the document labels it — do not
>    translate it and do not substitute an English engineering term for an
>    Italian (or other language) label. Normalization is a Stage 5 decision.
> 3. If a value is printed without an associated equipment label nearby,
>    still extract it, and set `Related equipment` to `Not specified` —
>    do not guess which equipment it belongs to from context.
> 4. If the same attribute concept (e.g. "rated voltage") is stated multiple
>    times in the document with different values for different equipment,
>    extract each occurrence as its own entry. Do not average, range, or
>    otherwise combine them.
> 5. Set `Confidence` per the template's criteria.
> 6. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/attributes.md`, one
> filled template per entry, in the order encountered.

## Category-specific guidance

- A range or a set of discrete options (e.g. tap-changer positions "−12 to
  +12") is one attribute entry with `Allowed / alternative values` listing
  the full set, not one entry per position.
- Attributes that are themselves signals with a live, changing value on a
  functional schematic (a measured current, a measured voltage) are
  extracted under `signals.md`, not here — `attributes.md` is for
  *design-time* characteristics and settings, not runtime measurement
  points.
- When the same nameplate table lists many attributes for one piece of
  equipment, extract each as a separate entry — do not combine a nameplate
  table into a single free-text attribute entry.

## Illustrative example (not real extracted data)

```
Attribute name (as labelled): Rated Voltage
Value: 145
Unit: kV
Data type (as it appears): numeric
Allowed / alternative values: Not specified
Related equipment: CB-101
Confidence: High
```
