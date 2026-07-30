/**
 * `GET|POST /documents` and the governed download.
 *
 * Since Milestone 30.1.3 the backend owns paging, filtering, search and
 * sorting, and exposes a per-document read and a download. Nothing here
 * filters a list client-side any more - that would filter one page.
 */

import { apiClient, request } from "@/lib/api";
import { PIPELINE_TIMEOUT_MS } from "@/lib/api/client";
import type {
  DocumentContentDownload,
  DocumentDetail,
  DocumentListResponse,
  DocumentQuery,
  DocumentScope,
  DocumentUploadResponse,
} from "@/lib/contracts";
import { env } from "@/config/env";

export function listDocuments(
  query: DocumentQuery = {},
  signal?: AbortSignal,
): Promise<DocumentListResponse> {
  return apiClient.get<DocumentListResponse>("/documents/", {
    query: {
      page: query.page,
      page_size: query.page_size,
      project_id: query.project_id,
      scope: query.scope,
      file_format: query.file_format,
      category: query.category,
      search: query.search?.trim() || undefined,
      sort_by: query.sort_by,
      direction: query.direction,
    },
    signal,
    retries: 1,
  });
}

/** `GET /documents/{id}` - introduced in Milestone 30.1.3. */
export function getDocument(
  documentId: number,
  signal?: AbortSignal,
): Promise<DocumentDetail> {
  return apiClient.get<DocumentDetail>(`/documents/${documentId}`, {
    signal,
    retries: 1,
  });
}

export interface UploadDocumentOptions {
  file: File;
  projectId?: number;
  scope?: DocumentScope;
  signal?: AbortSignal;
}

/**
 * Uploads one document.
 *
 * Scope rules, enforced by the backend with 422: `project` requires a
 * `project_id`; `canonical_library` refuses one. 404 when the project
 * does not exist, 409 when its lifecycle state makes it read-only.
 */
export function uploadDocument(
  options: UploadDocumentOptions,
): Promise<DocumentUploadResponse> {
  const form = new FormData();

  form.append("file", options.file);

  if (options.projectId !== undefined) {
    form.append("project_id", String(options.projectId));
  }

  if (options.scope !== undefined) {
    form.append("scope", options.scope);
  }

  return apiClient.post<DocumentUploadResponse>("/documents/upload", {
    body: form,
    signal: options.signal,
    timeoutMs: PIPELINE_TIMEOUT_MS,
  });
}

/**
 * `GET /documents/{id}/content` - the original bytes.
 *
 * The only input is the document id: the frontend never knows, sends or
 * receives a storage location. The filename comes from the response's
 * `Content-Disposition`, which the backend already sanitised.
 *
 * This is the one read that does not go through `apiClient`'s JSON path,
 * because the response is not JSON. It still goes through the same
 * module and the same base URL - `request` is not bypassed, it simply
 * has no shape to parse here.
 */
export async function downloadDocumentContent(
  documentId: number,
  signal?: AbortSignal,
): Promise<DocumentContentDownload> {
  const response = await request<Response>(
    `/documents/${documentId}/content`,
    { signal, raw: true, timeoutMs: PIPELINE_TIMEOUT_MS },
  );

  return {
    blob: await response.blob(),
    filename: filenameFrom(response.headers.get("content-disposition")),
  };
}

const FALLBACK_DOWNLOAD_NAME = "documento";

function filenameFrom(disposition: string | null): string {
  if (disposition === null) {
    return FALLBACK_DOWNLOAD_NAME;
  }

  const quoted = /filename="([^"]*)"/.exec(disposition);

  return quoted?.[1] || FALLBACK_DOWNLOAD_NAME;
}

/** The absolute URL of a document's content, for an `<a download>`. */
export function documentContentUrl(documentId: number): string {
  return `${env.apiBaseUrl}/documents/${documentId}/content`;
}
