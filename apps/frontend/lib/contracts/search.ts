/**
 * `GET /projects/{id}/search` — finding what a project's documents say.
 *
 * These types mirror the backend's response exactly. Nothing here
 * mentions segments or canonical representations: a result names a
 * document, a position inside it, and the text that matched, and that
 * is the whole vocabulary the interface needs.
 */

/** Which kind of document a result came from. */
export const SEARCH_SOURCE_TYPES = ["pdf", "spreadsheet"] as const;

export type SearchSourceType = (typeof SEARCH_SOURCE_TYPES)[number];

/** Where a searched term sits inside the snippet shown to the reader. */
export interface SearchHighlight {
  start: number;
  end: number;
}

export interface SearchSnippet {
  /** The source text, exactly as the document has it. */
  text: string;
  highlights: SearchHighlight[];
  truncated_before: boolean;
  truncated_after: boolean;
}

/**
 * Where a match is inside its document.
 *
 * `determined` is false when the source recorded no position. Every
 * other field is then null, and the interface must say the position is
 * unknown rather than leave the reader to assume one.
 */
export interface SearchLocation {
  determined: boolean;
  page_number: number | null;
  worksheet_name: string | null;
  row_number: number | null;
  cell_reference: string | null;
}

export interface SearchMatch {
  location: SearchLocation;
  snippet: SearchSnippet;
}

export interface SearchDocumentResult {
  document_id: number;
  filename: string;
  source_type: SearchSourceType;
  /** The document version these matches were read from, when known. */
  content_checksum: string | null;
  matches: SearchMatch[];
}

/**
 * A term that matched nothing, and the designations the project does
 * contain that differ from it only by an IEC 81346 aspect prefix.
 *
 * Shown so an empty result can be understood. The search is never rerun
 * with them: `-Q1` and `Q1` are different designations.
 */
export interface SearchTermSuggestion {
  term: string;
  present_variants: string[];
}

export interface ProjectSearchResponse {
  project_id: number;
  /** What was typed, unchanged. */
  query: string;
  /** What was searched for once case and accents were folded. */
  terms: string[];
  total_matches: number;
  total_documents: number;
  documents: SearchDocumentResult[];
  suggestions: SearchTermSuggestion[];
}

export interface ProjectSearchQuery {
  q: string;
  limit?: number;
  offset?: number;
}

/** What the backend returns for a query that asked for nothing. */
export const EMPTY_SEARCH: ProjectSearchResponse = {
  project_id: 0,
  query: "",
  terms: [],
  total_matches: 0,
  total_documents: 0,
  documents: [],
  suggestions: [],
};
