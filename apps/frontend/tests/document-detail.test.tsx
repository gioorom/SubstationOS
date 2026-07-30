/**
 * Document detail and the governed download (Milestone 30.1.3).
 *
 * Two capabilities the frontend gained, and one it must not have: the
 * URL of a stored file is never constructed here, and the filename comes
 * from the header the backend already sanitised.
 */

import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { useDocument } from "@/hooks/useDocuments";
import { downloadDocumentContent } from "@/lib/resources/documents";
import { NotFoundError, ServerError } from "@/lib/api";

import { aDocumentDetail, stubBackend } from "./_backend";

/**
 * The stub returns JSON; a download returns bytes. This replaces `fetch`
 * with one that answers a binary response, so the resource module's own
 * header parsing is what is under test.
 */
function stubDownload(options: {
  body?: BodyInit;
  status?: number;
  disposition?: string | null;
  contentType?: string;
}) {
  const calls: string[] = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      calls.push(String(input));

      const headers = new Headers({
        "Content-Type": options.contentType ?? "application/pdf",
      });

      if (options.disposition != null) {
        headers.set("Content-Disposition", options.disposition);
      }

      return new Response(options.body ?? new Blob([new Uint8Array([1])]), {
        status: options.status ?? 200,
        headers,
      });
    }),
  );

  return calls;
}

describe("document detail", () => {
  it("loads from GET /documents/{id}", async () => {
    const backend = stubBackend({
      "GET /documents/7": {
        body: aDocumentDetail({ id: 7, filename: "schema.pdf" }),
      },
    });

    const { result } = renderHook(() => useDocument(7));

    await waitFor(() => expect(result.current.document).not.toBeNull());

    expect(result.current.document?.filename).toBe("schema.pdf");
    expect(backend.requestsFor("GET", "/documents/7")).toHaveLength(1);

    // It does not read the whole list to find one document.
    expect(backend.requestsFor("GET", "/documents/")).toHaveLength(0);
  });

  it("exposes the content identity the pipeline binds its artefacts to", async () => {
    stubBackend({
      "GET /documents/7": {
        body: aDocumentDetail({
          id: 7,
          content_checksum: "c".repeat(64),
          checksum_algorithm: "sha256",
          size_bytes: 4096,
        }),
      },
    });

    const { result } = renderHook(() => useDocument(7));

    await waitFor(() => expect(result.current.document).not.toBeNull());

    expect(result.current.document?.content_checksum).toBe("c".repeat(64));
    expect(result.current.document?.size_bytes).toBe(4096);
  });

  it("reports no checksum for a document that was never ingested", async () => {
    stubBackend({
      "GET /documents/7": {
        body: aDocumentDetail({
          id: 7,
          content_checksum: null,
          checksum_algorithm: null,
          size_bytes: null,
          ingestion_state: null,
        }),
      },
    });

    const { result } = renderHook(() => useDocument(7));

    await waitFor(() => expect(result.current.document).not.toBeNull());

    // An un-run identity is not a zero, and the UI does not invent one.
    expect(result.current.document?.content_checksum).toBeNull();
    expect(result.current.document?.size_bytes).toBeNull();
  });

  it("carries no storage field at all", async () => {
    stubBackend({ "GET /documents/7": { body: aDocumentDetail({ id: 7 }) } });

    const { result } = renderHook(() => useDocument(7));

    await waitFor(() => expect(result.current.document).not.toBeNull());

    for (const field of Object.keys(result.current.document ?? {})) {
      expect(field).not.toContain("path");
      expect(field).not.toContain("storage");
    }
  });

  it("reports a 404 as a missing document", async () => {
    stubBackend({
      "GET /documents/99": {
        status: 404,
        body: { detail: "Document '99' does not exist." },
      },
    });

    const { result } = renderHook(() => useDocument(99));

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toBe("Il documento richiesto non esiste.");
    expect(result.current.failure).toBeInstanceOf(NotFoundError);
  });

  it("does not read anything when the id is unresolved", async () => {
    const backend = stubBackend({});

    const { result } = renderHook(() => useDocument(undefined));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(backend.requests).toHaveLength(0);
  });
});

describe("the governed download", () => {
  it("fetches the bytes from /documents/{id}/content", async () => {
    const calls = stubDownload({
      disposition: 'attachment; filename="schema.pdf"',
    });

    const content = await downloadDocumentContent(7);

    expect(calls).toEqual([
      "http://127.0.0.1:8000/documents/7/content",
    ]);
    expect(content.filename).toBe("schema.pdf");
    expect(content.blob.size).toBeGreaterThan(0);
  });

  it("takes the filename from the header, never from a path", async () => {
    stubDownload({
      disposition: 'attachment; filename="schema-funzionale_rev-02.pdf"',
    });

    const content = await downloadDocumentContent(7);

    expect(content.filename).toBe("schema-funzionale_rev-02.pdf");
  });

  it("falls back to a safe name when the header is absent", async () => {
    stubDownload({ disposition: null });

    const content = await downloadDocumentContent(7);

    expect(content.filename).toBe("documento");
  });

  it("never asks for a path - the id is the only input", async () => {
    const calls = stubDownload({
      disposition: 'attachment; filename="a.pdf"',
    });

    await downloadDocumentContent(42);

    // No storage reference, no filename, no directory in the URL.
    expect(calls[0]).toBe("http://127.0.0.1:8000/documents/42/content");
    expect(calls[0]).not.toContain("storage");
  });

  it("translates a 404 into the typed error, as any other read", async () => {
    stubDownload({
      status: 404,
      body: JSON.stringify({ detail: "content is not available" }),
      contentType: "application/json",
    });

    const failure = await downloadDocumentContent(7).catch(
      (error: unknown) => error,
    );

    // A raw read changes what a success looks like, never a failure.
    expect(failure).toBeInstanceOf(NotFoundError);
  });

  it("translates a 500 into the typed error", async () => {
    stubDownload({
      status: 500,
      body: JSON.stringify({ detail: "unreadable" }),
      contentType: "application/json",
    });

    const failure = await downloadDocumentContent(7).catch(
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(ServerError);
  });

  it("reports a missing file with wording an engineer can act on", async () => {
    stubBackend({
      "GET /documents/7": {
        body: aDocumentDetail({ id: 7, content_available: false }),
      },
      "GET /documents/7/content": {
        status: 404,
        body: { detail: "the stored content no longer exists" },
      },
    });

    const { result } = renderHook(() => useDocument(7));

    await waitFor(() => expect(result.current.document).not.toBeNull());

    await act(async () => {
      await result.current.download().catch(() => undefined);
    });

    expect(result.current.downloadError).toContain(
      "file archiviato non esiste",
    );
  });
});
