"use client";

import { useCallback, useEffect, useState } from "react";

import type { ErrorCopy } from "@/lib/api";
import type { ProjectSearchResponse } from "@/lib/contracts";
import { EMPTY_SEARCH } from "@/lib/contracts";
import { searchProjectDocuments } from "@/lib/resources/search";

import { useResource } from "./useResource";

const SEARCH_COPY: ErrorCopy = {
  notFound: "Il progetto richiesto non esiste.",
  network:
    "Impossibile eseguire la ricerca: il backend SubstationOS non risponde.",
};

/**
 * How long the interface waits after the last keystroke before asking.
 *
 * Long enough that typing a designation is one request rather than
 * five, short enough that the answer still feels like a consequence of
 * typing.
 */
export const SEARCH_DEBOUNCE_MS = 300;

export interface ProjectSearchOptions {
  limit?: number;
}

/**
 * Searching one project's documents as the engineer types.
 *
 * The submitted query is kept separately from what is in the box, so a
 * result on screen always belongs to a query that was actually sent -
 * never to the half-typed one the reader is still working on.
 *
 * An empty box performs no request at all and shows nothing. There is
 * no state in which this hook asks the backend for everything.
 */
export function useProjectSearch(
  projectId: number | undefined,
  query: string,
  options: ProjectSearchOptions = {},
) {
  const limit = options.limit;
  const trimmed = query.trim();

  const [submitted, setSubmitted] = useState("");

  useEffect(() => {
    if (trimmed === submitted) {
      return;
    }

    const timer = setTimeout(
      () => setSubmitted(trimmed),
      SEARCH_DEBOUNCE_MS,
    );

    return () => clearTimeout(timer);
  }, [trimmed, submitted]);

  const read = useCallback(
    (signal: AbortSignal) => {
      if (projectId === undefined || submitted === "") {
        return Promise.resolve(EMPTY_SEARCH);
      }

      return searchProjectDocuments(
        projectId,
        { q: submitted, limit },
        signal,
      );
    },
    [projectId, submitted, limit],
  );

  const { data, loading, refreshing, error, reload } = useResource(
    read,
    { enabled: projectId !== undefined, copy: SEARCH_COPY },
  );

  const results: ProjectSearchResponse = data ?? EMPTY_SEARCH;

  return {
    results,
    /** The query the results on screen belong to. */
    submitted,
    /** True while a query the reader typed has not been sent yet. */
    pending: trimmed !== submitted,
    searching: loading || refreshing,
    error,
    reload,
  };
}
