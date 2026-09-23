"use client";

import { useCallback, useEffect, useState } from "react";

import { describeError, isCancellation } from "@/lib/api";
import type { ErrorCopy } from "@/lib/api";
import type {
  ProjectSearchResponse,
  SearchDocumentResult,
} from "@/lib/contracts";
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

/**
 * How many matches one request asks for.
 *
 * The backend refuses more than fifty. A real corpus answers a common
 * term with thousands of matches concentrated in whichever document
 * sorts first, so one page is rarely the whole answer - which is why
 * further pages can be fetched and merged rather than left
 * unreachable.
 */
export const SEARCH_PAGE_SIZE = 50;

/**
 * Everything fetched beyond the first page, and what it belongs to.
 *
 * ``answers`` identifies **both** the project and the query. Keying on
 * the query alone would let a second page loaded for one project be
 * merged into the results of another that happened to be searched for
 * the same word - one project's documents listed under another's
 * search, which is the one thing this feature promises cannot happen.
 */
interface FurtherPages {
  answers: string;
  documents: SearchDocumentResult[];
  count: number;
}

const NOTHING_FURTHER: FurtherPages = {
  answers: "",
  documents: [],
  count: 0,
};

/** What a cached page answers: a project and a query, never one alone. */
function answerKey(
  projectId: number | undefined,
  query: string,
): string {
  return projectId === undefined
    ? ""
    : `${projectId}:${query.length}:${query}`;
}

function countMatches(documents: SearchDocumentResult[]): number {
  return documents.reduce(
    (total, document) => total + document.matches.length,
    0,
  );
}

/**
 * Merge a further page into what is already on screen.
 *
 * Results arrive grouped by document and ordered by it, so a document
 * can straddle a page boundary. Its matches are appended to the group
 * already shown instead of starting a second group for the same
 * document, which would read as two documents with the same name.
 */
function mergeDocuments(
  shown: SearchDocumentResult[],
  next: SearchDocumentResult[],
): SearchDocumentResult[] {
  const merged = shown.map((document) => ({ ...document }));

  for (const document of next) {
    const existing = merged.find(
      (candidate) => candidate.document_id === document.document_id,
    );

    if (existing === undefined) {
      merged.push({ ...document });
      continue;
    }

    existing.matches = [...existing.matches, ...document.matches];
  }

  return merged;
}

export interface ProjectSearchOptions {
  pageSize?: number;
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
  const pageSize = options.pageSize ?? SEARCH_PAGE_SIZE;
  const trimmed = query.trim();

  const [submitted, setSubmitted] = useState("");
  const [further, setFurther] = useState<FurtherPages>(NOTHING_FURTHER);
  const [loadingMore, setLoadingMore] = useState(false);

  // Keyed like the pages themselves, so a failure to load more is
  // forgotten the moment the engineer asks something else. Held
  // unkeyed it would survive every later query, and because the panel
  // hides the results *and* the retry control whenever an error is
  // present, one failed click would blank search for the session.
  const [moreFailure, setMoreFailure] = useState<{
    answers: string;
    message: string;
  } | null>(null);

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
        { q: submitted, limit: pageSize, offset: 0 },
        signal,
      );
    },
    [projectId, submitted, pageSize],
  );

  const { data, loading, refreshing, error } = useResource(read, {
    enabled: projectId !== undefined,
    copy: SEARCH_COPY,
  });

  const firstPage: ProjectSearchResponse = data ?? EMPTY_SEARCH;

  const answers = answerKey(projectId, submitted);

  // Pages fetched for an earlier question are ignored rather than
  // cleared, so no effect has to write state to forget them.
  const extra = further.answers === answers ? further : NOTHING_FURTHER;

  const moreError =
    moreFailure?.answers === answers ? moreFailure.message : null;

  const results: ProjectSearchResponse =
    extra.documents.length > 0
      ? {
          ...firstPage,
          documents: mergeDocuments(firstPage.documents, extra.documents),
        }
      : firstPage;

  const shown = countMatches(firstPage.documents) + extra.count;

  const loadMore = useCallback(async () => {
    if (projectId === undefined || submitted === "" || loadingMore) {
      return;
    }

    setLoadingMore(true);
    setMoreFailure(null);

    try {
      const page = await searchProjectDocuments(projectId, {
        q: submitted,
        limit: pageSize,
        offset: shown,
      });

      setFurther((previous) => {
        const base =
          previous.answers === answers ? previous : NOTHING_FURTHER;

        return {
          answers,
          documents: mergeDocuments(base.documents, page.documents),
          count: base.count + countMatches(page.documents),
        };
      });
    } catch (failure: unknown) {
      if (!isCancellation(failure)) {
        setMoreFailure({
          answers,
          message:
            describeError(failure, SEARCH_COPY) ??
            SEARCH_COPY.network ??
            "Ricerca non riuscita.",
        });
      }
    } finally {
      setLoadingMore(false);
    }
  }, [projectId, submitted, pageSize, shown, loadingMore, answers]);

  return {
    results,
    /** The query the results on screen belong to. */
    submitted,
    /** True while a query the reader typed has not been sent yet. */
    pending: trimmed !== submitted,
    searching: loading || refreshing,
    loadingMore,
    /** How many matches are on screen, of `results.total_matches`. */
    shown,
    hasMore: shown > 0 && shown < results.total_matches,
    loadMore,
    error: error ?? moreError,
  };
}
