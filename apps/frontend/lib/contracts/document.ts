/**
 * The Document contract, transcribed from the backend.
 *
 * Source of truth: `app/models/document.py` (`DocumentFormat`,
 * `DocumentCategory`), `app/domain/project/project_document_scope.py`
 * (`DocumentScope`) and the `POST /documents/upload` response built in
 * `app/routers/documents.py`.
 *
 * Milestone 30.1.3 replaced the ORM-shaped rows this file used to
 * describe with governed schemas. Two consequences the UI must respect:
 *
 * - **`file_path` is gone.** Where a document is stored is private
 *   backend state; the frontend has no field for it and no reason to.
 * - Lists are `PagedResponse<DocumentSummary>`, filtered and sorted by
 *   the server. Client-side filtering of the whole registry is no longer
 *   correct - it would filter one page.
 */

import type {
  PagedResponse,
  PageRequest,
  SortDirection,
} from "./pagination";

export const DOCUMENT_FORMATS = [
  "pdf",
  "dwg",
  "dxf",
  "model_3d",
  "xlsx",
  "docx",
  "image",
  "other",
] as const;

export type DocumentFormat = (typeof DOCUMENT_FORMATS)[number];

/** `other` means *unclassified*, not "examined and found unusable". */
export const DOCUMENT_FORMAT_LABELS: Record<DocumentFormat, string> = {
  pdf: "PDF",
  dwg: "DWG",
  dxf: "DXF",
  model_3d: "Modello 3D",
  xlsx: "XLSX",
  docx: "DOCX",
  image: "Immagine",
  other: "Non classificato",
};

export const DOCUMENT_CATEGORIES = [
  "functional_schematic",
  "wiring_terminal",
  "general_technical",
  "cable_list",
  "relay_settings",
  "commissioning_report",
  "other",
] as const;

export type DocumentCategory = (typeof DOCUMENT_CATEGORIES)[number];

export const DOCUMENT_CATEGORY_LABELS: Record<DocumentCategory, string> = {
  functional_schematic: "Schema funzionale",
  wiring_terminal: "Schema morsettiere",
  general_technical: "Documentazione tecnica",
  cable_list: "Elenco cavi",
  relay_settings: "Tarature relè",
  commissioning_report: "Report di messa in servizio",
  other: "Altro",
};

/**
 * A document belongs to exactly one Project, or to the Canonical
 * Library - never both, never neither (ADR-0005).
 */
export const DOCUMENT_SCOPES = ["project", "canonical_library"] as const;

export type DocumentScope = (typeof DOCUMENT_SCOPES)[number];

/** What a list or a document picker needs. Deliberately small. */
export interface DocumentSummary {
  id: number;
  project_id: number | null;
  /**
   * The one field that looks like a detail and is not: a registry table
   * spanning several projects has to say which project a row belongs to,
   * and a numeric id tells a human nothing.
   */
  project_name: string;
  filename: string;
  file_format: DocumentFormat;
  category: DocumentCategory;
  revision: string;
  scope: DocumentScope;
  uploaded_at: string;
}

/**
 * One document in full.
 *
 * `content_checksum` is public on purpose: the deterministic pipeline
 * binds every artefact to it. It identifies *the bytes*, never where
 * they are. `content_available` answers "can I download this?" honestly -
 * it is `false` for a document whose bytes have gone missing under a
 * registry row that remains.
 */
export interface DocumentDetail extends DocumentSummary {
  content_checksum: string | null;
  checksum_algorithm: string | null;
  size_bytes: number | null;
  content_available: boolean;
  ingestion_state: string | null;
  ingestion_outcome: string | null;
}

export type DocumentListResponse = PagedResponse<DocumentSummary>;

export const DOCUMENT_SORT_FIELDS = [
  "uploaded_at",
  "filename",
  "revision",
  "document_format",
] as const;

export type DocumentSortField = (typeof DOCUMENT_SORT_FIELDS)[number];

export const DOCUMENT_SORT_LABELS: Record<DocumentSortField, string> = {
  uploaded_at: "Data di caricamento",
  filename: "Nome file",
  revision: "Revisione",
  document_format: "Formato",
};

/** The server-side query. Every field is optional; all combine as AND. */
export interface DocumentQuery extends PageRequest {
  project_id?: number;
  scope?: DocumentScope;
  file_format?: DocumentFormat;
  category?: DocumentCategory;
  /**
   * Case-insensitive partial match over **filename and project name**,
   * trimmed at both ends. Internal whitespace is significant.
   */
  search?: string;
  sort_by?: DocumentSortField;
  direction?: SortDirection;
}

/**
 * The Knowledge Graph outcome the upload endpoint reports beside the
 * stored document.
 *
 * A pipeline failure never fails the upload - the document is stored
 * whatever the graph made of it - so this block is informational and its
 * `status` is a legacy vocabulary preserved by the backend.
 */
export const UPLOAD_PIPELINE_STATUSES = [
  "completed",
  "skipped",
  "failed",
  "no_text",
  "unsupported_file_type",
] as const;

export type UploadPipelineStatus =
  (typeof UPLOAD_PIPELINE_STATUSES)[number];

export interface UploadPipelineFailure {
  /** The pipeline stage that stopped, e.g. `canonical_representation`. */
  stage: string;
  /** That stage's own typed failure code. */
  code: string;
  message: string;
}

export interface UploadPipelineResult {
  status: UploadPipelineStatus;
  entities_found: number;
  failure: UploadPipelineFailure | null;
}

export interface DocumentContentDownload {
  blob: Blob;
  /** From the response's Content-Disposition, already sanitised server-side. */
  filename: string;
}

/**
 * The result of `POST /documents/upload`.
 *
 * There is no `reused` field: upload does not deduplicate. Milestone
 * 25.2 established that an identical checksum is recorded and nothing is
 * concluded from it, so reporting `reused: false` on every response
 * would imply a comparison that never happens.
 */
export interface DocumentUploadResponse {
  document: DocumentDetail;
  scope: DocumentScope;
  analysis: UploadPipelineResult;
  /** Non-fatal observations: an unclassified format, a sanitised name. */
  warnings: string[];
}

export interface UploadDocumentRequest {
  file: File;
  /** Required for scope `project`; must be absent for the library. */
  projectId?: number;
  scope?: DocumentScope;
}

export const UPLOAD_PIPELINE_LABELS: Record<
  UploadPipelineStatus,
  string
> = {
  completed: "Analisi completata",
  skipped: "Analisi non applicabile",
  failed: "Analisi non riuscita",
  no_text: "Nessun testo estraibile",
  unsupported_file_type: "Formato non supportato dall'analisi",
};
