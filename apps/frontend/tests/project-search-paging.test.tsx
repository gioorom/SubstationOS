/**
 * `useProjectSearch`, which had no tests at all.
 *
 * The hook holds the state that survives between requests - the pages
 * fetched beyond the first, and the failure of a fetch. Both were keyed
 * wrongly when this file was written, and neither could be caught
 * through the panel, which only ever sees finished props. Two of the
 * defects pinned here were reported as blockers by an independent bug
 * hunt while every existing test stayed green.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useProjectSearch } from "@/hooks/useProjectSearch";
import type {
  ProjectSearchResponse,
  SearchDocumentResult,
} from "@/lib/contracts";

const BASE = "http://localhost:8000";

function aDocument(
  id: number,
  matches: number,
  filename = `doc-${id}.pdf`,
): SearchDocumentResult {
  return {
    document_id: id,
    filename,
    source_type: "pdf",
    content_checksum: "a".repeat(64),
    matches: Array.from({ length: matches }, (_, index) => ({
      location: {
        determined: true,
        page_number: index + 1,
        worksheet_name: null,
        row_number: null,
        cell_reference: null,
      },
      snippet: {
        text: `riga ${index}`,
        highlights: [],
        truncated_before: false,
        truncated_after: false,
      },
    })),
  };
}

function aPage(
  documents: SearchDocumentResult[],
  total: number,
): ProjectSearchResponse {
  return {
    project_id: 1,
    query: "MT",
    terms: ["mt"],
    total_matches: total,
    total_documents: 8,
    documents,
    suggestions: [],
  };
}

interface Route {
  body?: ProjectSearchResponse;
  fail?: boolean;
}

/** Answers each request in turn; the last route repeats. */
function stub(routes: Route[]) {
  const calls: string[] = [];
  let index = 0;

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input));

      const route = routes[Math.min(index, routes.length - 1)];
      index += 1;

      if (route.fail === true) {
        throw new TypeError("Failed to fetch");
      }

      return new Response(JSON.stringify(route.body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );

  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("reaching further pages", () => {
  it("asks for the next page from where the last one ended", async () => {
    const calls = stub([
      { body: aPage([aDocument(7, 50)], 200) },
      { body: aPage([aDocument(8, 50)], 200) },
    ]);

    const { result } = renderHook(() =>
      useProjectSearch(1, "MT", { pageSize: 50 }),
    );

    await waitFor(() => expect(result.current.shown).toBe(50));
    expect(result.current.hasMore).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });

    expect(calls[calls.length - 1]).toContain("offset=50");
    expect(result.current.shown).toBe(100);
  });

  it("appends to a document already shown rather than repeating it", async () => {
    stub([
      { body: aPage([aDocument(7, 50)], 120) },
      { body: aPage([aDocument(7, 10), aDocument(8, 40)], 120) },
    ]);

    const { result } = renderHook(() =>
      useProjectSearch(1, "MT", { pageSize: 50 }),
    );

    await waitFor(() => expect(result.current.shown).toBe(50));

    await act(async () => {
      await result.current.loadMore();
    });

    const documents = result.current.results.documents;

    expect(documents.map((d) => d.document_id)).toEqual([7, 8]);
    expect(documents[0].matches).toHaveLength(60);
    expect(documents[1].matches).toHaveLength(40);
  });

  it("counts exactly what it renders", async () => {
    stub([
      { body: aPage([aDocument(7, 50)], 120) },
      { body: aPage([aDocument(8, 30)], 120) },
    ]);

    const { result } = renderHook(() =>
      useProjectSearch(1, "MT", { pageSize: 50 }),
    );

    await waitFor(() => expect(result.current.shown).toBe(50));

    await act(async () => {
      await result.current.loadMore();
    });

    const rendered = result.current.results.documents.reduce(
      (total, document) => total + document.matches.length,
      0,
    );

    expect(result.current.shown).toBe(rendered);
  });
});

describe("a failure to load more", () => {
  it("does not outlive the query it belongs to", async () => {
    /**
     * Regression: the failure was held unkeyed, and the panel hides the
     * results *and* the retry control whenever an error is present - so
     * one failed click blanked search for the rest of the session, for
     * every later query.
     */

    stub([
      { body: aPage([aDocument(7, 50)], 200) },
      { fail: true },
      { fail: true },
      { body: aPage([aDocument(9, 3)], 3) },
    ]);

    const { result, rerender } = renderHook(
      ({ query }) => useProjectSearch(1, query, { pageSize: 50 }),
      { initialProps: { query: "MT" } },
    );

    await waitFor(() => expect(result.current.shown).toBe(50));

    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.error).not.toBeNull();

    rerender({ query: "TR1" });

    await waitFor(() => expect(result.current.submitted).toBe("TR1"));
    await waitFor(() => expect(result.current.error).toBeNull());

    expect(result.current.results.documents).toHaveLength(1);
  });
});

describe("pages never cross a project boundary", () => {
  it("does not merge one project's extra pages into another's results", async () => {
    /**
     * The cache was keyed on the query alone. Two projects searched for
     * the same word would share it, and one project's documents would
     * be listed under the other's search - the one thing this feature
     * promises cannot happen.
     */

    stub([
      { body: aPage([aDocument(7, 50)], 200) },
      { body: aPage([aDocument(8, 50)], 200) },
      { body: aPage([aDocument(99, 2, "altro.pdf")], 2) },
    ]);

    const { result, rerender } = renderHook(
      ({ projectId }) => useProjectSearch(projectId, "MT", { pageSize: 50 }),
      { initialProps: { projectId: 1 } },
    );

    await waitFor(() => expect(result.current.shown).toBe(50));

    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.shown).toBe(100);

    rerender({ projectId: 2 });

    await waitFor(() =>
      expect(
        result.current.results.documents.map((d) => d.document_id),
      ).toEqual([99]),
    );

    expect(result.current.shown).toBe(2);
  });
});

describe("asking for nothing", () => {
  it("performs no request for an empty query", async () => {
    const calls = stub([{ body: aPage([], 0) }]);

    const { result } = renderHook(() =>
      useProjectSearch(1, "   ", { pageSize: 50 }),
    );

    await waitFor(() => expect(result.current.searching).toBe(false));

    expect(
      calls.filter((call) => call.startsWith(BASE)),
    ).toHaveLength(0);
    expect(result.current.results.total_matches).toBe(0);
    expect(result.current.hasMore).toBe(false);
  });
});
