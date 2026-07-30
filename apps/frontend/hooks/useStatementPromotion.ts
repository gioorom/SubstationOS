"use client";

/**
 * Whether one semantic statement is in the governed graph.
 *
 * Reads the projection and can trigger a promotion run. It decides
 * **nothing**: whether a statement is promotable is the backend's rule,
 * and a frontend that re-implemented it would be a second, quietly
 * diverging definition of governed knowledge.
 */

import { useCallback, useState } from "react";

import { describeError, type ErrorCopy } from "@/lib/api";
import type { StatementPromotion } from "@/lib/contracts";
import {
  createPromotion,
  readStatementPromotion,
} from "@/lib/resources/graph";

import { useResource } from "./useResource";

const COPY: ErrorCopy = {
  forbidden:
    "Il tuo ruolo non consente di promuovere conoscenza nel grafo governato.",
  network:
    "Impossibile leggere lo stato di promozione: il backend non risponde.",
};

export interface StatementPromotionState {
  promotion: StatementPromotion | null;
  loading: boolean;
  error: string | null;
  promoting: boolean;
  promoteError: string | null;
  promote: () => Promise<void>;
  reload: () => Promise<void>;
}

export function useStatementPromotion(
  documentId: number | undefined,
  statementKey: string | null,
): StatementPromotionState {
  const enabled = documentId !== undefined && statementKey !== null;

  const read = useCallback(
    (signal: AbortSignal) =>
      readStatementPromotion(
        documentId as number,
        statementKey as string,
        signal,
      ),
    [documentId, statementKey],
  );

  const resource = useResource<StatementPromotion>(read, {
    enabled,
    copy: COPY,
  });

  const [promoting, setPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  const { reload } = resource;

  const promote = useCallback(async () => {
    if (documentId === undefined || statementKey === null) {
      return;
    }

    setPromoting(true);
    setPromoteError(null);

    try {
      await createPromotion(documentId, statementKey);

      // The projection is what changed; re-read it rather than guessing
      // the outcome from the run's counters.
      await reload();
    } catch (caught) {
      setPromoteError(describeError(caught, COPY));

      throw caught;
    } finally {
      setPromoting(false);
    }
  }, [documentId, statementKey, reload]);

  return {
    promotion: resource.data,
    loading: resource.loading,
    error: resource.error,
    promoting,
    promoteError,
    promote,
    reload,
  };
}
