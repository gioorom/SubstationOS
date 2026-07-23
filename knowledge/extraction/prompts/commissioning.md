# Extraction Prompt — Commissioning

## Purpose

Identify every factory test, site test, and commissioning step described
in a source document, and record it using
[`commissioning_template.md`](../templates/commissioning_template.md).

## Scope — what counts as a commissioning entry

Any named test procedure, inspection step, or acceptance requirement stated
in the document as something to be performed on equipment, whether before
delivery (factory test) or after installation (site test/commissioning).

**Not a commissioning entry for this category:**
- A protection function's own operating logic → `protections.md` (a
  commissioning entry may reference a protection function it verifies, but
  does not re-describe the function's logic).
- Actual, historical test results — this pipeline records what a procedure
  **is**, per its governing document, never what happened when a specific
  test was run on a specific date. Result tracking is out of scope for
  this knowledge-extraction pipeline entirely.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "commissioning", on the document `<document-code>`.
>
> Read the document for any section describing tests, inspections, or
> commissioning procedures. For every distinct procedure or step named,
> produce one filled copy of `commissioning_template.md`.
>
> Rules, non-negotiable:
> 1. Record `Acceptance criteria` only if the document states a pass/fail
>    condition explicitly. A procedure name with no stated criterion is
>    still extracted, with `Acceptance criteria` set to `Not specified`.
> 2. Never fill in a `Result` field — this template has none by design;
>    if you find yourself wanting to record an outcome, you are looking at
>    a project test record, not a governing procedure, and it is out of
>    scope for this pipeline.
> 3. Record `Test type` (Factory / Site / Commissioning Step) only as the
>    document itself labels or clearly structures it — do not assume a
>    test is a site test merely because it appears in a document whose
>    other content concerns installed equipment.
> 4. Set `Confidence` per the template's criteria.
> 5. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/commissioning.md`, one
> filled template per entry, in the order encountered.

## Category-specific guidance

- A single procedure that lists multiple discrete acceptance criteria
  (e.g. an insulation test with separate criteria per phase) is one entry,
  with all criteria listed verbatim under `Acceptance criteria` — split it
  into multiple entries only if the source document itself presents them
  as separate, independently-named procedures.
- If a document only references a procedure by number, without describing
  it (e.g. "per IEC 60076-3"), still extract an entry: record the
  reference in `Procedure reference`, and set every other content field
  that the document does not itself restate to `Not specified` — do not
  look up what the referenced standard requires.

## Illustrative example (not real extracted data)

```
Procedure name (as labelled): Prova di Isolamento
Test type: Factory Test
Associated equipment (as labelled): TR-01
Procedure reference (if stated): Not specified
Acceptance criteria (as stated): Insulation resistance ≥ 500 MΩ at 5000 Vdc
Confidence: High
```
