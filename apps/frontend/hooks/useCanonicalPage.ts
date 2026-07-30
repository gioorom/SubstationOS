"use client";

/**
 * One page of the canonical representation, read when it is displayed.
 *
 * The page map needs the spans and bounding boxes of the page on screen
 * and of no other. Reading the whole representation would transfer every
 * page of a drawing set to render one, so the Workspace reads pages
 * lazily through
 * `GET /documents/{id}/canonical-representation/pages/{page_number}`,
 * and `useResource` cancels the read for a page the engineer has already
 * navigated away from.
 *
 * `null` with no error means the page is not in the representation -
 * either the document was never canonicalised, or the parser recorded no
 * such page. Neither is a failure worth interrupting an engineer with.
 */

import { useCallback } from "react";

import type { ErrorCopy } from "@/lib/api";
import type { CanonicalPdfPage } from "@/lib/contracts";
import { readCanonicalPage } from "@/lib/resources/pipeline";

import { useResource } from "./useResource";

const PAGE_COPY: ErrorCopy = {
  network:
    "Impossibile leggere la pagina canonica: il backend non risponde.",
};

export function useCanonicalPage(
  documentId: number | undefined,
  pageNumber: number | null,
) {
  const read = useCallback(
    (signal: AbortSignal) =>
      readCanonicalPage(
        documentId as number,
        pageNumber as number,
        signal,
      ),
    [documentId, pageNumber],
  );

  const resource = useResource<CanonicalPdfPage | null>(read, {
    enabled: documentId !== undefined && pageNumber !== null,
    copy: PAGE_COPY,
  });

  return {
    page: resource.data,
    loading: resource.loading,
    error: resource.error,
  };
}
