# Extraction Prompt — Glossary

## Purpose

Capture the terminology, abbreviations, and equipment aliases used across
the document set, in whatever language they appear. This category directly
feeds the `aliases` field of the ontology's YAML definitions
(`CLAUDE.md` §7), which explicitly welcomes non-English, field-realistic
terms (e.g. Italian "Interruttore" for Circuit Breaker) because they mirror
how documents in the field actually name equipment.

There is no separate `glossary_template.md` — a glossary entry is
deliberately lighter-weight than the other categories. Use the inline
record shape given below.

## Scope — what counts as a glossary entry

- An abbreviation or device tag defined in a document's own legend or
  "Legenda Simboli" (e.g. "TA = Trasformatore di Corrente").
- A term used consistently across a document to refer to an equipment
  category or concept, whether or not it is formally defined (e.g. a
  document that always calls a disconnector a "sezionatore").
- Any explicit synonym relationship the document itself states (e.g. a
  bilingual title block, or a note equating two designations).

**Not a glossary entry:** a specific equipment instance's own label (e.g.
"TR ROSSO") — that is an equipment identification, not a term definition,
and belongs in `equipment.md`.

## Record shape

For each term, record:

- **Term (as printed):** the exact word or abbreviation as it appears.
- **Language:** the language the term is in, if determinable (e.g.
  Italian, English). `Not specified` if ambiguous.
- **Expansion / definition (as stated):** the document's own definition or
  expansion, verbatim. `Not specified` if the term is used but never
  formally defined in this document — still extract the term itself; its
  meaning can be corroborated across documents at review time.
- **Equivalent term(s) (if stated):** any other term the document
  explicitly equates this one with (e.g. from a bilingual legend).
- **Source document:**
- **Drawing code:**
- **Page:**
- **Confidence:** `High` when the term is formally defined in a legend;
  `Medium` when only used consistently without formal definition; `Low`
  when usage is inconsistent or ambiguous within the document itself.
- **References:** other extraction entries for the same term, if known.
- **Open questions:**
- **Engineering review:** `Pending` until Stage 3.
- **Canonical decision:** `Pending` until Stage 4.

## Extraction prompt

> You are performing Stage 2 (AI Extraction) of the SubstationOS knowledge
> pipeline, category "glossary", on the document `<document-code>`.
>
> Read every legend, symbol key, and abbreviation table in the document,
> plus any other page where a term is defined or explicitly equated with
> another. For every distinct term, abbreviation, or explicit synonym
> relationship, produce one entry using the record shape above.
>
> Rules, non-negotiable:
> 1. Record the term exactly as printed, including capitalization and any
>    diacritics.
> 2. Never translate a term into English as part of extraction — record it
>    in its original language, in `Term (as printed)`; a canonical,
>    normalized name is chosen only at Stage 5, when mapping onto the
>    ontology.
> 3. If a term is used differently in different parts of the same document,
>    extract it once per distinct usage and note the inconsistency in
>    `Open questions` rather than picking the "correct" one.
> 4. Set `Confidence` per the criteria above.
> 5. Leave `Engineering review` and `Canonical decision` as `Pending`.
>
> Write your output to `outputs/raw/<document-code>/glossary.md`, one
> entry per term, in the order encountered.

## Category-specific guidance

- Prioritize legend/"Legenda Simboli" pages — they are the highest-
  confidence source for this category and are usually concentrated on one
  or two sheets near the front of a document.
- A device-number legend (e.g. a table mapping ANSI numbers to function
  names) is both a glossary source and useful corroborating context for
  `protections.md` extraction of the same document — extract it here as
  terminology; the functions themselves, where they appear on schematics,
  are extracted separately under `protections.md`.

## Illustrative example (not real extracted data)

```
Term (as printed): Sezionatore
Language: Italian
Expansion / definition (as stated): Not specified — used consistently to label disconnector symbols in the document's legend
Equivalent term(s) (if stated): Not specified
Confidence: Medium
```
