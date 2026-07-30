"use client";

import { useCallback, useMemo, useState } from "react";

import type { ErrorCopy } from "@/lib/api";
import type {
  DocumentDetail,
  DocumentListResponse,
  DocumentQuery,
  DocumentScope,
  DocumentUploadResponse,
} from "@/lib/contracts";
import { EMPTY_PAGE } from "@/lib/contracts";
import {
  downloadDocumentContent,
  getDocument,
  listDocuments,
  uploadDocument,
} from "@/lib/resources/documents";

import { useMutation, useResource } from "./useResource";

export interface UploadInput {
  file: File;
  projectId?: number;
  scope?: DocumentScope;
}

const LIST_COPY: ErrorCopy = {
  network:
    "Impossibile caricare i documenti: il backend SubstationOS non risponde.",
};

const DETAIL_COPY: ErrorCopy = {
  notFound: "Il documento richiesto non esiste.",
};

const UPLOAD_COPY: ErrorCopy = {
  validation:
    "Il caricamento è stato rifiutato: verifica progetto e ambito del documento.",
  notFound: "Il progetto selezionato non esiste.",
  conflict:
    "Il progetto è archiviato o eliminato: non accetta nuovi documenti.",
};

const DOWNLOAD_COPY: ErrorCopy = {
  notFound:
    "Il documento non è più disponibile: il file archiviato non esiste.",
  server: "Il file esiste ma non è leggibile dal backend.",
};

/**
 * A page of the document registry.
 *
 * **The query goes to the server.** Since Milestone 30.1.3 filtering,
 * search, sorting and paging are all backend concerns; this hook sends
 * the query and renders the page it gets back. It never filters the
 * result, because the result is one page and filtering it would silently
 * hide matches on every other.
 */
export function useDocuments(query: DocumentQuery = {}) {
  const {
    page,
    page_size,
    project_id,
    scope,
    file_format,
    category,
    search,
    sort_by,
    direction,
  } = query;

  const read = useCallback(
    (signal: AbortSignal) =>
      listDocuments(
        {
          page,
          page_size,
          project_id,
          scope,
          file_format,
          category,
          search,
          sort_by,
          direction,
        },
        signal,
      ),
    [
      page,
      page_size,
      project_id,
      scope,
      file_format,
      category,
      search,
      sort_by,
      direction,
    ],
  );

  const resource = useResource<DocumentListResponse>(read, {
    copy: LIST_COPY,
  });

  const perform = useCallback(
    (input: UploadInput, signal: AbortSignal) =>
      uploadDocument({
        file: input.file,
        projectId: input.projectId,
        scope: input.scope,
        signal,
      }),
    [],
  );

  const upload = useMutation<UploadInput, DocumentUploadResponse>(perform, {
    copy: UPLOAD_COPY,
  });

  const { reload } = resource;
  const { run: runUpload } = upload;

  const add = useCallback(
    async (input: UploadInput) => {
      const uploaded = await runUpload(input);

      // Re-read rather than splice: the new document's position depends
      // on the active sort and filters, which only the server knows.
      await reload();

      return uploaded;
    },
    [runUpload, reload],
  );

  return {
    documents: resource.data?.items ?? [],
    pagination: resource.data?.pagination ?? EMPTY_PAGE,
    loading: resource.loading,
    refreshing: resource.refreshing,
    error: resource.error,
    reload: resource.reload,
    upload: add,
    uploading: upload.pending,
    uploadError: upload.error,
    uploadFailure: upload.failure,
    resetUploadError: upload.reset,
  };
}

/** One document, read from `GET /documents/{id}`. */
export function useDocument(documentId: number | undefined) {
  const read = useCallback(
    (signal: AbortSignal) => getDocument(documentId as number, signal),
    [documentId],
  );

  const resource = useResource<DocumentDetail>(read, {
    enabled: documentId !== undefined,
    copy: DETAIL_COPY,
  });

  const perform = useCallback(
    (_: void, signal: AbortSignal) =>
      downloadDocumentContent(documentId as number, signal),
    [documentId],
  );

  const download = useMutation(perform, { copy: DOWNLOAD_COPY });

  const { run: runDownload } = download;

  /**
   * Fetches the bytes through the governed endpoint and hands them to the
   * browser. The URL is never constructed in a component, and the
   * filename is the one the backend sanitised.
   */
  const save = useCallback(async () => {
    const content = await runDownload();

    const url = URL.createObjectURL(content.blob);

    try {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = content.filename;
      anchor.click();
    } finally {
      URL.revokeObjectURL(url);
    }

    return content;
  }, [runDownload]);

  return {
    document: resource.data,
    loading: resource.loading,
    error: resource.error,
    failure: resource.failure,
    reload: resource.reload,
    download: save,
    downloading: download.pending,
    downloadError: download.error,
  };
}

/**
 * Page state for a registry view: the query, and the setters that reset
 * to page 1 whenever a filter changes.
 *
 * Resetting matters - changing a filter while on page 4 of the old
 * result set would show an empty page and look like "no matches".
 */
export function useDocumentQuery(initial: DocumentQuery = {}) {
  const [query, setQuery] = useState<DocumentQuery>({
    page: 1,
    ...initial,
  });

  const setFilter = useCallback(
    (patch: Partial<DocumentQuery>) => {
      setQuery((current) => ({ ...current, ...patch, page: 1 }));
    },
    [],
  );

  const setPage = useCallback((page: number) => {
    setQuery((current) => ({ ...current, page }));
  }, []);

  const hasFilters = useMemo(
    () =>
      Boolean(
        query.search ||
          query.scope ||
          query.file_format ||
          query.category,
      ),
    [query.search, query.scope, query.file_format, query.category],
  );

  const reset = useCallback(() => {
    setQuery((current) => ({
      page: 1,
      page_size: current.page_size,
      project_id: current.project_id,
      sort_by: current.sort_by,
      direction: current.direction,
    }));
  }, []);

  return { query, setFilter, setPage, reset, hasFilters };
}
