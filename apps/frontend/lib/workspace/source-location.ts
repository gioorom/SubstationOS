/**
 * Where an artefact came from in the source document.
 *
 * **Every field below is a transcription of a field the backend
 * supplied.** Nothing here is measured, guessed or interpolated, and a
 * coordinate the backend does not record is `null` rather than a
 * plausible number - a viewer that draws an approximate rectangle over a
 * wiring diagram is worse than one that draws none, because the engineer
 * cannot tell the difference.
 *
 * The backend's own source coordinates, and where each comes from:
 *
 * | Field | Source |
 * |---|---|
 * | `page_number` | `EvidenceProvenance.page_number` (1-based) |
 * | `section_index` | `EvidenceProvenance.section_index` - one page |
 * | `paragraph_index` | `EvidenceProvenance.paragraph_index` - one PDF block |
 * | `block_reading_order` | `EvidenceProvenance.block_reading_order` |
 * | `line_index` | `EvidenceProvenance.line_index` |
 * | `token_start` / `token_end` | `EvidenceProvenance.token_*` |
 * | `spans` | `EvidenceProvenance.spans` - span number + character range |
 * | `excerpt` | `EvidenceProvenance.source_text` - the canonical line |
 *
 * There is deliberately **no `bounding_box` field**. Evidence does not
 * carry geometry; the canonical representation does, and the two are
 * joined by the explicit `(page_number, block_reading_order,
 * span_reading_order)` identity through `resolveSpanBoxes`. A location
 * whose page has not been read has no box, and says so.
 */

import type {
  BoundingBox,
  CanonicalPdfPage,
  EvidenceProvenance,
  EvidenceReference,
  FactDiagnostic,
  FactSupport,
  SpanReference,
} from "@/lib/contracts";

export interface SourceLocation {
  document_id: number;
  /** 1-based, as the document itself numbers its pages. */
  page_number: number;
  paragraph_index: number;
  line_index: number;
  /** `null` on locations the backend records without one. */
  section_index: number | null;
  block_reading_order: number | null;
  token_start: number | null;
  token_end: number | null;
  /** Empty when the artefact cites no span - never a fabricated one. */
  spans: readonly SpanReference[];
  /** The canonical line, verbatim. `null` where none was supplied. */
  excerpt: string | null;
}

/** The full location of an observation: every field the backend has. */
export function locationOfProvenance(
  documentId: number,
  provenance: EvidenceProvenance,
): SourceLocation {
  return {
    document_id: documentId,
    page_number: provenance.page_number,
    paragraph_index: provenance.paragraph_index,
    line_index: provenance.line_index,
    section_index: provenance.section_index,
    block_reading_order: provenance.block_reading_order,
    token_start: provenance.token_start,
    token_end: provenance.token_end,
    spans: provenance.spans,
    excerpt: provenance.source_text,
  };
}

/**
 * The location an entity's or a fact's support reference carries.
 *
 * Both shapes repeat page, paragraph, line and tokens so an artefact can
 * be placed without a second lookup, and neither repeats the spans or
 * the source line. Those stay `null`/empty here: the authoritative
 * record is the evidence, which the Workspace indexes by key anyway.
 */
export function locationOfReference(
  documentId: number,
  reference: EvidenceReference | FactSupport,
): SourceLocation {
  return {
    document_id: documentId,
    page_number: reference.page_number,
    paragraph_index: reference.paragraph_index,
    line_index: reference.line_index,
    section_index: null,
    block_reading_order: null,
    token_start: reference.token_start,
    token_end: reference.token_end,
    spans: [],
    excerpt: null,
  };
}

/**
 * The line a declined fact construction happened on.
 *
 * A diagnostic names a line and no tokens - which token was the subject
 * is exactly what could not be decided - so the location stops at the
 * line. That is a limit of the artefact, faithfully reported.
 */
export function locationOfFactDiagnostic(
  documentId: number,
  diagnostic: FactDiagnostic,
): SourceLocation {
  return {
    document_id: documentId,
    page_number: diagnostic.page_number,
    paragraph_index: diagnostic.paragraph_index,
    line_index: diagnostic.line_index,
    section_index: null,
    block_reading_order: null,
    token_start: null,
    token_end: null,
    spans: [],
    excerpt: null,
  };
}

/** `p. 3 · par. 12 · riga 4` - the same reading in every panel. */
export function describeLocation(location: SourceLocation): string {
  return [
    `p. ${location.page_number}`,
    `par. ${location.paragraph_index}`,
    `riga ${location.line_index}`,
  ].join(" · ");
}

/**
 * The rectangles the parser recorded for the spans this location cites.
 *
 * The join is by explicit identity - block `block_reading_order`, span
 * `span_reading_order`, on `page` - and never by text. A span the page
 * does not contain contributes nothing: the result is short, not
 * approximate.
 *
 * Returns an empty array when the location cites no span, when its
 * `block_reading_order` is unknown, or when the page is not the one the
 * location names. Callers render highlights only for what comes back.
 */
export function resolveSpanBoxes(
  page: CanonicalPdfPage | null,
  location: SourceLocation,
): BoundingBox[] {
  if (
    page === null ||
    page.page_number !== location.page_number ||
    location.block_reading_order === null ||
    location.spans.length === 0
  ) {
    return [];
  }

  const block = page.blocks.find(
    (candidate) => candidate.reading_order === location.block_reading_order,
  );

  if (block === undefined) {
    return [];
  }

  const boxes: BoundingBox[] = [];

  for (const reference of location.spans) {
    const span = block.spans.find(
      (candidate) =>
        candidate.reading_order === reference.span_reading_order,
    );

    if (span !== undefined) {
      boxes.push(span.bounding_box);
    }
  }

  return boxes;
}
