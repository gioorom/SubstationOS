"use client";

/**
 * The current decision for every reviewed statement in one document.
 *
 * **One request for the whole screen.** Badging a list of statements with
 * one request per row would be the request fan-out EPIC 30.2 refused to
 * build for support chains, arriving through a different door.
 *
 * Statements nobody has reviewed are simply absent from the response; the
 * map returns `undefined` for them, which the badge renders as "mai
 * revisionato" - a state, not a decision.
 */

import { useCallback, useMemo } from "react";

import type { ErrorCopy } from "@/lib/api";
import type { CurrentReview, DocumentReviewSummaryResponse } from "@/lib/contracts";
import { readDocumentReviews } from "@/lib/resources/review";

import { useResource } from "./useResource";

const COPY: ErrorCopy = {
  network:
    "Impossibile leggere lo stato di revisione: il backend non risponde.",
};

export interface DocumentReviewState {
  /** Statement key -> its current decision. Absent means never reviewed. */
  byStatement: ReadonlyMap<string, CurrentReview>;
  loading: boolean;
  /** Non-null when the summary failed; the Workspace stays usable. */
  error: string | null;
  reload: () => Promise<void>;
}

export function useDocumentReviews(
  documentId: number | undefined,
): DocumentReviewState {
  const read = useCallback(
    (signal: AbortSignal) =>
      readDocumentReviews(documentId as number, signal),
    [documentId],
  );

  const resource = useResource<DocumentReviewSummaryResponse>(read, {
    enabled: documentId !== undefined,
    copy: COPY,
  });

  const byStatement = useMemo(() => {
    const index = new Map<string, CurrentReview>();

    for (const item of resource.data?.items ?? []) {
      index.set(item.target_key, item);
    }

    return index;
  }, [resource.data]);

  return {
    byStatement,
    loading: resource.loading,
    error: resource.error,
    reload: resource.reload,
  };
}
