# Commissioning Procedure — Extraction Record

One copy of this template per factory test, site test, or commissioning
step identified in a source document. See
[`prompts/commissioning.md`](../prompts/commissioning.md) for the scope of
this category.

Do not fill in a field with an inference. If the document does not state a
value explicitly, write `Not specified`. In particular: never fill in a
`Result` — this template records what a test **is**, per its governing
document, not what happened when it was performed. Actual test results,
when available, belong to a separate, project-specific test record, not to
this knowledge-extraction pipeline.

## Identification

- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` / `Medium` / `Low` — `High` when the test/step is
  explicitly named with a clear scope; `Medium` when the scope must be
  inferred from surrounding procedural context on the same page; `Low` when
  ambiguous.

## Content

- **Procedure name (as labelled):** — e.g. "Factory Acceptance Test",
  "Prova di Isolamento".
- **Test type:** — Factory Test / Site Test / Commissioning Step, chosen
  by what the document itself states, not by assumption about where the
  test would normally occur.
- **Associated equipment (as labelled):** — the equipment this
  procedure applies to.
- **Procedure reference (if stated):** — a referenced standard, internal
  procedure number, or document the source cites for this test (e.g. an
  IEC standard number, if and only if the source document itself prints
  it).
- **Acceptance criteria (as stated):** — the pass/fail condition as printed,
  verbatim. `Not specified` if the document names the test but does not
  state a criterion.
- **Required equipment / instrumentation (if stated):**

## Description

A one-paragraph, source-grounded description of what this procedure
verifies and how, using only wording the document supports.

## Traceability

- **References:** — other extraction entries describing the same
  procedure, if known. `None known yet` otherwise.
- **Related equipment:** — equipment under test, and any equipment used to
  perform the test (test sets, instrumentation) if named.

## Review

- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.
