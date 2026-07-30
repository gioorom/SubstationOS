"use client";

/**
 * The review state of one semantic statement.
 *
 * Reads the current decision and the history, and appends a judgement.
 * It computes **neither** the current decision nor whether an entry has
 * been superseded - both come from the backend, which derives them from
 * the ordered history. A frontend that decided either would be a second,
 * quietly diverging account of what the record says.
 *
 * The two reads settle independently, so a history that fails to load
 * leaves the current decision on screen. The distinction matters: an
 * engineer looking at a rejected statement needs to see the rejection
 * even if the timeline beneath it is unavailable.
 */

import { useCallback, useMemo, useState } from "react";

import { describeError, type ErrorCopy } from "@/lib/api";
import type {
  CurrentReview,
  ReviewDecision,
  ReviewHistoryEntry,
  ReviewReason,
} from "@/lib/contracts";
import {
  readCurrentReview,
  readReviewHistory,
  recordReview,
} from "@/lib/resources/review";

import { useResource } from "./useResource";

const HISTORY_PAGE_SIZE = 20;

const REVIEW_COPY: ErrorCopy = {
  forbidden:
    "Il tuo ruolo non consente di registrare revisioni ingegneristiche.",
  network:
    "Impossibile leggere lo stato di revisione: il backend non risponde.",
};

export interface StatementReviewState {
  /** `null` while loading, or when the read failed. */
  current: CurrentReview | null;
  history: ReviewHistoryEntry[];
  /** How many reviews exist in total, across every page. */
  historyTotal: number;
  hasMoreHistory: boolean;

  loading: boolean;
  /** The current decision could not be read. */
  error: string | null;
  /** The history could not be read; the current decision may still be. */
  historyError: string | null;

  submitting: boolean;
  submitError: string | null;
  /** True when the backend refused the submission for lack of permission. */
  forbidden: boolean;

  submit: (input: {
    decision: ReviewDecision;
    reason: ReviewReason;
    comment: string | null;
  }) => Promise<void>;
  reload: () => Promise<void>;
}

export function useStatementReview(
  documentId: number | undefined,
  statementKey: string | null,
): StatementReviewState {
  const enabled = documentId !== undefined && statementKey !== null;

  const readCurrent = useCallback(
    (signal: AbortSignal) =>
      readCurrentReview(
        documentId as number,
        statementKey as string,
        signal,
      ),
    [documentId, statementKey],
  );

  const readHistory = useCallback(
    (signal: AbortSignal) =>
      readReviewHistory(
        documentId as number,
        statementKey as string,
        { page: 1, page_size: HISTORY_PAGE_SIZE },
        signal,
      ),
    [documentId, statementKey],
  );

  const currentResource = useResource<CurrentReview>(readCurrent, {
    enabled,
    copy: REVIEW_COPY,
  });

  const historyResource = useResource(readHistory, {
    enabled,
    copy: REVIEW_COPY,
  });

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const reloadCurrent = currentResource.reload;
  const reloadHistory = historyResource.reload;

  const reload = useCallback(async () => {
    await Promise.all([reloadCurrent(), reloadHistory()]);
  }, [reloadCurrent, reloadHistory]);

  const submit = useCallback(
    async (input: {
      decision: ReviewDecision;
      reason: ReviewReason;
      comment: string | null;
    }) => {
      if (documentId === undefined || statementKey === null) {
        return;
      }

      setSubmitting(true);
      setSubmitError(null);
      setForbidden(false);

      try {
        await recordReview(documentId, statementKey, input);

        // Both projections change: a new current decision, and one more
        // entry in the history that now supersedes the previous one.
        await reload();
      } catch (caught) {
        setForbidden(
          typeof caught === "object" &&
            caught !== null &&
            (caught as { status?: number }).status === 403,
        );
        setSubmitError(describeError(caught, REVIEW_COPY));

        throw caught;
      } finally {
        setSubmitting(false);
      }
    },
    [documentId, statementKey, reload],
  );

  const history = useMemo(
    () => historyResource.data?.items ?? [],
    [historyResource.data],
  );

  return {
    current: currentResource.data,
    history,
    historyTotal: historyResource.data?.pagination.total ?? 0,
    hasMoreHistory: historyResource.data?.pagination.has_next ?? false,
    loading: currentResource.loading,
    error: currentResource.error,
    historyError: historyResource.error,
    submitting,
    submitError,
    forbidden,
    submit,
    reload,
  };
}
